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
import fcntl
import json
import base64
import logging
import re
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parseaddr

from dotenv import load_dotenv

# ---------- Config ----------
BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = Path.home() / "email-pdfs"
SUMMARY_THRESHOLD = 5
SUMMARY_FILENAME = "_summary.csv"

# Load .env BEFORE importing firestore_alerts — that module captures
# TELEGRAM_BOT_TOKEN / AUTHORIZED_CHAT_ID at import time for the shared-bot
# fallback. Importing it before load_dotenv leaves both as empty strings.
load_dotenv(BASE_DIR / ".env")

from firestore_activity import get_db, report_run  # noqa: E402
from firestore_alerts import send_alert, send_document  # noqa: E402
from firestore_folders import upsert_folder_item  # noqa: E402
from firestore_leads import upsert_lead  # noqa: E402
from firestore_state import (  # noqa: E402
    MAX_PROCESSED,
    load_user_last_run_at,
    load_user_self_email,
    load_user_state,
    save_user_last_run_at,
    save_user_state,
)
from firestore_users import (  # noqa: E402
    GOOGLE_OAUTH_WEB_CLIENT_ID,
    GOOGLE_OAUTH_WEB_CLIENT_SECRET,
    enumerate_linked_users,
    load_user_config,
    load_user_credentials,
)

import httplib2  # noqa: E402
from openai import OpenAI  # noqa: E402
from google.oauth2.credentials import Credentials  # noqa: E402
from google.auth.exceptions import RefreshError  # noqa: E402
from google_auth_httplib2 import AuthorizedHttp  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402

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
from log_redaction import install_redaction_filter  # noqa: E402
install_redaction_filter(logging.getLogger())


# ---------- Gmail helpers ----------
def _extract_body(payload) -> str:
    if not isinstance(payload, dict):
        return ""
    body_data = (payload.get("body") or {}).get("data")
    if body_data:
        return base64.urlsafe_b64decode(body_data).decode(
            "utf-8", errors="replace"
        )
    for part in payload.get("parts") or []:
        part_data = (part.get("body") or {}).get("data")
        if part.get("mimeType") == "text/plain" and part_data:
            return base64.urlsafe_b64decode(part_data).decode(
                "utf-8", errors="replace"
            )
    for part in payload.get("parts") or []:
        text = _extract_body(part)
        if text:
            return text
    return ""


_GMAIL_RETRY_STATUSES = {429, 500, 502, 503, 504}
_GMAIL_RETRY_BACKOFFS = (1, 4)


def _gmail_execute(request, *, label: str):
    """Execute a Gmail API request with bounded retry on transients.

    Retries 429 + 5xx; lets 4xx auth errors propagate. Without this, a
    routine 502 from Gmail silently dropped the whole cycle's email list.
    """
    last_exc: HttpError | None = None
    for attempt in range(3):
        try:
            return request.execute()
        except HttpError as exc:
            status = getattr(exc.resp, "status", 0)
            if status not in _GMAIL_RETRY_STATUSES:
                raise
            last_exc = exc
            log.warning(
                "Gmail %s transient %s (attempt %d/3)",
                label, status, attempt + 1,
            )
        if attempt < len(_GMAIL_RETRY_BACKOFFS):
            time.sleep(_GMAIL_RETRY_BACKOFFS[attempt])
    assert last_exc is not None
    raise last_exc


def fetch_new_emails(creds: Credentials, senders: list, lookback: str) -> list:
    if not senders:
        return []
    # 20s socket timeout on every Gmail HTTP call so a stalled TLS handshake
    # cannot block the watcher cycle indefinitely.
    authed_http = AuthorizedHttp(creds, http=httplib2.Http(timeout=20))
    service = build("gmail", "v1", http=authed_http, cache_discovery=False)
    or_clause = " OR ".join(f"from:{s}" for s in senders)
    query = f"({or_clause}) newer_than:{lookback}"
    log.info(f"Gmail query: {query}")
    result = _gmail_execute(
        service.users().messages().list(userId="me", q=query, maxResults=25),
        label="messages.list",
    )
    messages = result.get("messages", [])
    emails = []
    for m in messages:
        msg = _gmail_execute(
            service.users().messages().get(userId="me", id=m["id"], format="full"),
            label="messages.get",
        )
        payload = msg.get("payload") or {}
        headers = {
            h.get("name", ""): h.get("value", "")
            for h in payload.get("headers") or []
        }
        body = _extract_body(payload)[:8000]
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


