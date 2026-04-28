"""Mirror watcher's per-subject folder/sidecar data into Firestore.

The watcher writes PDFs + JSON sidecars to disk on the Mac Mini. The portal
can't reach that filesystem, so this module replicates the same data into
Firestore as the source of truth for the portal's Folders pages:

  users/{uid}/folders/{subject-slug}            (folder metadata)
  users/{uid}/folders/{subject-slug}/items/{id} (per-PDF row, mirrors sidecar)

Failures here never crash the caller — the local PDF/CSV pipeline is the
source of truth for delivery; the portal index is best-effort.
"""

from __future__ import annotations

import logging
from typing import Any

from google.api_core import exceptions as gax
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

log = logging.getLogger("firestore_folders")


def upsert_folder_item(
    db,
    uid: str,
    *,
    subject: str,
    subject_slug: str,
    folder_path: str,
    item_id: str,
    item: dict[str, Any],
    pdf_count: int,
    has_csv: bool,
) -> None:
    """Write one item doc and update the parent folder doc. Never raises.

    `item` mirrors the on-disk JSON sidecar payload (from, date, urgency,
    key_points, asks, suggested_response, pdf_filename).
    """
    if not uid:
        log.warning("upsert_folder_item skipped: empty uid")
        return

    try:
        folder_ref = (
            db.collection("users")
            .document(uid)
            .collection("folders")
            .document(subject_slug)
        )
        folder_ref.set(
            {
                "subject": subject or "(no subject)",
                "subjectSlug": subject_slug,
                "folderPath": folder_path,
                "pdfCount": int(pdf_count),
                "hasSummaryCsv": bool(has_csv),
                "updatedAt": SERVER_TIMESTAMP,
                "createdAt": SERVER_TIMESTAMP,
            },
            merge=True,
        )

        folder_ref.collection("items").document(item_id).set(
            {
                "date": item.get("date", ""),
                "from": item.get("from", ""),
                "urgency": item.get("urgency", "low"),
                "keyPoints": list(item.get("key_points") or []),
                "asks": list(item.get("asks") or []),
                "suggestedResponse": item.get("suggested_response", ""),
                "pdfFilename": item.get("pdf_filename", ""),
                "createdAt": SERVER_TIMESTAMP,
            },
            merge=True,
        )
    except gax.GoogleAPIError as exc:
        log.warning(
            "folder index write failed (uid=%s slug=%s): %s",
            uid, subject_slug, exc,
        )
    except Exception as exc:  # noqa: BLE001 - best-effort mirror
        log.warning(
            "folder index unexpected error (uid=%s slug=%s): %s",
            uid, subject_slug, exc,
        )
