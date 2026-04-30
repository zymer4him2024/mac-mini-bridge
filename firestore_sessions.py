"""Per-user ephemeral session state for the Telegram bot.

One doc per user at users/{uid}/sessions/telegram. Holds the currently scoped
folder for /ask. Auto-expires via Firestore TTL on `expiresAt`.

Why Firestore (not in-memory): bridge.py runs as a single launchd process,
but it can be restarted (config reload, crash, deploy). Persisting the scope
means a user mid-conversation isn't kicked out by a 5-second restart.

The Firestore TTL policy must be configured once on the `expiresAt` field
in the `sessions` collection-group:
  gcloud firestore fields ttls update expiresAt \\
    --collection-group=sessions --enable-ttl \\
    --project=simpleios01 --database=email2ppt
This module also enforces expiry client-side in get_session() so even before
Firestore's background sweep runs, an expired scope is treated as cleared.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.api_core import exceptions as gax
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

log = logging.getLogger("firestore_sessions")


def _ref(db, uid: str):
    return (
        db.collection("users")
        .document(uid)
        .collection("sessions")
        .document("telegram")
    )


def get_session(db, uid: str) -> dict[str, Any] | None:
    """Return the active session dict (with currentFolderSlug, currentSubject)
    or None if no session exists or it has expired."""
    if not uid:
        return None
    try:
        snap = _ref(db, uid).get()
    except gax.GoogleAPIError as exc:
        log.warning("get_session firestore error uid=%s: %s", uid, exc)
        return None
    if not snap.exists:
        return None
    d = snap.to_dict() or {}
    expires_at = d.get("expiresAt")
    if expires_at and isinstance(expires_at, datetime):
        if expires_at <= datetime.now(timezone.utc):
            return None
    return d


def set_folder_scope(
    db,
    uid: str,
    subject_slug: str,
    *,
    subject: str = "",
    ttl_minutes: int = 30,
) -> None:
    """Pin a folder scope for this user. Overwrites any prior scope."""
    if not uid or not subject_slug:
        raise ValueError("set_folder_scope: uid and subject_slug required")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    _ref(db, uid).set(
        {
            "currentFolderSlug": subject_slug,
            "currentSubject": subject or "",
            "updatedAt": SERVER_TIMESTAMP,
            "expiresAt": expires_at,
        },
        merge=False,
    )


def clear_session(db, uid: str) -> None:
    if not uid:
        return
    try:
        _ref(db, uid).delete()
    except gax.GoogleAPIError as exc:
        log.warning("clear_session firestore error uid=%s: %s", uid, exc)
