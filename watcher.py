#!/usr/bin/env python3
"""
Gmail watcher for priority senders (multi-tenant).

Each cycle enumerates portal-linked customers (users with gmail.email set in
Firestore) and for each runs the same pipeline:
  1. Build credentials from users/{uid}/secrets/gmail.refreshToken.
  2. Send Telegram alert with sender + subject (per-user bot).
  3. Summarize via local Ollama.
  4. Build PDF and save to ~/email-pdfs/{uid}/{subject-slug}/.
     Once a subject folder reaches 5 PDFs, _summary.csv is maintained
     alongside them as a tracker.
  5. Send PDF to Telegram as a document.

One-shot: run periodically via LaunchAgent (StartInterval=300).
Dedup state lives at users/{uid}/state/watcher in Firestore.
"""

import os
import csv
import json
import base64
import logging
import re
import traceback
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

# ---------- Config ----------
BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = Path.home() / "email-pdfs"
MAX_PROCESSED = 200
SUMMARY_THRESHOLD = 5
SUMMARY_FILENAME = "_summary.csv"

# Load .env BEFORE importing firestore_alerts — that module captures
# TELEGRAM_BOT_TOKEN / AUTHORIZED_CHAT_ID at import time for the shared-bot
# fallback. Importing it before load_dotenv leaves both as empty strings.
load_dotenv(BASE_DIR / ".env")

from firestore_activity import _client as firestore_client, report_run  # noqa: E402
from firestore_alerts import send_alert, send_document  # noqa: E402
from firestore_folders import upsert_folder_item  # noqa: E402
from firestore_users import (  # noqa: E402
    GOOGLE_OAUTH_WEB_CLIENT_ID,
    GOOGLE_OAUTH_WEB_CLIENT_SECRET,
    enumerate_linked_users,
    load_user_config,
    load_user_credentials,
)

from openai import OpenAI  # noqa: E402
from google.oauth2.credentials import Credentials  # noqa: E402
from google.auth.exceptions import RefreshError  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402

from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.lib.colors import HexColor  # noqa: E402
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak  # noqa: E402

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = BASE_DIR / "watcher.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("watcher")


# ---------- Gmail helpers ----------
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


def fetch_new_emails(creds: Credentials, senders: list, lookback: str) -> list:
    if not senders:
        return []
    service = build("gmail", "v1", credentials=creds)
    or_clause = " OR ".join(f"from:{s}" for s in senders)
    query = f"({or_clause}) newer_than:{lookback}"
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


# ---------- State (dedup) — per-user, Firestore-backed ----------
def load_user_state(db, uid: str) -> list[str]:
    doc = (
        db.collection("users")
        .document(uid)
        .collection("state")
        .document("watcher")
        .get()
    )
    if not doc.exists:
        return []
    data = doc.to_dict() or {}
    ids = data.get("processedIds") or []
    return [str(x) for x in ids]


def save_user_state(db, uid: str, processed_ids: list[str]) -> None:
    db.collection("users").document(uid).collection("state").document(
        "watcher"
    ).set(
        {
            "processedIds": processed_ids[-MAX_PROCESSED:],
            "updatedAt": datetime.now(timezone.utc),
        }
    )


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


# ---------- Main ----------
def _sender_slug(from_field: str) -> str:
    m = re.search(r"<([^>]+)>", from_field)
    addr = m.group(1) if m else from_field
    addr = addr.split("@")[0]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", addr)[:30] or "unknown"


_REPLY_PREFIX = re.compile(r"^(re|fwd?|fw)\s*:\s*", re.I)


def _subject_slug(subject: str) -> str:
    s = subject or ""
    while _REPLY_PREFIX.match(s):
        s = _REPLY_PREFIX.sub("", s, count=1)
    s = re.sub(r"[^a-zA-Z0-9 _-]", "", s).strip().lower()
    s = re.sub(r"\s+", "-", s)
    return s[:80] or "no-subject"


