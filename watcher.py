#!/usr/bin/env python3
"""
Gmail watcher for priority senders.

For each new email matching priority_senders.txt:
  1. Send Telegram alert with sender + subject.
  2. Summarize via local Ollama.
  3. Build PDF and save to ~/email-pdfs/.
  4. Send PDF to Telegram as a document.

One-shot: run periodically via LaunchAgent (StartInterval=300).
Dedup via watcher_state.json (last 200 message IDs).
"""

import os
import sys
import json
import base64
import logging
import re
import traceback
from pathlib import Path
from datetime import datetime, timezone
import requests

from firestore_activity import report_run
from firestore_alerts import send_alert, send_document

from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

# ---------- Config ----------
BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = Path.home() / "email-pdfs"
STATE_FILE = BASE_DIR / "watcher_state.json"
SENDERS_FILE = BASE_DIR / "priority_senders.txt"
WATCHER_CONFIG = BASE_DIR / "watcher_config.json"
MAX_PROCESSED = 200
DEFAULT_LOOKBACK = "1d"

load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AUTHORIZED_CHAT_ID = int(os.environ["AUTHORIZED_CHAT_ID"])
USER_UID = os.environ.get("EMAIL2PPT_USER_UID", "").strip()
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

GMAIL_TOKEN_PATH = BASE_DIR / "gmail_token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = BASE_DIR / "watcher.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("watcher")


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


def load_priority_senders() -> list:
    if not SENDERS_FILE.exists():
        return []
    senders = []
    for line in SENDERS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            senders.append(line)
    return senders


def _load_lookback() -> str:
    if not WATCHER_CONFIG.exists():
        return DEFAULT_LOOKBACK
    try:
        v = json.loads(WATCHER_CONFIG.read_text()).get("lookback", DEFAULT_LOOKBACK)
    except (json.JSONDecodeError, OSError):
        return DEFAULT_LOOKBACK
    return v if isinstance(v, str) and v.strip() else DEFAULT_LOOKBACK


def fetch_new_emails(senders: list) -> list:
    if not senders:
        return []
    service = get_gmail_service()
    or_clause = " OR ".join(f"from:{s}" for s in senders)
    query = f"({or_clause}) newer_than:{_load_lookback()}"
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
        body = _extract_body(msg["payload"])[:8000]
        emails.append(
            {
                "id": m["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", "(no subject)"),
                "date": headers.get("Date", ""),
                "body": body,
            }
        )
    return emails


# ---------- State (dedup) ----------
def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"processed_ids": []}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        log.warning("State file corrupt, resetting")
        return {"processed_ids": []}


def save_state(processed_ids: list):
    STATE_FILE.write_text(json.dumps({"processed_ids": processed_ids}, indent=2))


