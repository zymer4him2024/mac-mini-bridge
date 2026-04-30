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
    pdf_storage_path: str | None = None,
    summary_csv_storage_path: str | None = None,
) -> None:
    """Write one item doc and update the parent folder doc. Never raises.

    `item` mirrors the on-disk JSON sidecar payload (from, date, urgency,
    key_points, asks, suggested_response, pdf_filename).

    `pdf_storage_path` and `summary_csv_storage_path`, when provided, are the
    Firebase Storage object paths used by the portal to render download links.
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
        folder_doc: dict[str, Any] = {
            "subject": subject or "(no subject)",
            "subjectSlug": subject_slug,
            "folderPath": folder_path,
            "pdfCount": int(pdf_count),
            "hasSummaryCsv": bool(has_csv),
            "updatedAt": SERVER_TIMESTAMP,
            "createdAt": SERVER_TIMESTAMP,
        }
        if summary_csv_storage_path:
            folder_doc["summaryCsvStoragePath"] = summary_csv_storage_path
        folder_ref.set(folder_doc, merge=True)

        item_doc: dict[str, Any] = {
            # Denormalized so a collection-group query on `items` can be
            # filtered by uid (security rules + per-tenant scoping) and the
            # cross-folder feed can render folder context without a parent
            # lookup per row.
            "uid": uid,
            "folderSubject": subject or "(no subject)",
            "folderSlug": subject_slug,
            "date": item.get("date", ""),
            "from": item.get("from", ""),
            "urgency": item.get("urgency", "low"),
            "keyPoints": list(item.get("key_points") or []),
            "asks": list(item.get("asks") or []),
            "suggestedResponse": item.get("suggested_response", ""),
            "pdfFilename": item.get("pdf_filename", ""),
            "createdAt": SERVER_TIMESTAMP,
        }
        if pdf_storage_path:
            item_doc["pdfStoragePath"] = pdf_storage_path
        folder_ref.collection("items").document(item_id).set(item_doc, merge=True)
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


def list_folders(
    db,
    uid: str,
    *,
    limit: int = 20,
    order_by: str = "updatedAt",
) -> list[dict[str, Any]]:
    """Return up to `limit` folder docs for a user, newest first by `order_by`.

    Used by the Telegram /folders picker. Each dict carries `subjectSlug`,
    `subject`, `pdfCount`, and `updatedAt` — enough to render a button.
    Folders missing the order_by field are excluded by Firestore (matches
    Firestore semantics for ordered queries).
    """
    if not uid:
        return []
    coll = db.collection("users").document(uid).collection("folders")
    q = coll.order_by(order_by, direction="DESCENDING").limit(limit)
    out: list[dict[str, Any]] = []
    for snap in q.stream():
        d = snap.to_dict() or {}
        d["subjectSlug"] = d.get("subjectSlug") or snap.id
        out.append(d)
    return out


def fetch_folder(db, uid: str, subject_slug: str) -> dict[str, Any] | None:
    if not uid or not subject_slug:
        return None
    snap = (
        db.collection("users")
        .document(uid)
        .collection("folders")
        .document(subject_slug)
        .get()
    )
    if not snap.exists:
        return None
    d = snap.to_dict() or {}
    d["subjectSlug"] = d.get("subjectSlug") or snap.id
    return d
