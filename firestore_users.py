"""Resolves portal-linked users and their Gmail credentials/config from Firestore.

Shared by watcher.py (per-cycle loop) and digest.py (per-day loop). Reads the
shared Web OAuth client id/secret from env at module load — callers MUST run
load_dotenv() before importing this module.
"""

from __future__ import annotations

import logging
import os

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from kms_envelope import unwrap_token

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_URI = "https://oauth2.googleapis.com/token"

GOOGLE_OAUTH_WEB_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_WEB_CLIENT_ID", "").strip()
GOOGLE_OAUTH_WEB_CLIENT_SECRET = os.environ.get(
    "GOOGLE_OAUTH_WEB_CLIENT_SECRET", ""
).strip()

DEFAULT_LOOKBACK = "1d"
DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 365

# Per-user watcher cadence. The LaunchAgent ticks every 2 min (the floor);
# users opting into a slower cadence are skipped on intermediate ticks.
ALLOWED_INTERVAL_MINUTES = (2, 5, 10, 15, 30, 60)
DEFAULT_INTERVAL_MINUTES = 5

DEFAULT_SUMMARY_KEY_POINTS_MAX = 6
SUMMARY_KEY_POINTS_MIN = 3
SUMMARY_KEY_POINTS_MAX = 10
DEFAULT_SUMMARY_ASKS_MAX = 4
SUMMARY_ASKS_MIN = 1
SUMMARY_ASKS_MAX = 6
SUMMARY_PERSONA_MAX_CHARS = 500

log = logging.getLogger("firestore_users")


def enumerate_linked_users(db) -> list[str]:
    """Return uids of all users with gmail.email set."""
    uids: list[str] = []
    for snap in db.collection("users").stream():
        data = snap.to_dict() or {}
        if (data.get("gmail") or {}).get("email"):
            uids.append(snap.id)
    return uids


def load_user_credentials(db, uid: str) -> Credentials:
    """Build refreshed Credentials from users/{uid}/secrets/gmail."""
    if not GOOGLE_OAUTH_WEB_CLIENT_ID or not GOOGLE_OAUTH_WEB_CLIENT_SECRET:
        raise RuntimeError(
            "GOOGLE_OAUTH_WEB_CLIENT_ID and GOOGLE_OAUTH_WEB_CLIENT_SECRET "
            "must be set in .env"
        )
    secret_doc = (
        db.collection("users")
        .document(uid)
        .collection("secrets")
        .document("gmail")
        .get()
    )
    if not secret_doc.exists:
        raise RuntimeError(f"no refresh token at users/{uid}/secrets/gmail")
    data = secret_doc.to_dict() or {}
    refresh_token = data.get("refreshToken")
    if not refresh_token:
        raise RuntimeError(f"users/{uid}/secrets/gmail.refreshToken is empty")
    refresh_token = unwrap_token(refresh_token)
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=GOOGLE_OAUTH_WEB_CLIENT_ID,
        client_secret=GOOGLE_OAUTH_WEB_CLIENT_SECRET,
        scopes=GMAIL_SCOPES,
    )
    creds.refresh(Request())
    return creds