def write_sidecar(pdf_path: Path, email: dict, summary: dict) -> None:
    sidecar = pdf_path.with_suffix(".json")
    payload = {
        "from": email.get("from", ""),
        "subject": email.get("subject", ""),
        "date": email.get("date", ""),
        "urgency": (summary.get("urgency") or "low"),
        "key_points": summary.get("key_points") or [],
        "asks": summary.get("asks") or [],
        "suggested_response": summary.get("suggested_response") or "",
        "pdf_filename": pdf_path.name,
    }
    sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def update_subject_summary(subject_dir: Path) -> None:
    """Regenerate _summary.csv when the folder has >= SUMMARY_THRESHOLD PDFs.

    Scans all *.json sidecars in the folder, sorts by email date, and writes
    the CSV atomically (tmp + rename). Idempotent — safe to call after every
    PDF save.
    """
    pdfs = list(subject_dir.glob("*.pdf"))
    if len(pdfs) < SUMMARY_THRESHOLD:
        return

    rows = []
    for sidecar in subject_dir.glob("*.json"):
        try:
            data = json.loads(sidecar.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("skipping malformed sidecar %s: %s", sidecar, exc)
            continue
        rows.append(data)

    rows.sort(key=lambda r: r.get("date", ""))

    csv_path = subject_dir / SUMMARY_FILENAME
    tmp_path = csv_path.with_suffix(".csv.tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "date", "from", "urgency",
            "key_points", "asks", "suggested_response", "pdf_filename",
        ])
        for r in rows:
            writer.writerow([
                r.get("date", ""),
                r.get("from", ""),
                r.get("urgency", ""),
                " | ".join(str(x) for x in (r.get("key_points") or [])),
                " | ".join(str(x) for x in (r.get("asks") or [])),
                r.get("suggested_response", ""),
                r.get("pdf_filename", ""),
            ])
    os.replace(tmp_path, csv_path)
    log.info("summary updated: %s (%d rows)", csv_path, len(rows))


