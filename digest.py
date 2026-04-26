#!/usr/bin/env python3
"""
Daily email digest for Shawn.

What it does:
  1. Reads ~/telegram-bridge/priority_senders.txt for the priority list.
  2. Searches Gmail for emails from those senders in the last 24 hours.
  3. Summarizes them with the local Ollama model.
  4. Saves a Markdown file to ~/email-digests/YYYY-MM-DD-morning.md.
  5. Sends a compact version to Telegram.

Designed to be run by launchd at 7:00 AM daily.
"""

import os
import base64
import logging
import traceback
from pathlib import Path
from datetime import datetime, timezone
import requests

from firestore_activity import report_run

from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ---------- Config ----------
BRIDGE_DIR = Path.home() / "telegram-bridge"
DIGEST_DIR = Path.home() / "email-digests"
SENDERS_FILE = BRIDGE_DIR / "priority_senders.txt"

load_dotenv(BRIDGE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AUTHORIZED_CHAT_ID = int(os.environ["AUTHORIZED_CHAT_ID"])
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")

GMAIL_TOKEN_PATH = BRIDGE_DIR / "gmail_token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

DIGEST_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = BRIDGE_DIR / "digest.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("digest")


# ---------- Gmail helpers ----------
def get_gmail_service():
    creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_PATH), GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        GMAIL_TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


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


def fetch_priority_emails(senders: list) -> list:
    """Fetch emails from priority senders received in the last 24 hours."""
    service = get_gmail_service()

    # Build OR query — Gmail search syntax: (from:a OR from:b) newer_than:1d
    or_clause = " OR ".join(f"from:{s}" for s in senders)
    query = f"({or_clause}) newer_than:1d"
    log.info(f"Gmail query: {query}")

    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=25)
        .execute()
    )
    messages = result.get("messages", [])

    emails = []
    for m in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=m["id"], format="full")
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        body = _extract_body(msg["payload"])[:4000]  # cap body to keep prompt small
        emails.append(
            {
                "id": m["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
                "body": body,
            }
        )
    return emails


# ---------- Sender list ----------
def load_priority_senders() -> list:
    if not SENDERS_FILE.exists():
        SENDERS_FILE.write_text(
            "# Priority Senders for Daily Email Digest\n"
            "# One sender per line. Lines starting with # are ignored.\n"
            "#\n"
            "# Examples:\n"
            "#   jane@acme.com         (specific email)\n"
            "#   @sequoia.com          (anyone at sequoia.com)\n"
            "#   ceo@yourpartner.io\n"
            "#\n"
            "# Add yours below this line:\n\n"
        )
        log.warning(f"Created empty {SENDERS_FILE}")
        return []

    senders = []
    for line in SENDERS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            senders.append(line)
    return senders


# ---------- LLM summarization ----------
def summarize_emails(emails: list) -> tuple:
    """Returns (telegram_short_version, full_markdown_for_file)."""
    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama-local")

    blocks = []
    for i, e in enumerate(emails, 1):
        blocks.append(
            f"### Email {i}\n"
            f"From: {e['from']}\n"
            f"Subject: {e['subject']}\n"
            f"Date: {e['date']}\n\n"
            f"{e['body']}\n"
        )
    body_text = "\n---\n".join(blocks)

    full_prompt = f"""You are Shawn's executive assistant. Summarize the following {len(emails)} priority emails Shawn received in the last 24 hours.

Output format - strict Markdown:

# Top 3 Things to Know

- Bullet 1 (the single most important takeaway)
- Bullet 2
- Bullet 3

# Email-by-Email Detail

For EACH email, produce this structure:

## [Sender name, or email if no name]
- **Subject:** [verbatim subject line]
- **Date:** [date received]
- **Context:** 1-2 bullets giving the situation / who they are / why they're writing
- **Key points:**
  - 3-6 bullets covering the main content. Each bullet should be ONE specific fact, claim, request, number, or quote - not a paraphrased blob. Pull actual specifics (names, dates, numbers, dollar figures, deadlines).
- **Asks / actions:**
  - What they explicitly want from Shawn (or "FYI only - no action")
  - Any embedded deadline or implied timing
- **Suggested response:** one short line (e.g., "Reply Friday confirming the meeting", "Forward to legal", "Decline politely", "No reply needed")
- **Urgency:** low / medium / high (with one-line justification)

Style:
- Bullet points throughout - not paragraphs.
- Specific over generic. Pull real numbers, names, and quotes from the email.
- Skip greetings, signatures, and email-thread quoted history.
- If multiple emails are clearly part of one thread, only summarize the most recent fully.
- Apple-style: precise, restrained, no filler.

EMAILS TO SUMMARIZE:

{body_text}
"""

    resp = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0.3,
    )
    full_markdown = resp.choices[0].message.content or "(no summary generated)"

    # Compact version for Telegram (no markdown headers, scannable)
    short_prompt = f"""Compress the following digest into a Telegram-friendly message (under 2000 chars total).

Strict format:

Top 3:
- [most important takeaway]
- [second]
- [third]

Per email:
- [Sender]: [one short sentence] - [low/med/high]
- [Sender]: [one short sentence] - [low/med/high]

Rules:
- No markdown headers (no #, ##, **)
- One bullet per email, max 12 words each
- Use the actual sender's name if available, else email

DIGEST TO COMPRESS:

{full_markdown}
"""

    resp2 = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": short_prompt}],
        temperature=0.3,
    )
    short_telegram = resp2.choices[0].message.content or "(no short summary)"

    return short_telegram, full_markdown


