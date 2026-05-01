#!/usr/bin/env python3
"""Phase 4 backfill — embed existing lead summaries into the RAG store.

Walks all linked Quick-Link users, iterates each user's leads, and writes one
embedding per lead (keyed by `lead-{lead_id}`) using `lastSummaryResponse` as
the text. Idempotent: re-running skips leads whose embedding already matches
the current EMBEDDING_VERSION.

Why one-per-lead (not one-per-message): Firestore stores leads as
thread-aggregates (sender|subject), so only the latest summary is available
to the backfill. Phase 2 indexes one-per-message going forward — backfill
only covers the historical residue.

Usage:
  python3 backfill_embeddings.py --dry-run              # report counts only
  python3 backfill_embeddings.py --uid <uid>            # one user
  python3 backfill_embeddings.py                        # all linked users
  python3 backfill_embeddings.py --rate 4               # max embed/s (default)
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

from embeddings import EMBEDDING_VERSION, build_rag_text, embed_text  # noqa: E402
from firestore_activity import get_db  # noqa: E402
from firestore_embeddings import upsert_embedding  # noqa: E402
from firestore_users import enumerate_linked_users  # noqa: E402

log = logging.getLogger("backfill")


def _embedding_doc_id(lead_id: str) -> str:
    return f"lead-{lead_id}"


def _embedding_already_indexed(db, uid: str, doc_id: str) -> bool:
    ref = db.collection("users").document(uid).collection("embeddings").document(doc_id)
    snap = ref.get()
    if not snap.exists:
        return False
    d = snap.to_dict() or {}
    return d.get("embeddingVersion") == EMBEDDING_VERSION


def _iter_user_leads(db, uid: str):
    coll = db.collection("users").document(uid).collection("leads")
    for snap in coll.stream():
        d = snap.to_dict() or {}
        d["leadId"] = snap.id
        yield d


def backfill_user(
    db, uid: str, *, dry_run: bool, force: bool, rate_per_sec: float
) -> dict[str, int]:
    counts = {
        "total": 0,
        "skipped_no_summary": 0,
        "skipped_indexed": 0,
        "embedded": 0,
        "errors": 0,
    }
    sleep_between = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0

    for lead in _iter_user_leads(db, uid):
        counts["total"] += 1
        lead_id = lead["leadId"]
        slug = lead.get("subjectSlug", "")
        summary = (lead.get("lastSummaryResponse") or "").strip()
        if not summary or not slug:
            counts["skipped_no_summary"] += 1
            continue

        doc_id = _embedding_doc_id(lead_id)
        if not force and _embedding_already_indexed(db, uid, doc_id):
            counts["skipped_indexed"] += 1
            continue

        if dry_run:
            counts["embedded"] += 1
            continue

        subject = lead.get("subject", "")
        sender_name = lead.get("senderName", "")
        text = build_rag_text(
            subject=subject,
            sender_name=sender_name,
            context=lead.get("lastContext") or [],
            key_points=lead.get("lastKeyPoints") or [],
            asks=lead.get("lastAsks") or [],
            suggested_response=summary,
        )
        try:
            vec = embed_text(text)
            upsert_embedding(
                db,
                uid,
                subject_slug=slug,
                lead_id=lead_id,
                message_id=doc_id,
                text=text,
                vector=vec,
                subject=subject,
                sender_name=sender_name,
            )
            counts["embedded"] += 1
            log.info("[%s] embedded lead=%s slug=%s", uid, lead_id, slug)
        except Exception as exc:  # noqa: BLE001 - log and continue per lead
            counts["errors"] += 1
            log.warning("[%s] embed failed lead=%s: %s", uid, lead_id, exc)

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
        help="Report counts only; no writes.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-embed even if a v-matching embedding already exists.",
    )
    p.add_argument(
        "--uid",
        default="",
        help="Limit to one uid. If omitted, process all linked users.",
    )
    p.add_argument(
        "--rate",
        type=float,
        default=4.0,
        help="Max embed calls per second (default 4).",
    )
    args = p.parse_args()

    db = get_db()
    uids = [args.uid] if args.uid else enumerate_linked_users(db)
    if not uids:
        log.error("no linked users found")
        return 2

    grand = {
        "total": 0,
        "skipped_no_summary": 0,
        "skipped_indexed": 0,
        "embedded": 0,
        "errors": 0,
    }
    for uid in uids:
        log.info("---- uid=%s ----", uid)
        c = backfill_user(
            db,
            uid,
            dry_run=args.dry_run,
            force=args.force,
            rate_per_sec=args.rate,
        )
        log.info("[%s] %s", uid, c)
        for k, v in c.items():
            grand[k] += v

    log.info("==== grand total ====")
    log.info("%s", grand)
    if args.dry_run:
        log.info("dry-run: would have embedded %d leads", grand["embedded"])
    return 0 if grand["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
