"""Append-only audit log helpers.

Writes to `users/{uid}/audit/{auto-id}`. Service-account only (Firestore
rules deny client writes). Audit failures must NOT block the user-facing
operation that triggered them — losing one entry is preferable to failing
a /unlink because audit infra is down.

Read access for owner + admin lives in firestore.rules; this module only
writes.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core import exceptions as gax

BASE_DIR = Path(__file__).parent.resolve()
SERVICE_ACCOUNT = BASE_DIR / "firebase-service-account.json"

AuditEvent = Literal[
    "gmail_link",
    "gmail_disconnect",
    "telegram_link",
    "telegram_unlink",
    "customer_bot_link",
    "customer_bot_unlink",
    "config_change",
    "data_export",
    "data_delete",
    "admin_action",
]

log = logging.getLogger("firestore_audit")


def _client():
    if not SERVICE_ACCOUNT.exists():
        raise FileNotFoundError(f"service account missing: {SERVICE_ACCOUNT}")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.Certificate(str(SERVICE_ACCOUNT))
        )
    db_id = os.environ.get("FIRESTORE_DATABASE_ID", "email2ppt")
    return firestore.client(database_id=db_id)


def record_audit(
    uid: str,
    event: AuditEvent,
    actor: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a single audit entry. Best-effort; never raises."""
    if not uid:
        return
    try:
        db = _client()
        db.collection("users").document(uid).collection("audit").add(
            {
                "event": event,
                "actor": actor,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc),
            }
        )
    except (gax.GoogleAPIError, FileNotFoundError, OSError, ValueError) as exc:
        log.warning(
            "audit write failed uid=%s event=%s: %s", uid, event, exc
        )
