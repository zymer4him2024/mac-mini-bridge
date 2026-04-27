"""Resolves portal-linked users and their Gmail credentials from Firestore.

Shared by watcher.py (per-cycle loop) and digest.py (per-day loop). Reads the
shared Web OAuth client id/secret from env at module load — callers MUST run
load_dotenv() before importing this module.
"""

from __future__ import annotations

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
