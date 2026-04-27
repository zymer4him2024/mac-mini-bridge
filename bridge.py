#!/usr/bin/env python3
"""
Telegram <-> Ollama bridge for Shawn's Mac mini.

Uses a local Ollama model (default: llama3.1:8b) via Ollama's
OpenAI-compatible API at http://localhost:11434/v1.

What it does:
  1. Listens for Telegram messages from your authorized chat (only yours).
  2. Forwards the message to your local Ollama model.
  3. The model can search/read Gmail and create email drafts using tools.
  4. Sends the model's reply back to you on Telegram.

Runs forever. Designed to be started by launchd on boot.
"""

import os
import json
import base64
import logging
import subprocess
from pathlib import Path
from email.mime.text import MIMEText

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from firestore_telegram import (
    LinkLookupStatus,
    consume_link_token,
    delete_telegram_link,
    find_telegram_link,
)

# ---------- Config ----------
BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AUTHORIZED_CHAT_ID = int(os.environ["AUTHORIZED_CHAT_ID"])
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

GMAIL_TOKEN_PATH = BASE_DIR / "gmail_token.json"
GMAIL_CREDS_PATH = BASE_DIR / "gmail_credentials.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

LOG_PATH = BASE_DIR / "bridge.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("bridge")

# httpx logs full request URLs at INFO level, which leaks the Telegram bot
# token in every getUpdates poll. Suppress to WARNING.
logging.getLogger("httpx").setLevel(logging.WARNING)

# OpenAI client pointed at local Ollama
llm = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama-local")

# Short-term in-memory conversation (cleared on restart or /reset)
conversation_history: list = []
MAX_TURNS = 16  # smaller than Anthropic version - 8B context is tighter
MAX_TOOL_LOOPS = 6  # safety cap so a confused model can't loop forever


# ---------- Gmail helpers ----------
def get_gmail_service():
    creds = None
    if GMAIL_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_PATH), GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(GMAIL_CREDS_PATH), GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
        GMAIL_TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def search_emails(query: str, max_results: int = 10) -> list:
    service = get_gmail_service()
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    out = []
    for m in result.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=m["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        out.append(
            {
                "id": m["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
            }
        )
    return out


def _extract_body(payload) -> str:
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode(
            "utf-8", errors="replace"
        )
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain" and part["body"].get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                "utf-8", errors="replace"
            )
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


def read_email(message_id: str) -> dict:
    service = get_gmail_service()
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    return {
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "body": _extract_body(msg["payload"])[:6000],  # cap for 8B context
    }


def create_draft(to: str, subject: str, body: str) -> dict:
    service = get_gmail_service()
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw}})
        .execute()
    )
    return {
        "draft_id": draft["id"],
        "status": "draft created - review in Gmail before sending",
    }


# ---------- OpenAI-style tool spec (Ollama uses this format) ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": (
                "Search Shawn's Gmail using standard Gmail search syntax. "
                "Examples: 'is:unread', 'from:x@y.com newer_than:2d', "
                "'is:important newer_than:1d'. Returns list of {id, from, subject, date, snippet}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Gmail search query"},
                    "max_results": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": "Read full body of an email by message_id (get id from search_emails first).",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Gmail message id"},
                },
                "required": ["message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft",
            "description": (
                "Create a Gmail draft (does NOT send — Shawn reviews and sends). "
                "Always confirm recipient and intent before using."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]


def execute_tool(name: str, args: dict):
    if name == "search_emails":
        return search_emails(args["query"], args.get("max_results", 10))
    if name == "read_email":
        return read_email(args["message_id"])
    if name == "create_draft":
        return create_draft(args["to"], args["subject"], args["body"])
    return {"error": f"unknown tool: {name}"}


# ---------- LLM conversation loop ----------
SYSTEM_PROMPT = """You are Shawn's executive assistant, running locally on his Mac mini and reached via Telegram.
Shawn is the CEO of a small AI-detection and AI-creation software company.
He values Apple-like clarity: simple, concise, no jargon.

You have tools to search Gmail, read individual emails, and create drafts.
RULES:
- Use tools whenever the user asks about email. Don't guess at email content.
- After getting tool results, give a SHORT direct answer in plain English (Telegram messages, not essays).
- Use bullet points for lists; prose for single answers.
- Never send email — only create drafts. Shawn reviews and presses send himself.
- When confirming a draft, summarize: who, subject, key point.
- If unsure who a sender is or whether something is urgent, say so — don't guess.
"""


def ask_llm(user_message: str) -> str:
    conversation_history.append({"role": "user", "content": user_message})

    for _ in range(MAX_TOOL_LOOPS):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history
        try:
            resp = llm.chat.completions.create(
                model=OLLAMA_MODEL,
                messages=messages,
                tools=TOOLS,
                temperature=0.3,
            )
        except Exception as e:
            log.exception("LLM call failed")
            return f"Local model error: {e}"

        msg = resp.choices[0].message

        # If the model wants to call tools, run them and loop
        if msg.tool_calls:
            conversation_history.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                log.info(f"Tool: {tc.function.name}({tc.function.arguments})")
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    result = execute_tool(tc.function.name, args)
                except Exception as e:
                    log.exception("Tool error")
                    result = {"error": str(e)}
                conversation_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str)[:6000],
                    }
                )
            continue

        # Final text answer
        text = msg.content or "(no response)"
        conversation_history.append({"role": "assistant", "content": text})
        break
    else:
        text = "I got stuck in a tool loop. Try /reset and rephrase."

    # Keep history bounded
    if len(conversation_history) > MAX_TURNS * 2:
        del conversation_history[: len(conversation_history) - MAX_TURNS * 2]

    return text


