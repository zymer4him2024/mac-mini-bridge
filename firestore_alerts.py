"""Per-user alert delivery via Telegram.

`send_alert(uid, text)` and `send_document(uid, path, caption)` resolve
the destination for a message in this priority order:

  1. `users/{uid}.customerBot` — the user brought their own bot via the
     portal's "Use my own bot" wizard.
  2. `users/{uid}.telegram` — the user used the portal's "Quick link
     (shared bot)" flow; we deliver via the shared `TELEGRAM_BOT_TOKEN`
     using the user's own `chatId`.

If neither is set, the message is dropped. We do NOT fall back to a
global shared chat, since that would leak one user's emails into the
operator's inbox.

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


def _user_creds(uid: str) -> tuple[str, int] | None:
    """Return (token, chat_id) for this user's Telegram destination, or None.

    Resolves customerBot first, then falls back to the Quick-Link
    `telegram.chatId` paired with the shared bot token.
    """
    if not uid:
        return None
    try:
        snap = _firestore_client().collection("users").document(uid).get()
    except Exception:
        log.exception("Firestore read failed for users/%s", uid)
        return None
    if not snap.exists:
        return None
    data = snap.to_dict() or {}

    bot = data.get("customerBot") or {}
    token = bot.get("token")
    chat_id = bot.get("chatId")
    if token and chat_id is not None:
        try:
            return str(token), int(chat_id)
        except (TypeError, ValueError):
            log.warning("users/%s.customerBot has malformed token/chatId", uid)

    tg = data.get("telegram") or {}
    tg_chat = tg.get("chatId")
    if _SHARED_TOKEN and tg_chat is not None:
        try:
            return _SHARED_TOKEN, int(tg_chat)
        except (TypeError, ValueError):
            log.warning("users/%s.telegram has malformed chatId", uid)

    return None


def _resolve(uid: str) -> tuple[str, int] | None:
    return _user_creds(uid)


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