# ---------- LLM summarization ----------
EMAIL_PROMPT = """You are Shawn's executive assistant. Summarize the email below into structured JSON ONLY (no prose, no markdown fences).

Required JSON shape:
{{
  "context": ["1-2 short bullets giving who they are / why writing"],
  "key_points": ["3-6 bullets of specific facts, claims, requests, numbers, quotes from the email"],
  "asks": ["bullets of what they want from Shawn, or one item 'FYI only - no action'"],
  "suggested_response": "one short line e.g. 'Reply Friday', 'No reply needed'",
  "urgency": "low" | "med" | "high"
}}

Style:
- Specific over generic. Pull real numbers, names, dates.
- Skip greetings, signatures, quoted-thread history.
- Output ONLY the JSON object.

EMAIL:
From: {from_}
Subject: {subject}
Date: {date}

{body}
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
    return text


def summarize_email(client: OpenAI, email: dict) -> dict:
    prompt = EMAIL_PROMPT.format(
        from_=email["from"],
        subject=email["subject"],
        date=email["date"],
        body=email["body"],
    )
    resp = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    text = _strip_fences(resp.choices[0].message.content or "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning(f"JSON parse failed for {email['subject']!r}; using fallback")
        return {
            "context": [],
            "key_points": [text[:400]] if text else [],
            "asks": [],
            "suggested_response": "",
            "urgency": "low",
        }


# ---------- PDF builder ----------
URGENCY_HEX = {"low": "#34C759", "med": "#FF9F0A", "high": "#FF3B30"}


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(email: dict, summary: dict, out_path: Path):
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=14, spaceAfter=4, spaceBefore=10)
    body_style = styles["BodyText"]
    meta = ParagraphStyle("meta", parent=body_style, fontSize=10, textColor=HexColor("#48484A"))

    urg = (summary.get("urgency") or "low").lower()
    if urg not in URGENCY_HEX:
        urg = "low"
    badge = ParagraphStyle(
        "badge", parent=body_style, fontSize=11, textColor=HexColor(URGENCY_HEX[urg]),
    )

    story = []
    story.append(Paragraph(_html_escape(email["subject"]), h1))
    story.append(Paragraph(f"From: {_html_escape(email['from'])}", meta))
    story.append(Paragraph(f"Date: {_html_escape(email['date'])}", meta))
    story.append(Paragraph(f"Urgency: <b>{urg.upper()}</b>", badge))
    story.append(Spacer(1, 0.15 * inch))

    for label, key in [
        ("Context", "context"),
        ("Key Points", "key_points"),
        ("Asks / Actions", "asks"),
    ]:
        items = summary.get(key) or []
        if not items:
            continue
        story.append(Paragraph(label, h2))
        for it in items:
            story.append(Paragraph(f"• {_html_escape(str(it))}", body_style))

    if summary.get("suggested_response"):
        story.append(Paragraph("Suggested Response", h2))
        story.append(Paragraph(_html_escape(summary["suggested_response"]), body_style))

    story.append(PageBreak())
    story.append(Paragraph("Original Email", h2))
    raw = email.get("body") or "(empty body)"
    for chunk in raw.split("\n\n"):
        story.append(Paragraph(_html_escape(chunk).replace("\n", "<br/>"), body_style))
        story.append(Spacer(1, 0.08 * inch))

    doc.build(story)


# ---------- Telegram ----------
# Routes via firestore_alerts: customer's own bot if linked, else env shared bot.
def send_telegram(text: str):
    send_alert(USER_UID, text)


def send_telegram_document(path: Path, caption: str):
    send_document(USER_UID, path, caption)


# ---------- Main ----------
def _sender_slug(from_field: str) -> str:
    m = re.search(r"<([^>]+)>", from_field)
    addr = m.group(1) if m else from_field
    addr = addr.split("@")[0]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", addr)[:30] or "unknown"


def main():
    started = datetime.now(timezone.utc)
    outputs: list[str] = []
    new_count = 0
    try:
        log.info("=" * 60)
        log.info("Watcher run starting")

        senders = load_priority_senders()
        if not senders:
            log.warning("No priority senders configured")
            report_run("watcher", "ok", started_at=started, email_count=0)
            return

        log.info(f"Priority senders ({len(senders)}): {senders}")

        state = load_state()
        seen_ids = list(state.get("processed_ids", []))
        seen = set(seen_ids)

        emails = fetch_new_emails(senders)
        log.info(f"Matching emails (last 24h): {len(emails)}")

        new_emails = [e for e in emails if e["id"] not in seen]
        new_count = len(new_emails)
        log.info(f"New (not yet processed): {new_count}")

        if not new_emails:
            report_run("watcher", "ok", started_at=started, email_count=0)
            return

        client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama-local")

        for email in new_emails:
            try:
                send_telegram(f"📬 New from {email['from']}\n{email['subject']}")

                log.info(f"Summarizing: {email['subject'][:60]}")
                summary = summarize_email(client, email)

                run_at = datetime.now()
                pdf_name = (
                    run_at.strftime("%Y-%m-%d-%H%M%S")
                    + "-" + _sender_slug(email["from"]) + ".pdf"
                )
                pdf_path = OUTPUT_DIR / pdf_name
                build_pdf(email, summary, pdf_path)
                log.info(f"PDF saved: {pdf_path}")
                outputs.append(pdf_name)

                urg = (summary.get("urgency") or "low").upper()
                caption = f"{email['subject']}\nUrgency: {urg}"
                send_telegram_document(pdf_path, caption)

                seen_ids.append(email["id"])
                seen.add(email["id"])
            except Exception as e:
                log.exception(f"Failed processing {email['id']}: {e}")
                # Don't add to seen — retry next run

        if len(seen_ids) > MAX_PROCESSED:
            seen_ids = seen_ids[-MAX_PROCESSED:]
        save_state(seen_ids)
        log.info(f"State saved ({len(seen_ids)} ids)")
        report_run(
            "watcher",
            "ok",
            started_at=started,
            email_count=new_count,
            outputs=outputs,
        )
    except Exception:
        report_run(
            "watcher",
            "error",
            started_at=started,
            email_count=new_count,
            outputs=outputs,
            error=traceback.format_exc(),
        )
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception("Watcher run failed")
        try:
            send_telegram(f"⚠️ Watcher failed: {e}\nSee {LOG_PATH}")
        except Exception:
            pass
        raise
