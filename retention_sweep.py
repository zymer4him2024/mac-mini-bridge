#!/usr/bin/env python3
"""Per-user retention sweep for local email artifacts.

Walks ~/email-pdfs/{uid}/ and ~/email-digests/{uid}/ for every linked user
and deletes files whose mtime is older than that user's
`config.retentionDays` (default 30). Empty subdirectories left behind are
removed. The user-root directories themselves are kept so the workers do
not have to recreate them.

Designed to run daily via launchd (`com.shawn.email-retention.plist`).

Lawful basis: GDPR Art. 5(1)(e) — storage limitation. The retention is
configurable per tenant via the portal.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core import exceptions as gax

from firebase_storage import delete_old_user_blobs
from firestore_activity import report_run
from firestore_audit import record_audit
from firestore_embeddings import delete_stale_embeddings
from firestore_users import enumerate_linked_users, load_user_config

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

SERVICE_ACCOUNT = BASE_DIR / "firebase-service-account.json"
FIRESTORE_DB_ID = os.environ.get("FIRESTORE_DATABASE_ID", "email2ppt")

PDF_ROOT = Path.home() / "email-pdfs"
DIGEST_ROOT = Path.home() / "email-digests"


def _find_pdf_user_dirs(uid: str) -> list[Path]:
    """PDF dirs may be email-named (new) or uid-named (legacy). Find both.

    Email-named dirs carry a `.uid` marker file written by the watcher so we
    can map back to the owning uid without consulting Firestore.
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

LOG_PATH = BASE_DIR / "retention_sweep.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("retention_sweep")
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


def _sweep_dir(root: Path, cutoff_ts: float) -> tuple[int, int]:
    """Delete files older than cutoff_ts. Return (files_deleted, bytes_deleted).

    Walks bottom-up so empty directories can be removed in the same pass.
    Symlinks are not followed and not deleted.
    """
    if not root.exists() or not root.is_dir():
        return (0, 0)

    files_deleted = 0
    bytes_deleted = 0

    for dirpath, _dirnames, filenames in os.walk(root, topdown=False, followlinks=False):
        dir_path = Path(dirpath)
        for fname in filenames:
            fpath = dir_path / fname
            try:
                if fpath.is_symlink():
                    continue
                stat = fpath.stat()
                if stat.st_mtime < cutoff_ts:
                    size = stat.st_size
                    fpath.unlink()
                    files_deleted += 1
                    bytes_deleted += size
            except (FileNotFoundError, PermissionError, OSError) as exc:
                log.warning("skipping %s: %s", fpath, exc)
        # Best-effort prune: remove the directory if it ended up empty,
        # but never delete the user-root itself.
        if dir_path != root:
            try:
                dir_path.rmdir()
            except OSError:
                pass

    return (files_deleted, bytes_deleted)


def sweep_user(db, uid: str, retention_days: int) -> dict:
    """Sweep one user's directories. Returns metrics dict for the activity feed."""
    cutoff = time.time() - retention_days * 86400
    cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
    pdf_files = 0
    pdf_bytes = 0
    for pdf_dir in _find_pdf_user_dirs(uid):
        f, b = _sweep_dir(pdf_dir, cutoff)
        pdf_files += f
        pdf_bytes += b
    digest_files, digest_bytes = _sweep_dir(DIGEST_ROOT / uid, cutoff)
    storage_objs, storage_bytes = delete_old_user_blobs(uid, cutoff)
    try:
        embeddings_deleted = delete_stale_embeddings(db, uid, cutoff_dt)
    except gax.GoogleAPIError as exc:
        log.warning("uid=%s stale embeddings delete failed: %s", uid, exc)
        embeddings_deleted = 0
    return {
        "retentionDays": retention_days,
        "cutoffIso": cutoff_dt.isoformat(),
        "pdfsDeleted": pdf_files,
        "pdfBytesDeleted": pdf_bytes,
        "digestsDeleted": digest_files,
        "digestBytesDeleted": digest_bytes,
        "storageObjectsDeleted": storage_objs,
        "storageBytesDeleted": storage_bytes,
        "embeddingsDeleted": embeddings_deleted,
    }


def main() -> None:
    started = datetime.now(timezone.utc)
    db = _client()
    try:
        uids = enumerate_linked_users(db)
    except gax.GoogleAPIError as exc:
        log.warning("Firestore unreachable (%s); skipping run", exc)
        return

    log.info("retention sweep start; users=%d", len(uids))
    summary: list[str] = []

    for uid in uids:
        try:
            cfg = load_user_config(db, uid)
            metrics = sweep_user(db, uid, cfg["retentionDays"])
        except (gax.GoogleAPIError, OSError, ValueError) as exc:
            log.warning("uid=%s sweep failed: %s", uid, exc)
            report_run(
                "retention_sweep",
                "error",
                started_at=started,
                error=traceback.format_exc(),
                uid=uid,
            )
            continue

        line = (
            f"uid={uid} pdfs={metrics['pdfsDeleted']} "
            f"digests={metrics['digestsDeleted']} "
            f"storage={metrics['storageObjectsDeleted']} "
            f"embeddings={metrics['embeddingsDeleted']} "
            f"retention={metrics['retentionDays']}d"
        )
        summary.append(line)
        log.info(line)
        if (
            metrics["pdfsDeleted"]
            or metrics["digestsDeleted"]
            or metrics["storageObjectsDeleted"]
            or metrics["embeddingsDeleted"]
        ):
            report_run(
                "retention_sweep",
                "ok",
                started_at=started,
                outputs=[line],
                uid=uid,
            )
            record_audit(uid, "config_change", "retention_sweep", metrics)

    log.info("retention sweep complete; %s", " | ".join(summary) or "no-op")


if __name__ == "__main__":
    main()