def load_user_config(db, uid: str) -> dict:
    """Read users/{uid}/config/main; return per-user runtime config.

    Returns: {senders, lookback, digestEnabled, displayName, retentionDays,
              summaryPersona, summaryKeyPointsMax, summaryAsksMax}.
    Missing or malformed fields fall back to defaults with a warning.
    """
    doc = (
        db.collection("users").document(uid).collection("config").document("main").get()
    )
    data = doc.to_dict() if doc.exists else {}
    if not isinstance(data, dict):
        data = {}

    senders_raw = data.get("priorityWatchSenders", [])
    if not isinstance(senders_raw, list) or not all(
        isinstance(s, str) for s in senders_raw
    ):
        log.warning("uid=%s priorityWatchSenders malformed; treating as empty", uid)
        senders_raw = []
    senders = sorted({s.strip().lower() for s in senders_raw if s.strip()})

    lookback = data.get("watcherLookback", DEFAULT_LOOKBACK)
    if not isinstance(lookback, str) or not lookback.strip():
        log.warning("uid=%s watcherLookback malformed; using default", uid)
        lookback = DEFAULT_LOOKBACK
    lookback = lookback.strip()

    digest_enabled = data.get("digestEnabled", True)
    if not isinstance(digest_enabled, bool):
        log.warning("uid=%s digestEnabled is not bool; defaulting to True", uid)
        digest_enabled = True

    display_name = data.get("userDisplayName", "")
    if not isinstance(display_name, str):
        log.warning("uid=%s userDisplayName is not str; defaulting to empty", uid)
        display_name = ""
    display_name = display_name.strip()

    retention_raw = data.get("retentionDays", DEFAULT_RETENTION_DAYS)
    if isinstance(retention_raw, bool) or not isinstance(retention_raw, int):
        log.warning(
            "uid=%s retentionDays not an int; defaulting to %d",
            uid,
            DEFAULT_RETENTION_DAYS,
        )
        retention_days = DEFAULT_RETENTION_DAYS
    elif retention_raw < 1 or retention_raw > MAX_RETENTION_DAYS:
        log.warning(
            "uid=%s retentionDays=%d out of range [1, %d]; clamping",
            uid,
            retention_raw,
            MAX_RETENTION_DAYS,
        )
        retention_days = max(1, min(retention_raw, MAX_RETENTION_DAYS))
    else:
        retention_days = retention_raw

    persona_raw = data.get("summaryPersona", "")
    if isinstance(persona_raw, str):
        persona = persona_raw.strip()[:SUMMARY_PERSONA_MAX_CHARS]
    else:
        log.warning("uid=%s summaryPersona is not str; defaulting to empty", uid)
        persona = ""

    kp_raw = data.get("summaryKeyPointsMax", DEFAULT_SUMMARY_KEY_POINTS_MAX)
    try:
        kp_int = int(kp_raw)
        if isinstance(kp_raw, bool):
            raise TypeError
        if kp_int < SUMMARY_KEY_POINTS_MIN or kp_int > SUMMARY_KEY_POINTS_MAX:
            log.warning(
                "uid=%s summaryKeyPointsMax=%d out of range [%d, %d]; clamping",
                uid,
                kp_int,
                SUMMARY_KEY_POINTS_MIN,
                SUMMARY_KEY_POINTS_MAX,
            )
        kp_max = max(SUMMARY_KEY_POINTS_MIN, min(SUMMARY_KEY_POINTS_MAX, kp_int))
    except (TypeError, ValueError):
        log.warning(
            "uid=%s summaryKeyPointsMax invalid (%r); using default %d",
            uid,
            kp_raw,
            DEFAULT_SUMMARY_KEY_POINTS_MAX,
        )
        kp_max = DEFAULT_SUMMARY_KEY_POINTS_MAX

    interval_raw = data.get("intervalMinutes", DEFAULT_INTERVAL_MINUTES)
    if isinstance(interval_raw, bool) or not isinstance(interval_raw, int):
        log.warning(
            "uid=%s intervalMinutes not an int; defaulting to %d",
            uid,
            DEFAULT_INTERVAL_MINUTES,
        )
        interval_minutes = DEFAULT_INTERVAL_MINUTES
    elif interval_raw not in ALLOWED_INTERVAL_MINUTES:
        log.warning(
            "uid=%s intervalMinutes=%d not in %s; defaulting to %d",
            uid,
            interval_raw,
            ALLOWED_INTERVAL_MINUTES,
            DEFAULT_INTERVAL_MINUTES,
        )
        interval_minutes = DEFAULT_INTERVAL_MINUTES
    else:
        interval_minutes = interval_raw

    asks_raw = data.get("summaryAsksMax", DEFAULT_SUMMARY_ASKS_MAX)
    try:
        asks_int = int(asks_raw)
        if isinstance(asks_raw, bool):
            raise TypeError
        if asks_int < SUMMARY_ASKS_MIN or asks_int > SUMMARY_ASKS_MAX:
            log.warning(
                "uid=%s summaryAsksMax=%d out of range [%d, %d]; clamping",
                uid,
                asks_int,
                SUMMARY_ASKS_MIN,
                SUMMARY_ASKS_MAX,
            )
        asks_max = max(SUMMARY_ASKS_MIN, min(SUMMARY_ASKS_MAX, asks_int))
    except (TypeError, ValueError):
        log.warning(
            "uid=%s summaryAsksMax invalid (%r); using default %d",
            uid,
            asks_raw,
            DEFAULT_SUMMARY_ASKS_MAX,
        )
        asks_max = DEFAULT_SUMMARY_ASKS_MAX

    return {
        "senders": senders,
        "lookback": lookback,
        "digestEnabled": digest_enabled,
        "displayName": display_name,
        "retentionDays": retention_days,
        "summaryPersona": persona,
        "summaryKeyPointsMax": kp_max,
        "summaryAsksMax": asks_max,
        "intervalMinutes": interval_minutes,
    }
