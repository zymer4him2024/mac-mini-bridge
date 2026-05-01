#!/usr/bin/env python3
"""Re-summarize old leads to populate context/key_points/asks/suggested_response.

Leads created before 2026-04-29 only have `lastSummaryResponse` set (a meta
instruction string), so the v2 RAG corpus has nothing factual to ground on.
This script re-fetches each lead's original email from Gmail and runs
`summarize_email()` to produce the rich fields, then writes them back to the
lead doc. Run `backfill_embeddings.py` afterward to rebuild the vector index
from the enriched corpus.

Match strategy: leads store `senderEmail` + cleaned `subject`. We query Gmail
`from:{sender} newer_than:{N}d` and match each candidate's subject (after
running it through `_subject_slug`) against the lead's `subjectSlug`.

Idempotent: skips leads whose `lastKeyPoints` or `lastContext` is already
non-empty. Pass --force to re-summarize regardless.

Usage:
  python3 resummarize_leads.py --dry-run
  python3 resummarize_leads.py --uid <uid>
  python3 resummarize_leads.py --rate 0.5 --lookback-days 365
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

import httplib2  # noqa: E402
from google_auth_httplib2 import AuthorizedHttp  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402
from openai import OpenAI  # noqa: E402

from firestore_activity import get_db  # noqa: E402
from firestore_users import (  # noqa: E402
    enumerate_linked_users,
    load_user_config,
    load_user_credentials,
)
from mime_extract import decode_header_value, extract_body  # noqa: E402
from watcher import (  # noqa: E402
    OLLAMA_BASE_URL,
    _subject_slug,
    summarize_email,
)

log = logging.getLogger("resummarize")


def _is_rich(lead: dict) -> bool:
    return bool(lead.get("lastKeyPoints")) or bool(lead.get("lastContext"))


def _find_email_for_lead(
    service, sender_email: str, target_slug: str, lookback_days: int
) -> dict | None:
    query = f"from:{sender_email} newer_than:{lookback_days}d"
    res = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    for m in res.get("messages") or []:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=m["id"], format="full")
            .execute()
        )
        payload = msg.get("payload") or {}
        headers = {
            h.get("name", ""): h.get("value", "") for h in payload.get("headers") or []
        }
        msg_subject = decode_header_value(headers.get("Subject", "")) or "(no subject)"
        if _subject_slug(msg_subject) != target_slug:
            continue
        return {
            "id": m["id"],
            "from": decode_header_value(headers.get("From", "")),
            "subject": msg_subject,
            "date": headers.get("Date", ""),
            "body": extract_body(payload)[:8000],
        }
    return None


def resummarize_user(
    db,
    uid: str,
    *,
    dry_run: bool,
    force: bool,
    rate_per_sec: float,
    lookback_days: int,
    llm_client: OpenAI,
) -> dict[str, int]:
    counts = {
        "total": 0,
        "skipped_rich": 0,
        "skipped_no_msg": 0,
        "updated": 0,
        "errors": 0,
    }
    sleep_between = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0

    creds = load_user_credentials(db, uid)
    cfg = load_user_config(db, uid)
    authed_http = AuthorizedHttp(creds, http=httplib2.Http(timeout=20))
    service = build("gmail", "v1", http=authed_http, cache_discovery=False)

    leads_ref = db.collection("users").document(uid).collection("leads")
    for snap in leads_ref.stream():
        counts["total"] += 1
        lead = snap.to_dict() or {}
        lead_id = snap.id

        if not force and _is_rich(lead):
            counts["skipped_rich"] += 1
            continue

        sender = (lead.get("senderEmail") or "").strip().lower()
        slug = lead.get("subjectSlug") or ""
        subject = lead.get("subject") or ""
        if not sender or not slug:
            counts["errors"] += 1
            log.warning("[%s] lead=%s missing sender/slug; skipping", uid, lead_id)
            continue

        try:
            email = _find_email_for_lead(service, sender, slug, lookback_days)
        except Exception as exc:  # noqa: BLE001 - log per-lead, continue
            log.warning("[%s] gmail search failed lead=%s: %s", uid, lead_id, exc)
            counts["errors"] += 1
            continue

        if not email:
            log.info(
                "[%s] no gmail match lead=%s subj=%r",
                uid,
                lead_id,
                subject[:60],
            )
            counts["skipped_no_msg"] += 1
            continue

        if dry_run:
            log.info(
                "[%s] would resummarize lead=%s subj=%r",
                uid,
                lead_id,
                subject[:60],
            )
            counts["updated"] += 1
            continue

        try:
            summary = summarize_email(llm_client, email, cfg)
            snap.reference.set(
                {
                    "lastContext": list(summary.get("context") or []),
                    "lastKeyPoints": list(summary.get("key_points") or []),
                    "lastAsks": list(summary.get("asks") or []),
                    "lastSummaryResponse": summary.get("suggested_response") or "",
                    "urgency": summary.get("urgency") or lead.get("urgency", "low"),
                },
                merge=True,
            )
            counts["updated"] += 1
            log.info(
                "[%s] resummarized lead=%s kp=%d asks=%d",
                uid,
                lead_id,
                len(summary.get("key_points") or []),
                len(summary.get("asks") or []),
            )
        except Exception as exc:  # noqa: BLE001 - log per-lead, continue
            log.warning("[%s] resummarize failed lead=%s: %s", uid, lead_id, exc)
            counts["errors"] += 1

        if sleep_between:
            time.sleep(sleep_between)

    return counts


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser()
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts only; no Gmail re-fetch, no writes.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-summarize leads even if lastKeyPoints is already populated.",
    )
    p.add_argument(
        "--uid",
        default="",
        help="Limit to one uid. If omitted, process all linked users.",
    )
    p.add_argument(
        "--rate",
        type=float,
        default=0.5,
        help="Max leads per second (default 0.5 = 1 every 2s).",
    )
    p.add_argument(
        "--lookback-days",
        type=int,
        default=365,
        help="Gmail search window per sender (default 365).",
    )
    args = p.parse_args()

    db = get_db()
    uids = [args.uid] if args.uid else enumerate_linked_users(db)
    if not uids:
        log.error("no linked users found")
        return 2

    llm_client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama-local")

    grand = {
        "total": 0,
        "skipped_rich": 0,
        "skipped_no_msg": 0,
        "updated": 0,
        "errors": 0,
    }
    for uid in uids:
        log.info("---- uid=%s ----", uid)
        c = resummarize_user(
            db,
            uid,
            dry_run=args.dry_run,
            force=args.force,
            rate_per_sec=args.rate,
            lookback_days=args.lookback_days,
            llm_client=llm_client,
        )
        log.info("[%s] %s", uid, c)
        for k, v in c.items():
            grand[k] += v

    log.info("==== grand total ====")
    log.info("%s", grand)
    if args.dry_run:
        log.info("dry-run: would have resummarized %d leads", grand["updated"])
    return 0 if grand["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
