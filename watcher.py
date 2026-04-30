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

from embeddings import build_rag_text, embed_text  # noqa: E402
from firestore_activity import get_db, report_run  # noqa: E402
from firestore_alerts import send_document  # noqa: E402
from firestore_embeddings import upsert_embedding  # noqa: E402
from firestore_folders import upsert_folder_item  # noqa: E402
from firebase_storage import upload_pdf, upload_summary_csv  # noqa: E402
from firestore_leads import compute_lead_id, upsert_lead  # noqa: E402
from mime_extract import extract_body, decode_header_value  # noqa: E402
from lang_hint import detect_dominant_script, language_directive  # noqa: E402
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
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # noqa: E402
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
        body = extract_body(payload)[:8000]
        emails.append(
            {
                "id": m["id"],
                "from": decode_header_value(headers.get("From", "")),
                "subject": decode_header_value(headers.get("Subject", "")) or "(no subject)",
                "date": headers.get("Date", ""),
                "body": body,
            }
        )
    return emails


# ---------- LLM summarization ----------
DEFAULT_PERSONA_LINE = "You are an executive assistant summarizing emails for the recipient."

EMAIL_USER_TEMPLATE = """Summarize the email below into structured JSON ONLY (no prose, no markdown fences).

Required JSON shape:
{{
  "context": [1-2 short strings describing who the sender is and why they are writing],
  "key_points": [up to {kp_max} short strings, each one specific fact, claim, request, number, or quote from the email],
  "asks": [up to {asks_max} short strings describing what the sender wants from the recipient; if no action is requested, return a single string stating that],
  "suggested_response": "one short string describing what to do next, or that no reply is needed",
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


def _build_system_message(cfg: dict) -> str:
    extra = (cfg.get("summaryPersona") or "").strip()
    if extra:
        return f"{DEFAULT_PERSONA_LINE}\n\nAdditional instructions: {extra}"
    return DEFAULT_PERSONA_LINE


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
    system_msg = _build_system_message(cfg)
    user_msg = EMAIL_USER_TEMPLATE.format(
        kp_max=cfg.get("summaryKeyPointsMax", 6),
        asks_max=cfg.get("summaryAsksMax", 4),
        from_=email["from"],
        subject=email["subject"],
        date=email["date"],
        body=email["body"],
    )
    directive = language_directive(detect_dominant_script(email["body"]))
    if directive:
        user_msg = f"{user_msg}\n\n{directive}"
    resp = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
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

# ReportLab's default Helvetica/Times faces have no CJK glyphs, so a Korean
# email previously rendered as boxes. Register the bundled Adobe CID fonts
# at first PDF build and choose one based on the email's dominant script.
_CJK_FONTS_REGISTERED = False
_SCRIPT_TO_PDF_FONT = {
    "korean": "HYSMyeongJo-Medium",
    "japanese": "HeiseiKakuGo-W5",
    "chinese": "STSong-Light",
}


def _ensure_cjk_fonts() -> None:
    global _CJK_FONTS_REGISTERED
    if _CJK_FONTS_REGISTERED:
        return
    try:
        for face in _SCRIPT_TO_PDF_FONT.values():
            pdfmetrics.registerFont(UnicodeCIDFont(face))
            # CID fonts ship single-weight; map <b>/<i> back to the same face
            # so Paragraph's <b>...</b> doesn't warn about a missing variant.
            pdfmetrics.registerFontFamily(
                face, normal=face, bold=face, italic=face, boldItalic=face,
            )
        _CJK_FONTS_REGISTERED = True
    except Exception as exc:  # noqa: BLE001 - PDF still builds in Latin
        log.warning(
            "CJK font registration failed: %s — CJK glyphs will render as boxes",
            exc,
        )


def _pick_pdf_font(email: dict, summary: dict) -> str | None:
    """CJK font name when content is dominantly CJK; None for Latin/unknown."""
    parts = [
        email.get("subject") or "",
        email.get("body") or "",
        " ".join(str(x) for x in (summary.get("key_points") or [])),
        " ".join(str(x) for x in (summary.get("asks") or [])),
        summary.get("suggested_response") or "",
    ]
    return _SCRIPT_TO_PDF_FONT.get(detect_dominant_script(" ".join(parts)))


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(email: dict, summary: dict, out_path: Path):
    _ensure_cjk_fonts()
    cjk_font = _pick_pdf_font(email, summary)

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    h1_kwargs = {"parent": styles["Heading1"], "fontSize": 20, "spaceAfter": 6}
    h2_kwargs = {"parent": styles["Heading2"], "fontSize": 14, "spaceAfter": 4, "spaceBefore": 10}
    if cjk_font:
        h1_kwargs["fontName"] = cjk_font
        h2_kwargs["fontName"] = cjk_font
        body_style = ParagraphStyle("body", parent=styles["BodyText"], fontName=cjk_font)
    else:
        body_style = styles["BodyText"]
    h1 = ParagraphStyle("h1", **h1_kwargs)
    h2 = ParagraphStyle("h2", **h2_kwargs)
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

_URGENCY_EMOJI = {"high": "⚡", "med": "🔸", "low": "▫️"}


def _compose_telegram_msg(email: dict, summary: dict) -> str:
    """Build the single per-email Telegram caption (sent with the PDF attached).

    Layout (kept short — Telegram caps sendDocument captions at 1024 chars):
        📬 {sender display name}
        {subject}

        • {first key point}
        • {suggested next action}

        ⚡ HIGH
    """
    name, addr = parseaddr(email.get("from", ""))
    sender = (name.strip() or addr or email.get("from", "")).strip() or "Unknown"
    subject = (email.get("subject") or "(no subject)").strip()

    bullets: list[str] = []
    key_points = summary.get("key_points") or []
    if key_points:
        first = str(key_points[0]).strip()
        if first:
            bullets.append(f"• {first}")
    sr = (summary.get("suggested_response") or "").strip()
    if sr:
        bullets.append(f"• {sr}")

    urg = (summary.get("urgency") or "low").lower()
    urg_emoji = _URGENCY_EMOJI.get(urg, "▫️")
    urg_label = urg.upper()

    parts = [f"📬 {sender}", subject]
    if bullets:
        parts.append("")
        parts.extend(bullets)
    parts.append("")
    parts.append(f"{urg_emoji} {urg_label}")
    return "\n".join(parts)


def _subject_slug(subject: str) -> str:
    s = subject or ""
    while _REPLY_PREFIX.match(s):
        s = _REPLY_PREFIX.sub("", s, count=1)
    # Strip filesystem-unsafe chars only; preserve Unicode (Hangul / kana /
    # CJK ideographs) so each subject lands in its own readable folder.
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", s)
    s = re.sub(r"\s+", "-", s.strip()).strip("-.").lower()
    s = s[:80]
    # Cap UTF-8 bytes for worst-case 4-byte CJK so the directory name stays
    # under the 255-byte filesystem limit. Decode-with-ignore prevents a
    # truncated multibyte sequence from being kept as half a codepoint.
    if len(s.encode("utf-8")) > 200:
        s = s.encode("utf-8")[:200].decode("utf-8", errors="ignore")
    return s or "no-subject"


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

        # PDFs are stored under the user's Gmail address (when linked) so
        # operators browsing the host filesystem can tell whose folder is
        # whose. Falls back to the opaque uid when no email is on file.
        # A `.uid` marker is written inside so retention / GDPR cleanup can
        # map an email-named directory back to the uid it belongs to.
        user_pdf_dir = OUTPUT_DIR / (self_email or uid)
        user_pdf_dir.mkdir(parents=True, exist_ok=True)
        try:
            (user_pdf_dir / ".uid").write_text(uid)
        except OSError:  # marker is best-effort; cleanup degrades to legacy path
            log.warning("[%s] failed to write .uid marker in %s", uid, user_pdf_dir)

        for email in new_emails:
            try:
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

                pdf_storage_path = upload_pdf(uid, subject_slug, pdf_path)
                summary_csv_storage_path = (
                    upload_summary_csv(uid, subject_slug, subject_dir / SUMMARY_FILENAME)
                    if has_csv
                    else None
                )

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
                    pdf_storage_path=pdf_storage_path,
                    summary_csv_storage_path=summary_csv_storage_path,
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
                    context=summary.get("context") or [],
                    key_points=summary.get("key_points") or [],
                    asks=summary.get("asks") or [],
                )

                # Best-effort RAG index. The wide except is intentional: a
                # failure here (Ollama down, Firestore VS hiccup, malformed
                # embedding) must never block alert/digest/PDF delivery.
                rag_text = build_rag_text(
                    subject=email["subject"],
                    sender_name=sender_name,
                    context=summary.get("context") or [],
                    key_points=summary.get("key_points") or [],
                    asks=summary.get("asks") or [],
                    suggested_response=summary.get("suggested_response") or "",
                )
                if rag_text.strip():
                    try:
                        lead_id = compute_lead_id(sender_email, subject_slug)
                        vec = embed_text(rag_text)
                        upsert_embedding(
                            get_db(),
                            uid,
                            subject_slug=subject_slug,
                            lead_id=lead_id,
                            message_id=email["id"],
                            text=rag_text,
                            vector=vec,
                            subject=email["subject"],
                            sender_name=sender_name,
                        )
                    except Exception:  # noqa: BLE001 - best-effort RAG hook
                        log.warning(
                            "[%s] RAG index failed for msg=%s; alert path unaffected",
                            uid, email["id"], exc_info=True,
                        )

                msg = _compose_telegram_msg(email, summary)
                # Mark seen only after Telegram confirms delivery; on failure
                # the email gets re-processed next tick (idempotent: PDF +
                # Firestore upserts overwrite). Costs one repeat LLM call.
                alert_ok = send_document(uid, pdf_path, msg)
                if alert_ok:
                    seen_ids.append(email["id"])
                    seen.add(email["id"])
                    try:
                        save_user_state(db, uid, seen_ids)
                    except Exception:  # noqa: BLE001 - best-effort persist
                        log.exception(
                            "[%s] state save failed for %s",
                            uid, email["id"],
                        )
                else:
                    log.warning(
                        "[%s] alert not delivered for %s; will retry next tick",
                        uid, email["id"],
                    )
            except Exception as e:  # noqa: BLE001 - per-email isolation
                log.exception(
                    "[%s] failed processing %s: %s", uid, email["id"], e
                )

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