# ---------- File save ----------
def save_markdown(full_markdown: str, run_at: datetime, email_count: int) -> Path:
    filename = run_at.strftime("%Y-%m-%d") + "-morning.md"
    path = DIGEST_DIR / filename
    header = (
        f"# Daily Email Digest\n"
        f"**{run_at.strftime('%A, %B %d, %Y')}** · "
        f"Generated {run_at.strftime('%H:%M')} · "
        f"{email_count} priority emails\n\n"
        f"---\n\n"
    )
    path.write_text(header + full_markdown)
    return path


# ---------- Telegram delivery ----------
def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for i in range(0, len(text), 4000):
        chunk = text[i : i + 4000]
        try:
            r = requests.post(
                url,
                json={
                    "chat_id": AUTHORIZED_CHAT_ID,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            r.raise_for_status()
        except Exception as e:
            log.error(f"Telegram send failed: {e}")


# ---------- Main ----------
def main():
    started = datetime.now(timezone.utc)
    outputs: list[str] = []
    email_count = 0
    try:
        log.info("=" * 60)
        log.info("Starting daily email digest")
        run_at = datetime.now()

        senders = load_priority_senders()
        if not senders:
            msg = (
                f"No priority senders configured.\n"
                f"Edit: {SENDERS_FILE}"
            )
            log.warning(msg)
            send_telegram(f"📭 Daily digest skipped — no senders configured.\n\n{msg}")
            report_run("digest", "ok", started_at=started, email_count=0)
            return

        log.info(f"Priority senders ({len(senders)}): {senders}")

        emails = fetch_priority_emails(senders)
        email_count = len(emails)
        log.info(f"Matching emails in last 24h: {email_count}")

        if not emails:
            no_email_md = (
                f"## No priority emails today\n\n"
                f"No emails received from your {len(senders)} priority senders "
                f"in the last 24 hours. Quiet morning.\n"
            )
            md_path = save_markdown(no_email_md, run_at, 0)
            outputs.append(md_path.name)
            send_telegram(
                f"📭 Daily digest — {run_at.strftime('%a %b %d')}\n"
                f"No priority emails in the last 24 hours."
            )
            report_run(
                "digest",
                "ok",
                started_at=started,
                email_count=0,
                outputs=outputs,
            )
            return

        short, full = summarize_emails(emails)

        md_path = save_markdown(full, run_at, len(emails))
        log.info(f"Saved digest to {md_path}")
        outputs.append(md_path.name)

        telegram_msg = (
            f"📬 Daily Digest — {run_at.strftime('%a %b %d')}\n"
            f"{len(emails)} priority emails · saved to {md_path.name}\n"
            f"\n"
            f"{short}"
        )
        send_telegram(telegram_msg)
        log.info("Digest sent to Telegram")
        report_run(
            "digest",
            "ok",
            started_at=started,
            email_count=email_count,
            outputs=outputs,
        )
    except Exception:
        report_run(
            "digest",
            "error",
            started_at=started,
            email_count=email_count,
            outputs=outputs,
            error=traceback.format_exc(),
        )
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("Digest failed")
        try:
            send_telegram(f"⚠️ Daily digest failed: {e}\nSee {LOG_PATH}")
        except Exception:
            pass
        raise