# ---------- LLM summarization ----------
DEFAULT_PERSONA_LINE = "You are an executive assistant summarizing emails for the recipient."

EMAIL_PROMPT = """{persona_line} Summarize the email below into structured JSON ONLY (no prose, no markdown fences).

Required JSON shape:
{{{{
  "context": ["1-2 short bullets giving who they are / why writing"],
  "key_points": ["up to {kp_max} bullets of specific facts, claims, requests, numbers, quotes from the email"],
  "asks": ["up to {asks_max} bullets of what they want from the recipient, or one item 'FYI only - no action'"],
  "suggested_response": "one short line e.g. 'Reply Friday', 'No reply needed'",
  "urgency": "low" | "med" | "high"
}}}}

Style:
- Specific over generic. Pull real numbers, names, dates.
- Skip greetings, signatures, quoted-thread history.
- Output ONLY the JSON object.

EMAIL:
From: {{from_}}
Subject: {{subject}}
Date: {{date}}

{{body}}
"""


def _build_email_template(cfg: dict) -> str:
    persona = (cfg.get("summaryPersona") or "").strip()
    persona_line = persona if persona else DEFAULT_PERSONA_LINE
    kp_max = cfg.get("summaryKeyPointsMax", 6)
    asks_max = cfg.get("summaryAsksMax", 4)
    return EMAIL_PROMPT.format(
        persona_line=persona_line,
        kp_max=kp_max,
        asks_max=asks_max,
    )


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


_VALID_URGENCY = {"low", "med", "high"}


def _normalize_summary(data) -> dict:
    """Coerce LLM JSON output into the shape downstream code expects.

    Tolerates the LLM returning wrong types (string instead of list, missing
    keys, extra keys). Without this, a single malformed summary aborts the
    per-email try, so the user gets the Telegram alert but no PDF/folder/lead.
    """
    if not isinstance(data, dict):
        data = {}
    out: dict = {}
    for key in ("context", "key_points", "asks"):
        v = data.get(key)
        out[key] = v if isinstance(v, list) else []
    urg = data.get("urgency")
    out["urgency"] = urg if urg in _VALID_URGENCY else "low"
    sr = data.get("suggested_response")
    out["suggested_response"] = sr if isinstance(sr, str) else ""
    return out