# ---------- Telegram handlers ----------
def authorized(update: Update) -> bool:
    return bool(update.effective_chat) and update.effective_chat.id == AUTHORIZED_CHAT_ID


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /start <token-or-shortCode> — link an email2ppt account.
    raw = ctx.args[0].strip() if ctx.args else ""
    # Accept "123-456" or "123 456" as well as "123456" for the manual code.
    token_or_code = raw.replace("-", "").replace(" ", "")
    if token_or_code:
        chat = update.effective_chat
        user = update.effective_user
        try:
            status, uid = consume_link_token(
                token_or_code,
                chat.id,
                user.username if user else None,
                user.first_name if user else None,
            )
        except Exception:
            log.exception("consume_link_token failed")
            await update.message.reply_text(
                "Something went wrong on our end. Try again in a moment."
            )
            return

        fresh_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Get a fresh link", url="https://email2ppt.web.app")]]
        )

        if status is LinkLookupStatus.OK:
            await update.message.reply_text(
                "✅ Linked your email2ppt account. Future alerts will arrive here."
            )
            return
        if status is LinkLookupStatus.CONSUMED_SELF:
            await update.message.reply_text(
                "You're already connected ✓ — alerts will arrive here. "
                "Send /help to see what you can do."
            )
            return
        if status is LinkLookupStatus.CONSUMED_OTHER:
            await update.message.reply_text(
                "This link was already used by someone else. "
                "Open the email2ppt portal to get a fresh one.",
                reply_markup=fresh_button,
            )
            return
        if status is LinkLookupStatus.EXPIRED:
            await update.message.reply_text(
                "This link expired. Get a fresh one — they're good for 24 hours.",
                reply_markup=fresh_button,
            )
            return
        # NOT_FOUND
        await update.message.reply_text(
            "We couldn't find that link. Open the email2ppt portal to get a fresh one.",
            reply_markup=fresh_button,
        )
        return

    # Plain /start — admin gets the existing welcome; everyone else gets onboarding.
    if authorized(update):
        await update.message.reply_text(
            f"Hi Shawn — running locally on your Mac mini ({OLLAMA_MODEL}). "
            "Ask me anything, or say 'check inbox'."
        )
        return
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Get my link", url="https://email2ppt.web.app")]]
    )
    await update.message.reply_text(
        "Welcome to email2ppt — your alerts will arrive here once you connect "
        "your account.",
        reply_markup=keyboard,
    )


async def whoami(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        link = find_telegram_link(chat_id)
    except Exception:
        log.exception("find_telegram_link failed")
        await update.message.reply_text(
            "Something went wrong on our end. Try again in a moment."
        )
        return
    if not link:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Get my link", url="https://email2ppt.web.app")]]
        )
        await update.message.reply_text(
            "You're not connected to email2ppt yet.",
            reply_markup=keyboard,
        )
        return

    name = (
        f"@{link['username']}" if link["username"]
        else (link["firstName"] or "linked")
    )
    linked_at = link["linkedAt"]
    since = linked_at.strftime("%Y-%m-%d") if linked_at else "earlier"
    email = link["gmailEmail"]
    if email and "@" in email:
        local, domain = email.split("@", 1)
        masked = f"{local[0]}***@{domain}"
        email_line = f"\nLinked to {masked}."
    else:
        email_line = ""
    await update.message.reply_text(
        f"You're connected as {name} since {since}.{email_line}"
    )


