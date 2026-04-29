"""Mirror watcher's per-email summaries into a centralized lead tracker.

Each email becomes one row at users/{uid}/leads/{lead_id}, where lead_id is a
stable hash of (sender_email, subject_slug). Subsequent emails from the same
sender about the same subject UPDATE the existing row (lastSeenAt,
interactionCount, latest urgency) rather than create new rows.

Status is user-editable from the portal. The watcher writes with merge=True
and gates first-write-only fields (status, firstSeenAt, createdAt) behind a
get() check so subsequent writes do NOT overwrite a status the user has
edited.

Failures here never crash the caller — the local PDF/CSV pipeline is the
source of truth for delivery; the lead tracker is best-effort.
"""

from __future__ import annotations

import hashlib
import logging

from google.api_core import exceptions as gax
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

log = logging.getLogger("firestore_leads")


def _lead_id(sender_email: str, subject_slug: str) -> str:
    key = f"{sender_email.strip().lower()}|{subject_slug}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def upsert_lead(
    db,
    uid: str,
    *,
    sender_email: str,
    sender_name: str,
    subject: str,
    subject_slug: str,
    urgency: str,
    pdf_filename: str,
    suggested_response: str,
) -> None:
    """Upsert a lead row keyed by (sender_email, subject_slug). Never raises."""
    if not uid or not sender_email:
        log.warning("upsert_lead skipped: empty uid or sender_email")
        return

    lead_id = _lead_id(sender_email, subject_slug)

    try:
        ref = (
            db.collection("users")
            .document(uid)
            .collection("leads")
            .document(lead_id)
        )
        snap = ref.get()
        existing = snap.to_dict() if snap.exists else {}

        payload: dict = {
            "senderEmail": sender_email.strip().lower(),
            "senderName": (sender_name or "").strip(),
            "subject": subject or "(no subject)",
            "subjectSlug": subject_slug,
            "urgency": urgency or "low",
            "lastPdfFilename": pdf_filename,
            "lastSummaryResponse": suggested_response or "",
            "lastSeenAt": SERVER_TIMESTAMP,
            "updatedAt": SERVER_TIMESTAMP,
            "interactionCount": int(existing.get("interactionCount", 0)) + 1,
        }
        if not existing:
            payload["status"] = "new"
            payload["firstSeenAt"] = SERVER_TIMESTAMP
            payload["createdAt"] = SERVER_TIMESTAMP

        ref.set(payload, merge=True)
    except gax.GoogleAPIError as exc:
        log.warning(
            "lead upsert failed (uid=%s lead=%s): %s", uid, lead_id, exc
        )
    except Exception as exc:  # noqa: BLE001 - best-effort mirror
        log.warning(
            "lead upsert unexpected error (uid=%s lead=%s): %s",
            uid,
            lead_id,
            exc,
        )