def summarize_email(client: OpenAI, email: dict, cfg: dict) -> dict:
    template = _build_email_template(cfg)
    prompt = template.format(
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
        return _normalize_summary(json.loads(text))
    except json.JSONDecodeError:
        log.warning(f"JSON parse failed for {email['subject']!r}; using fallback")
        return _normalize_summary({
            "context": [],
            "key_points": [text[:400]] if text else [],
            "asks": [],
            "suggested_response": "",
            "urgency": "low",
        })


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
        interval_minutes = cfg["intervalMinutes"]
        log.info(
            "[%s] senders=%d lookback=%s interval=%dm",
            uid, len(senders), lookback, interval_minutes,
        )

        # Per-user cadence gate. The LaunchAgent ticks every 2 min, but each
        # user only actually processes when at least intervalMinutes has
        # elapsed since their last run. First-ever run (no lastRunAt) always
        # proceeds. A 5s grace covers tick jitter so a user who picked
        # "every 5 min" doesn't drift to 7 min on a slightly-late tick.
        last_run_at = load_user_last_run_at(db, uid)
        if last_run_at is not None:
            elapsed = (user_started - last_run_at).total_seconds()
            required = interval_minutes * 60 - 5
            if elapsed < required:
                log.info(
                    "[%s] skipping (last run %.0fs ago, interval=%dm)",
                    uid, elapsed, interval_minutes,
                )
                return

        # Record the run *before* doing the actual work. If the cycle
        # crashes mid-flight (Ollama hang, OOM), the next tick still respects
        # the user's chosen cadence instead of replaying immediately.
        try:
            save_user_last_run_at(db, uid, user_started)
        except Exception:  # noqa: BLE001 - best-effort gate persistence
            log.exception("[%s] save_user_last_run_at failed", uid)

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

        # Suppress emails the user sent themselves. When two portal-linked
        # users share a Telegram chat (one as inbox recipient, the other as
        # sender via Sent folder), both would otherwise fire on the same
        # email. Mark the suppressed ids seen so they don't re-fetch forever.
        self_email = load_user_self_email(db, uid)
        if self_email:
            kept, self_sent = [], []
            for e in new_emails:
                addr = (parseaddr(e.get("from", ""))[1] or "").strip().lower()
                (self_sent if addr == self_email else kept).append(e)
            if self_sent:
                log.info(
                    "[%s] suppressing %d self-sent email(s); marking seen",
                    uid, len(self_sent),
                )
                ids = [e["id"] for e in self_sent]
                seen_ids.extend(ids)
                seen.update(ids)
                try:
                    save_user_state(db, uid, seen_ids)
                except Exception:  # noqa: BLE001 - best-effort; suppression is idempotent
                    log.exception("[%s] save_user_state after self-sent suppression failed", uid)
            new_emails = kept

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
                alert_ok = send_alert(
                    uid,
                    f"📬 New from {email['from']}\n{email['subject']}",
                )
                # Mark as seen the instant Telegram confirms the alert went
                # out. If a SIGTERM / OOM / sleep happens mid-PDF, the user
                # gets at most one duplicate alert next tick instead of the
                # full storm of every already-alerted email.
                if alert_ok:
                    seen_ids.append(email["id"])
                    seen.add(email["id"])
                    try:
                        save_user_state(db, uid, seen_ids)
                    except Exception:  # noqa: BLE001 - best-effort early save
                        log.exception(
                            "[%s] early state save failed for %s",
                            uid, email["id"],
                        )
                else:
                    log.warning(
                        "[%s] alert not delivered for %s; will retry next tick",
                        uid, email["id"],
                    )
                    continue

                log.info("[%s] summarizing: %s", uid, email["subject"][:60])
                summary = summarize_email(llm_client, email, cfg)

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
                    get_db(),
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

                sender_name, sender_email = parseaddr(email.get("from", ""))
                upsert_lead(
                    get_db(),
                    uid,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    subject=email["subject"],
                    subject_slug=subject_slug,
                    urgency=(summary.get("urgency") or "low"),
                    pdf_filename=pdf_path.name,
                    suggested_response=summary.get("suggested_response") or "",
                )

                urg = (summary.get("urgency") or "low").upper()
                caption = f"{email['subject']}\nUrgency: {urg}"
                send_document(uid, pdf_path, caption)
            except Exception as e:  # noqa: BLE001 - per-email isolation
                log.exception(
                    "[%s] failed processing %s: %s", uid, email["id"], e
                )
                # Already in seen_ids from the early save above; the user
                # got the alert, just not the PDF — don't re-alert next tick.

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
    # Inter-process lock: if a previous LaunchAgent tick is still running
    # (e.g. a 25-email Ollama cycle exceeded StartInterval=300), exit cleanly
    # so we don't double-process the same Firestore state.
    lock_fd = open(BASE_DIR / ".watcher.lock", "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.info("previous watcher tick still running; exiting")
        return

    log.info("=" * 60)
    log.info("Watcher run starting (multi-tenant)")

    if not GOOGLE_OAUTH_WEB_CLIENT_ID or not GOOGLE_OAUTH_WEB_CLIENT_SECRET:
        log.error(
            "GOOGLE_OAUTH_WEB_CLIENT_ID/GOOGLE_OAUTH_WEB_CLIENT_SECRET not "
            "set; aborting"
        )
        return

    try:
        db = get_db()
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

    # 90s cap per Ollama call — generous for a laptop, short enough that a
    # stalled summary doesn't pile up across overlapping ticks.
    llm_client = OpenAI(
        base_url=OLLAMA_BASE_URL, api_key="ollama-local", timeout=90,
    )

    for uid in uids:
        process_user(db, uid, llm_client)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - top-level launchd guard:
        # log + re-raise so the LaunchAgent records a non-zero exit.
        log.exception("Watcher run failed")
        raise
