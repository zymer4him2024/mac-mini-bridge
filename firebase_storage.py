"""Mirror per-user PDF and summary CSV artifacts into Firebase Storage.

The watcher writes PDFs + sidecars to disk on the host. Firestore mirrors the
metadata so the portal can list folders, but the binary artifacts themselves
live only on the host. This module pushes those binaries to Firebase Storage
under `users/{uid}/folders/{slug}/...` so the portal can render download links
without exposing the host filesystem.

Layout:
  users/{uid}/folders/{subject-slug}/{filename}.pdf
  users/{uid}/folders/{subject-slug}/_summary.csv

Failures here never crash the caller — the on-disk pipeline is the source of
truth for delivery; the cloud copy is best-effort and the UI degrades to
"download unavailable" when the storage path is missing on the Firestore doc.

Bucket name comes from `EMAIL2PPT_STORAGE_BUCKET` env (defaults to the same
value the portal uses: `simpleios01.firebasestorage.app`).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from google.api_core import exceptions as gax
from google.auth import exceptions as gauth_exc
from google.cloud import storage as gcs
from google.cloud.exceptions import GoogleCloudError
from google.oauth2 import service_account

DEFAULT_BUCKET = "simpleios01.firebasestorage.app"
_SA_PATH = Path(__file__).parent / "firebase-service-account.json"

log = logging.getLogger("firebase_storage")

_client: gcs.Client | None = None


def _bucket_name() -> str:
    return os.environ.get("EMAIL2PPT_STORAGE_BUCKET", DEFAULT_BUCKET)


def _get_client() -> gcs.Client | None:
    """Reuse a single GCS client across uploads.

    `firebase-admin` and `google.cloud.storage` resolve credentials
    independently, so we load the service-account file explicitly here. If
    the file is missing we return None — uploads degrade to a warning rather
    than crashing the per-email pipeline.
    """
    global _client
    if _client is None:
        if not _SA_PATH.exists():
            log.warning("firebase-service-account.json missing at %s; uploads disabled", _SA_PATH)
            return None
        try:
            creds = service_account.Credentials.from_service_account_file(str(_SA_PATH))
            _client = gcs.Client(credentials=creds, project=creds.project_id)
        except (OSError, ValueError, gauth_exc.GoogleAuthError) as exc:
            log.warning("GCS client init failed: %s; uploads disabled", exc)
            return None
    return _client


def _object_path(uid: str, slug: str, filename: str) -> str:
    return f"users/{uid}/folders/{slug}/{filename}"


def upload_pdf(uid: str, subject_slug: str, pdf_path: Path) -> str | None:
    """Upload a single PDF. Returns the object path on success, else None."""
    if not uid or not subject_slug:
        return None
    if not pdf_path.exists():
        log.warning("upload_pdf: missing file %s", pdf_path)
        return None

    client = _get_client()
    if client is None:
        return None

    object_path = _object_path(uid, subject_slug, pdf_path.name)
    try:
        bucket = client.bucket(_bucket_name())
        blob = bucket.blob(object_path)
        blob.upload_from_filename(str(pdf_path), content_type="application/pdf")
        return object_path
    except (gax.GoogleAPIError, GoogleCloudError, gauth_exc.GoogleAuthError, OSError) as exc:
        log.warning(
            "pdf upload failed (uid=%s slug=%s file=%s): %s",
            uid, subject_slug, pdf_path.name, exc,
        )
        return None


def upload_summary_csv(uid: str, subject_slug: str, csv_path: Path) -> str | None:
    """Upload the per-folder _summary.csv. Returns object path or None."""
    if not uid or not subject_slug:
        return None
    if not csv_path.exists():
        return None

    client = _get_client()
    if client is None:
        return None

    object_path = _object_path(uid, subject_slug, csv_path.name)
    try:
        bucket = client.bucket(_bucket_name())
        blob = bucket.blob(object_path)
        blob.upload_from_filename(str(csv_path), content_type="text/csv")
        return object_path
    except (gax.GoogleAPIError, GoogleCloudError, gauth_exc.GoogleAuthError, OSError) as exc:
        log.warning(
            "csv upload failed (uid=%s slug=%s): %s", uid, subject_slug, exc,
        )
        return None


def delete_user_blobs(uid: str) -> tuple[int, int]:
    """Delete every blob under users/{uid}/folders/. Used by GDPR cleanup.

    Returns (objects_deleted, bytes_freed).
    """
    if not uid:
        return (0, 0)
    client = _get_client()
    if client is None:
        return (0, 0)
    prefix = f"users/{uid}/folders/"
    deleted = 0
    bytes_freed = 0
    try:
        bucket = client.bucket(_bucket_name())
        for blob in bucket.list_blobs(prefix=prefix):
            try:
                size = blob.size or 0
                blob.delete()
                deleted += 1
                bytes_freed += size
            except (gax.GoogleAPIError, GoogleCloudError) as exc:
                log.warning("blob delete failed (%s): %s", blob.name, exc)
    except (gax.GoogleAPIError, GoogleCloudError, gauth_exc.GoogleAuthError) as exc:
        log.warning("list_blobs failed for uid=%s: %s", uid, exc)
    return (deleted, bytes_freed)


def delete_old_user_blobs(uid: str, cutoff_ts: float) -> tuple[int, int]:
    """Delete blobs whose updated time is older than cutoff_ts (epoch seconds).

    Used by retention_sweep so cloud copies follow the same retention boundary
    as the on-disk artifacts. Returns (objects_deleted, bytes_freed).
    """
    if not uid:
        return (0, 0)
    client = _get_client()
    if client is None:
        return (0, 0)
    prefix = f"users/{uid}/folders/"
    deleted = 0
    bytes_freed = 0
    try:
        bucket = client.bucket(_bucket_name())
        for blob in bucket.list_blobs(prefix=prefix):
            try:
                # blob.updated is timezone-aware UTC datetime
                if blob.updated is None:
                    continue
                if blob.updated.timestamp() >= cutoff_ts:
                    continue
                size = blob.size or 0
                blob.delete()
                deleted += 1
                bytes_freed += size
            except (gax.GoogleAPIError, GoogleCloudError) as exc:
                log.warning("blob delete failed (%s): %s", blob.name, exc)
    except (gax.GoogleAPIError, GoogleCloudError, gauth_exc.GoogleAuthError) as exc:
        log.warning("list_blobs failed for uid=%s: %s", uid, exc)
    return (deleted, bytes_freed)