async def unlink(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        link = find_telegram_link(chat_id)
    except Exception:
        log.exception("find_telegram_link failed")
        await update.message.reply_text(
            "Something went wrong on our end. Try again in a moment."
        )
        return
    if not link:
        await update.message.reply_text("You're not connected to email2ppt.")
        return
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Yes, disconnect", callback_data="unlink:confirm"),
            InlineKeyboardButton("Cancel", callback_data="unlink:cancel"),
        ]]
    )
    await update.message.reply_text(
        "Disconnect this Telegram from email2ppt? Alerts will stop arriving here.",
        reply_markup=keyboard,
    )


async def unlink_callback(update: Update, _: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data == "unlink:cancel":
        await query.edit_message_text("Cancelled. You're still connected.")
        return
    if data != "unlink:confirm":
        return
    chat_id = query.message.chat.id
    try:
        link = find_telegram_link(chat_id)
    except Exception:
        log.exception("find_telegram_link failed during unlink confirm")
        await query.edit_message_text(
            "Something went wrong on our end. Try again in a moment."
        )
        return
    if not link:
        await query.edit_message_text("Already disconnected.")
        return
    try:
        delete_telegram_link(link["uid"])
    except Exception:
        log.exception("delete_telegram_link failed")
        await query.edit_message_text(
            "Couldn't disconnect. Try again in a moment."
        )
        return
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Get a fresh link", url="https://email2ppt.web.app")]]
    )
    await query.edit_message_text(
        "Disconnected. Get a new link to reconnect.",
        reply_markup=keyboard,
    )


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        text = (
            "Commands:\n"
            "/start — link your email2ppt account\n"
            "/whoami — check your connection\n"
            "/unlink — disconnect this Telegram\n"
            "/push — get your latest digest now\n"
            "/ppt <query> — generate a PowerPoint from emails\n"
            "/reset — clear conversation history\n"
            "/help — show this list"
        )
    else:
        text = (
            "Commands:\n"
            "/start — link your email2ppt account\n"
            "/whoami — check your connection\n"
            "/unlink — disconnect this Telegram\n"
            "/help — show this list"
        )
    await update.message.reply_text(text)


async def reset(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    conversation_history.clear()
    await update.message.reply_text("Conversation reset.")


async def trigger_digest(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Run the email digest immediately as a background subprocess."""
    if not authorized(update):
        return
    digest_path = BASE_DIR / "digest.py"
    python_path = BASE_DIR / "venv" / "bin" / "python"
    if not digest_path.exists():
        await update.message.reply_text(
            "Digest script not found at " + str(digest_path)
        )
        return
    try:
        subprocess.Popen(
            [str(python_path), str(digest_path)],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("Triggered digest.py via 'push' command")
        await update.message.reply_text(
            "📬 On it — running the email digest now. Summary will arrive in a moment."
        )
    except Exception as e:
        log.exception("Failed to launch digest")
        await update.message.reply_text(f"Couldn't start digest: {e}")


async def trigger_ppt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Generate a PowerPoint deck from emails matching a Gmail query."""
    if not authorized(update):
        return
    query = " ".join(ctx.args).strip() if ctx.args else ""
    if not query:
        await update.message.reply_text(
            "Usage: /ppt <gmail-query>\nExample: /ppt from:investor newer_than:7d"
        )
        return
    ppt_path = BASE_DIR / "ppt.py"
    python_path = BASE_DIR / "venv" / "bin" / "python"
    if not ppt_path.exists():
        await update.message.reply_text("PPT script not found at " + str(ppt_path))
        return
    try:
        subprocess.Popen(
            [str(python_path), str(ppt_path), query],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info(f"Triggered ppt.py with query: {query}")
        await update.message.reply_text(f"📊 Generating PPT for: {query}")
    except Exception as e:
        log.exception("Failed to launch ppt")
        await update.message.reply_text(f"Couldn't start PPT: {e}")


async def handle_message(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        log.info(f"Non-admin message from chat_id={update.effective_chat.id}")
        await update.message.reply_text(
            "Conversational features are admin-only. Your email2ppt alerts "
            "will arrive automatically here once linked."
        )
        return

    text = update.message.text or ""
    log.info(f"Incoming: {text[:120]}")

    # Special keyword: "push" triggers an immediate email digest
    if text.strip().lower() in ("push", "/push"):
        await trigger_digest(update, _)
        return

    await update.message.chat.send_action("typing")

    try:
        reply = ask_llm(text)
    except Exception as e:
        log.exception("LLM error")
        reply = f"Something went wrong: {e}"

    # Telegram 4096-char cap per message
    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i : i + 4000])


def main():
    log.info(f"Starting Telegram bridge with model={OLLAMA_MODEL} via {OLLAMA_BASE_URL}")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("unlink", unlink))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("push", trigger_digest))
    app.add_handler(CommandHandler("ppt", trigger_ppt))
    app.add_handler(CallbackQueryHandler(unlink_callback, pattern=r"^unlink:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
