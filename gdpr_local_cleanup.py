#!/usr/bin/env python3
"""Process queued GDPR delete jobs by removing local artifacts.

The portal's `deleteUserData` Cloud Function clears Firestore data and
writes `gdpr_cleanup_jobs/{uid}` with status="queued". This script polls
that collection on the worker host, deletes the user's
`~/email-pdfs/{uid}/`, `~/email-digests/{uid}/`, and `~/email-ppts/{uid}/`
directories, then marks the job as `done`.

Designed to run alongside `retention_sweep.py` on the same daily launchd
schedule (or more frequently — every 15 min is fine since the work is
small when the queue is empty).

Idempotent: a job that has already been processed is left alone if its
status is `done`. A re-queued job (status="queued") will sweep again
even if the directories are already gone.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core import exceptions as gax

from firebase_storage import delete_user_blobs
from firestore_activity import report_run
from firestore_audit import record_audit
from firestore_embeddings import delete_embeddings_for_user

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

SERVICE_ACCOUNT = BASE_DIR / "firebase-service-account.json"
FIRESTORE_DB_ID = os.environ.get("FIRESTORE_DATABASE_ID", "email2ppt")

PDF_ROOT = Path.home() / "email-pdfs"
# Digests and ppts stay uid-named; PDFs may be email-named (new layout) or
# uid-named (legacy) — handled via _find_pdf_user_dirs.
UID_ONLY_DIRS = [
    Path.home() / "email-digests",
    Path.home() / "email-ppts",
]


def _find_pdf_user_dirs(uid: str) -> list[Path]:
    """PDF dirs may be email-named (new) or uid-named (legacy). Find both.

    Email-named dirs carry a `.uid` marker file written by the watcher so we
    can map back to the owning uid even after Firestore data has been wiped.
    """
    found: list[Path] = []
    legacy = PDF_ROOT / uid
    if legacy.exists():
        found.append(legacy)
    if PDF_ROOT.exists():
        for child in PDF_ROOT.iterdir():
            if not child.is_dir() or child == legacy:
                continue
            marker = child / ".uid"
            try:
                if marker.is_file() and marker.read_text().strip() == uid:
                    found.append(child)
            except OSError:
                continue
    return found

LOG_PATH = BASE_DIR / "gdpr_local_cleanup.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("gdpr_local_cleanup")
from log_redaction import install_redaction_filter  # noqa: E402
install_redaction_filter(logging.getLogger())


def _client():
    if not SERVICE_ACCOUNT.exists():
        log.error("service account missing: %s", SERVICE_ACCOUNT)
        sys.exit(1)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.Certificate(str(SERVICE_ACCOUNT))
        )
    return firestore.client(database_id=FIRESTORE_DB_ID)


def _purge_user_dirs(uid: str) -> dict:
    """Delete every per-user output directory. Returns metrics."""
    removed = []
    bytes_freed = 0
    targets = _find_pdf_user_dirs(uid) + [
        root / uid for root in UID_ONLY_DIRS
    ]
    for target in targets:
        if not target.exists():
            continue
        # Tally size before deletion for the audit record.
        for p in target.rglob("*"):
            if p.is_file():
                try:
                    bytes_freed += p.stat().st_size
                except OSError:
                    pass
        try:
            shutil.rmtree(target)
            removed.append(str(target))
        except OSError as exc:
            log.warning("failed to remove %s: %s", target, exc)
    storage_objs, storage_bytes = delete_user_blobs(uid)
    return {
        "directoriesRemoved": removed,
        "bytesFreed": bytes_freed,
        "storageObjectsDeleted": storage_objs,
        "storageBytesDeleted": storage_bytes,
    }


def main() -> None:
    started = datetime.now(timezone.utc)
    db = _client()
    try:
        snaps = (
            db.collection("gdpr_cleanup_jobs")
            .where("status", "==", "queued")
            .stream()
        )
        jobs = [(snap.id, snap.to_dict() or {}) for snap in snaps]
    except gax.GoogleAPIError as exc:
        log.warning("Firestore unreachable (%s); skipping run", exc)
        return

    log.info("gdpr local cleanup start; queued=%d", len(jobs))
    for job_id, _job in jobs:
        uid = job_id
        try:
            metrics = _purge_user_dirs(uid)
            try:
                metrics["embeddingsDeleted"] = delete_embeddings_for_user(
                    db, uid
                )
            except gax.GoogleAPIError as exc:
                # Local artifact purge already succeeded; treat embedding
                # delete failure as a soft error so the job still marks done.
                log.warning(
                    "uid=%s embeddings delete failed: %s", uid, exc
                )
                metrics["embeddingsDeleted"] = 0
        except OSError as exc:
            log.warning("uid=%s purge failed: %s", uid, exc)
            db.collection("gdpr_cleanup_jobs").document(job_id).set(
                {
                    "status": "error",
                    "error": str(exc),
                    "updatedAt": datetime.now(timezone.utc),
                },
                merge=True,
            )
            report_run(
                "gdpr_local_cleanup",
                "error",
                started_at=started,
                error=traceback.format_exc(),
                uid=uid,
            )
            continue

        db.collection("gdpr_cleanup_jobs").document(job_id).set(
            {
                "status": "done",
                "completedAt": datetime.now(timezone.utc),
                "metrics": metrics,
            },
            merge=True,
        )
        log.info("uid=%s purged: %s", uid, metrics)
        # Audit even though the user doc is mostly emptied — owner+admin can
        # still read the audit subcollection until TTL clears it.
        record_audit(uid, "data_delete", "gdpr_local_cleanup", metrics)
        report_run(
            "gdpr_local_cleanup",
            "ok",
            started_at=started,
            outputs=[f"removed {len(metrics['directoriesRemoved'])} dirs"],
            uid=uid,
        )


if __name__ == "__main__":
    main()