def process_user(
    db,
    uid: str,
    llm_client: OpenAI,
) -> None:
    """One iteration of the pipeline for a single user. Never raises."""
    user_started = datetime.now(timezone.utc)
    outputs: list[str] = []
    new_count = 0
    try:
        log.info("[%s] starting", uid)

        cfg = load_user_config(db, uid)
        senders = cfg["senders"]
        lookback = cfg["lookback"]
        log.info("[%s] senders=%d lookback=%s", uid, len(senders), lookback)

        try:
            creds = load_user_credentials(db, uid)
        except RefreshError as exc:
            log.error("[%s] token refresh failed (revoked?): %s", uid, exc)
            report_run(
                "watcher",
                "error",
                started_at=user_started,
                error=f"refresh failed: {exc}",
                uid=uid,
            )
            return
        except (RuntimeError, ValueError) as exc:
            log.error("[%s] credentials load failed: %s", uid, exc)
            report_run(
                "watcher",
                "error",
                started_at=user_started,
                error=str(exc),
                uid=uid,
            )
            return

        if not senders:
            log.info("[%s] no priorityWatchSenders configured; skipping", uid)
            report_run(
                "watcher", "ok",
                started_at=user_started, email_count=0, uid=uid,
            )
            return

        seen_ids = load_user_state(db, uid)
        seen = set(seen_ids)

        emails = fetch_new_emails(creds, senders, lookback)
        log.info("[%s] matching emails: %d", uid, len(emails))

        new_emails = [e for e in emails if e["id"] not in seen]
        new_count = len(new_emails)
        log.info("[%s] new (not yet processed): %d", uid, new_count)

        if not new_emails:
            report_run(
                "watcher", "ok",
                started_at=user_started, email_count=0, uid=uid,
            )
            return

        user_pdf_dir = OUTPUT_DIR / uid
        user_pdf_dir.mkdir(parents=True, exist_ok=True)

        for email in new_emails:
            try:
                send_alert(
                    uid,
                    f"📬 New from {email['from']}\n{email['subject']}",
                )

                log.info("[%s] summarizing: %s", uid, email["subject"][:60])
                summary = summarize_email(llm_client, email)

                run_at = datetime.now()
                pdf_name = (
                    run_at.strftime("%Y-%m-%d-%H%M%S")
                    + "-" + _sender_slug(email["from"]) + ".pdf"
                )
                subject_slug = _subject_slug(email["subject"])
                subject_dir = user_pdf_dir / subject_slug
                subject_dir.mkdir(parents=True, exist_ok=True)
                pdf_path = subject_dir / pdf_name
                build_pdf(email, summary, pdf_path)
                write_sidecar(pdf_path, email, summary)
                update_subject_summary(subject_dir)
                log.info("[%s] PDF saved: %s", uid, pdf_path)
                outputs.append(pdf_name)

                pdf_count = len(list(subject_dir.glob("*.pdf")))
                has_csv = (subject_dir / SUMMARY_FILENAME).exists()
                upsert_folder_item(
                    firestore_client(),
                    uid,
                    subject=email["subject"],
                    subject_slug=subject_slug,
                    folder_path=str(subject_dir),
                    item_id=pdf_path.stem,
                    item={
                        "from": email.get("from", ""),
                        "date": email.get("date", ""),
                        "urgency": (summary.get("urgency") or "low"),
                        "key_points": summary.get("key_points") or [],
                        "asks": summary.get("asks") or [],
                        "suggested_response": summary.get("suggested_response") or "",
                        "pdf_filename": pdf_path.name,
                    },
                    pdf_count=pdf_count,
                    has_csv=has_csv,
                )

                urg = (summary.get("urgency") or "low").upper()
                caption = f"{email['subject']}\nUrgency: {urg}"
                send_document(uid, pdf_path, caption)

                seen_ids.append(email["id"])
                seen.add(email["id"])
            except Exception as e:  # noqa: BLE001 - per-email isolation
                log.exception(
                    "[%s] failed processing %s: %s", uid, email["id"], e
                )
                # Don't add to seen — retry next run.

        save_user_state(db, uid, seen_ids)
        log.info("[%s] state saved (%d ids)", uid, len(seen_ids[-MAX_PROCESSED:]))
        report_run(
            "watcher",
            "ok",
            started_at=user_started,
            email_count=new_count,
            outputs=outputs,
            uid=uid,
        )
    except Exception:  # noqa: BLE001 - per-user isolation
        log.exception("[%s] watcher iteration crashed", uid)
        report_run(
            "watcher",
            "error",
            started_at=user_started,
            email_count=new_count,
            outputs=outputs,
            error=traceback.format_exc(),
            uid=uid,
        )


def main():
    log.info("=" * 60)
    log.info("Watcher run starting (multi-tenant)")

    if not GOOGLE_OAUTH_WEB_CLIENT_ID or not GOOGLE_OAUTH_WEB_CLIENT_SECRET:
        log.error(
            "GOOGLE_OAUTH_WEB_CLIENT_ID/GOOGLE_OAUTH_WEB_CLIENT_SECRET not "
            "set; aborting"
        )
        return

    try:
        db = firestore_client()
    except (FileNotFoundError, OSError) as exc:
        log.error("Firestore client init failed: %s", exc)
        return

    try:
        uids = enumerate_linked_users(db)
    except Exception:  # noqa: BLE001 - top-level enumeration guard
        log.exception("Failed to enumerate users")
        return

    log.info("enumerated %d users with gmail set: %s", len(uids), uids)
    if not uids:
        return

    llm_client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama-local")

    for uid in uids:
        process_user(db, uid, llm_client)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - top-level launchd guard:
        # log + re-raise so the LaunchAgent records a non-zero exit.
        log.exception("Watcher run failed")
        raise
