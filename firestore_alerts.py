"""Per-user alert delivery via Telegram.

`send_alert(uid, text)` and `send_document(uid, path, caption)` look up
`users/{uid}.customerBot` and route the message through that bot if the
customer has linked their own. Otherwise they fall back to the shared bot
defined by env (`TELEGRAM_BOT_TOKEN` + `AUTHORIZED_CHAT_ID`) so legacy
single-tenant deployments keep working until the customer opts in via the
portal's "Use my own bot" wizard.

Reuses the service-account Firestore client from `firestore_telegram.py`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

from firestore_telegram import _client as _firestore_client

log = logging.getLogger("firestore_alerts")

_SHARED_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_SHARED_CHAT = os.environ.get("AUTHORIZED_CHAT_ID", "")


def _shared_creds() -> tuple[str, int] | None:
    if not _SHARED_TOKEN or not _SHARED_CHAT:
        return None
    try:
        return _SHARED_TOKEN, int(_SHARED_CHAT)
    except ValueError:
        return None


def _user_creds(uid: str) -> tuple[str, int] | None:
    """Return (token, chat_id) from users/{uid}.customerBot, or None if not linked."""
    if not uid:
        return None
    try:
        snap = _firestore_client().collection("users").document(uid).get()
    except Exception:
        log.exception("Firestore read failed for users/%s; falling back to shared bot", uid)
        return None
    if not snap.exists:
        return None
    bot = (snap.to_dict() or {}).get("customerBot") or {}
    token = bot.get("token")
    chat_id = bot.get("chatId")
    if not token or chat_id is None:
        return None
    try:
        return str(token), int(chat_id)
    except (TypeError, ValueError):
        log.warning("users/%s.customerBot has malformed token/chatId; using shared bot", uid)
        return None


def _resolve(uid: str) -> tuple[str, int] | None:
    return _user_creds(uid) or _shared_creds()


def send_alert(uid: str, text: str) -> None:
    """Send a text message. Truncated to Telegram's 4096-char limit."""
    creds = _resolve(uid)
    if creds is None:
        log.warning("no Telegram creds for uid=%s; dropping message", uid)
        return
    token, chat_id = creds
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text[:4000]},
            timeout=30,
        )
    except requests.RequestException as exc:
        log.warning("Telegram sendMessage failed for uid=%s: %s", uid, exc)


def send_document(uid: str, path: Path, caption: str) -> None:
    """Send a document (PDF/PPT/etc.) with caption."""
    creds = _resolve(uid)
    if creds is None:
        log.warning("no Telegram creds for uid=%s; dropping document", uid)
        return
    token, chat_id = creds
    try:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": chat_id, "caption": caption[:1000]},
                files={"document": f},
                timeout=120,
            )
    except (OSError, requests.RequestException) as exc:
        log.warning("Telegram sendDocument failed for uid=%s: %s", uid, exc)
