"""Publish run records to Firestore so the email2ppt portal can show activity.

Each script (watcher, digest, ppt, config_sync) calls report_run() at the end
of main() with timing + outcome. Records auto-expire 30 days after start
(Firestore TTL on `expiresAt`).

Failures here never crash the caller — Firestore unreachability is logged and
swallowed. The local Telegram path is the source of truth for operator alerts;
this is just the dashboard data feed.

Multi-tenant: writes land at customers/{EMAIL2PPT_CUSTOMER_UID}/activity. The
UID env var must be set (run migrate_to_multitenant.py to discover it). If it
is unset, reports are skipped with a warning.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core import exceptions as gax

BASE_DIR = Path(__file__).parent.resolve()
SERVICE_ACCOUNT = BASE_DIR / "firebase-service-account.json"
TTL_DAYS = 30

log = logging.getLogger("firestore_activity")


def _client():
    if not SERVICE_ACCOUNT.exists():
        raise FileNotFoundError(f"service account missing: {SERVICE_ACCOUNT}")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.Certificate(str(SERVICE_ACCOUNT))
        )
    db_id = os.environ.get("FIRESTORE_DATABASE_ID", "email2ppt")
    return firestore.client(database_id=db_id)


def report_run(
    run_type: str,
    status: str,
    *,
    started_at: datetime,
    email_count: int = 0,
    outputs: list[str] | None = None,
    error: str | None = None,
) -> None:
    """Write one activity record. Never raises."""
    customer_uid = os.environ.get("EMAIL2PPT_CUSTOMER_UID", "").strip()
    if not customer_uid:
        log.warning(
            "EMAIL2PPT_CUSTOMER_UID not set; activity report skipped (%s)",
            run_type,
        )
        return

    if status not in ("ok", "error"):
        log.warning("invalid status %r; coercing to error", status)
        status = "error"

    finished_at = datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    expires_at = started_at + timedelta(days=TTL_DAYS)

    record = {
        "type": run_type,
        "status": status,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "durationMs": duration_ms,
        "emailCount": int(email_count),
        "outputs": list(outputs or []),
        "errorMessage": (error[:2000] if error else None),
        "expiresAt": expires_at,
    }

    try:
        db = _client()
        db.collection("customers").document(customer_uid).collection(
            "activity"
        ).add(record)
    except FileNotFoundError as exc:
        log.warning("activity report skipped: %s", exc)
    except gax.GoogleAPIError as exc:
        log.warning("activity report failed (%s): %s", run_type, exc)
