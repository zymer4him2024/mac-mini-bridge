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

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_URI = "https://oauth2.googleapis.com/token"

GOOGLE_OAUTH_WEB_CLIENT_ID = os.environ.get(
    "GOOGLE_OAUTH_WEB_CLIENT_ID", ""
).strip()
GOOGLE_OAUTH_WEB_CLIENT_SECRET = os.environ.get(
    "GOOGLE_OAUTH_WEB_CLIENT_SECRET", ""
).strip()

DEFAULT_LOOKBACK = "1d"

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
        raise RuntimeError(
            f"users/{uid}/secrets/gmail.refreshToken is empty"
        )
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
    """Read users/{uid}/config/main; return {senders, lookback, digestEnabled}.

    Defaults: senders=[], lookback="1d", digestEnabled=True. Missing or
    malformed fields fall back to defaults with a warning.
    """
    doc = (
        db.collection("users")
        .document(uid)
        .collection("config")
        .document("main")
        .get()
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
    senders = sorted(
        {s.strip().lower() for s in senders_raw if s.strip()}
    )

    lookback = data.get("watcherLookback", DEFAULT_LOOKBACK)
    if not isinstance(lookback, str) or not lookback.strip():
        log.warning("uid=%s watcherLookback malformed; using default", uid)
        lookback = DEFAULT_LOOKBACK
    lookback = lookback.strip()

    digest_enabled = data.get("digestEnabled", True)
    if not isinstance(digest_enabled, bool):
        log.warning("uid=%s digestEnabled is not bool; defaulting to True", uid)
        digest_enabled = True

    return {
        "senders": senders,
        "lookback": lookback,
        "digestEnabled": digest_enabled,
    }
