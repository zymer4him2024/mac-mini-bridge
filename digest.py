#!/usr/bin/env python3
"""
Daily email digest (multi-tenant).

For every user with gmail.email set in Firestore:
  1. Build credentials from users/{uid}/secrets/gmail.refreshToken.
  2. Search Gmail for emails from priority senders in the last 24 hours.
  3. Summarize them with the local Ollama model.
  4. Save a Markdown file to ~/email-digests/{uid}/YYYY-MM-DD-morning.md.
  5. Send a compact version to the user's Telegram chat.

Designed to be run by launchd at 7:00 AM daily.
"""

import os
import base64
import logging
import traceback
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

# ---------- Config ----------
BASE_DIR = Path(__file__).parent.resolve()
DIGEST_DIR = Path.home() / "email-digests"

# Load .env BEFORE importing firestore_* — those modules and firestore_users
# capture env vars at import time. See watcher.py for the same pattern.
load_dotenv(BASE_DIR / ".env")

from firestore_activity import get_db, report_run  # noqa: E402
from firestore_alerts import send_alert  # noqa: E402
from firestore_users import (  # noqa: E402
    enumerate_linked_users,
    load_user_config,
    load_user_credentials,
)

from openai import OpenAI  # noqa: E402
from google.auth.exceptions import RefreshError  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
ADMIN_USER_UID = os.environ.get("ADMIN_USER_UID", "").strip()

DIGEST_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = BASE_DIR / "digest.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("digest")
from log_redaction import install_redaction_filter  # noqa: E402
install_redaction_filter(logging.getLogger())


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


def fetch_priority_emails(creds, senders: list, lookback: str) -> list:
    """Fetch emails from priority senders within the per-user lookback window."""
    service = build("gmail", "v1", credentials=creds)

    # Build OR query — Gmail search syntax: (from:a OR from:b) newer_than:1d
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


# ---------- LLM summarization ----------
def summarize_emails(emails: list, display_name: str = "") -> tuple:
    """Returns (telegram_short_version, full_markdown_for_file)."""
    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama-local")

    persona = f"{display_name}'s executive assistant" if display_name else "an executive assistant"
    user_ref = display_name if display_name else "the user"

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

    full_prompt = f"""You are {persona}. Summarize the following {len(emails)} priority emails {user_ref} received in the last 24 hours.

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
  - What they explicitly want from {user_ref} (or "FYI only - no action")
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
def save_markdown(uid: str, full_markdown: str, run_at: datetime, email_count: int) -> Path:
    filename = run_at.strftime("%Y-%m-%d") + "-morning.md"
    user_dir = DIGEST_DIR / uid
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / filename
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
# Routes via firestore_alerts: customerBot first, else Quick-Link, else drop.
def send_telegram(uid: str, text: str):
    for i in range(0, len(text), 4000):
        send_alert(uid, text[i : i + 4000])


# ---------- Per-user pipeline ----------
def run_digest_for_user(db, uid: str, run_at: datetime, started: datetime) -> None:
    outputs: list[str] = []
    email_count = 0
    try:
        cfg = load_user_config(db, uid)
        if not cfg["digestEnabled"]:
            log.info("uid=%s digestEnabled=false; skipping", uid)
            report_run(
                "digest",
                "ok",
                started_at=started,
                email_count=0,
                outputs=["disabled"],
                uid=uid,
            )
            return

        senders = cfg["senders"]
        lookback = cfg["lookback"]
        log.info("uid=%s senders=%d lookback=%s", uid, len(senders), lookback)
        if not senders:
            log.info("uid=%s no priorityWatchSenders configured; skipping", uid)
            send_telegram(
                uid,
                "📭 Daily digest skipped — no priority senders configured.\n"
                "Add senders in your portal Settings.",
            )
            report_run(
                "digest",
                "ok",
                started_at=started,
                email_count=0,
                uid=uid,
            )
            return

        creds = load_user_credentials(db, uid)
        emails = fetch_priority_emails(creds, senders, lookback)
        email_count = len(emails)
        log.info("uid=%s matching emails in last %s: %d", uid, lookback, email_count)

        if not emails:
            no_email_md = (
                f"## No priority emails today\n\n"
                f"No emails received from your {len(senders)} priority senders "
                f"in the last {lookback}. Quiet morning.\n"
            )
            md_path = save_markdown(uid, no_email_md, run_at, 0)
            outputs.append(str(md_path.relative_to(DIGEST_DIR)))
            send_telegram(
                uid,
                f"📭 Daily digest — {run_at.strftime('%a %b %d')}\n"
                f"No priority emails in the last {lookback}.",
            )
            report_run(
                "digest",
                "ok",
                started_at=started,
                email_count=0,
                outputs=outputs,
                uid=uid,
            )
            return

        short, full = summarize_emails(emails, cfg.get("displayName", ""))
        md_path = save_markdown(uid, full, run_at, len(emails))
        log.info("uid=%s saved digest to %s", uid, md_path)
        outputs.append(str(md_path.relative_to(DIGEST_DIR)))

        telegram_msg = (
            f"📬 Daily Digest — {run_at.strftime('%a %b %d')}\n"
            f"{len(emails)} priority emails · saved to {md_path.name}\n"
            f"\n"
            f"{short}"
        )
        send_telegram(uid, telegram_msg)
        log.info("uid=%s digest sent to Telegram", uid)
        report_run(
            "digest",
            "ok",
            started_at=started,
            email_count=email_count,
            outputs=outputs,
            uid=uid,
        )
    except RefreshError as exc:
        log.warning("uid=%s refresh failed: %s", uid, exc)
        report_run(
            "digest",
            "error",
            started_at=started,
            email_count=email_count,
            outputs=outputs,
            error=f"RefreshError: {exc}",
            uid=uid,
        )
    except Exception:  # noqa: BLE001 - per-user isolation: one user's
        # failure must not abort the digest loop for other tenants.
        log.exception("uid=%s digest failed", uid)
        report_run(
            "digest",
            "error",
            started_at=started,
            email_count=email_count,
            outputs=outputs,
            error=traceback.format_exc(),
            uid=uid,
        )


# ---------- Main ----------
def main():
    started = datetime.now(timezone.utc)
    run_at = datetime.now()
    log.info("=" * 60)
    log.info("Starting daily email digest (multi-tenant)")

    db = get_db()
    uids = enumerate_linked_users(db)
    log.info("enumerated %d users with gmail set: %s", len(uids), uids)
    if not uids:
        return

    for uid in uids:
        run_digest_for_user(db, uid, run_at, started)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - top-level launchd guard:
        # ensure the failure is logged + the admin paged before re-raising.
        log.exception("Digest run failed")
        if ADMIN_USER_UID:
            try:
                # Don't echo the exception text — it can carry tokens or
                # fragments of upstream HTTP responses. The admin reads
                # the log file for the detail.
                send_telegram(
                    ADMIN_USER_UID,
                    f"⚠️ Daily digest run failed. See {LOG_PATH}",
                )
            except (OSError, ValueError):
                log.exception("Failed to deliver fatal-alert to admin")
        raise
