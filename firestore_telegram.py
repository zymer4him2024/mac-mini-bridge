"""Telegram link-token helpers for the bot.

bridge.py calls these when a user runs `/start <token>` in Telegram. The
token was generated client-side in the email2ppt portal Settings tab and
stored at users/{uid}.telegramLink — find_link_token resolves it back to
the uid, complete_link writes the chat_id and clears the token.

Service-account writes bypass Firestore rules, which is required because
clients are forbidden from writing the `telegram` field on their own user
doc (rule guard prevents spoofing another user's chat_id).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

BASE_DIR = Path(__file__).parent.resolve()
SERVICE_ACCOUNT = BASE_DIR / "firebase-service-account.json"

log = logging.getLogger("firestore_telegram")


def _client():
    if not SERVICE_ACCOUNT.exists():
        raise FileNotFoundError(f"service account missing: {SERVICE_ACCOUNT}")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.Certificate(str(SERVICE_ACCOUNT))
        )
    db_id = os.environ.get("FIRESTORE_DATABASE_ID", "email2ppt")
    return firestore.client(database_id=db_id)


def find_link_token(token: str) -> str | None:
    """Return the uid whose users/{uid}.telegramLink.token == token, or None.

    Expired tokens (telegramLink.expiresAt < now) are treated as not found.
    """
    if not token:
        return None
    db = _client()
    now = datetime.now(timezone.utc)
    snaps = (
        db.collection("users")
        .where("telegramLink.token", "==", token)
        .limit(1)
        .stream()
    )
    for snap in snaps:
        data = snap.to_dict() or {}
        link = data.get("telegramLink") or {}
        expires = link.get("expiresAt")
        # Firestore returns timestamps as datetime; defensive in case it's None.
        if expires is None or expires < now:
            return None
        return snap.id
    return None


def complete_link(
    uid: str,
    chat_id: int,
    username: str | None,
    first_name: str | None,
) -> None:
    """Set users/{uid}.telegram and clear telegramLink. Service-account write."""
    db = _client()
    db.collection("users").document(uid).set(
        {
            "telegram": {
                "chatId": int(chat_id),
                "username": username or "",
                "firstName": first_name or "",
                "linkedAt": datetime.now(timezone.utc),
            },
            "telegramLink": firestore.DELETE_FIELD,
        },
        merge=True,
    )
    log.info("linked telegram chat_id=%s -> users/%s", chat_id, uid)
