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
import time
from pathlib import Path

import requests
from google.api_core import exceptions as gax

from firestore_telegram import _client as _firestore_client
from kms_envelope import unwrap_token

log = logging.getLogger("firestore_alerts")

# HTTP statuses worth retrying on. 4xx (other than 429) are caller errors —
# retrying won't help and can mask bugs.
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_RETRY_BACKOFFS = (1, 4)  # seconds between attempts 1->2 and 2->3


def _user_creds(uid: str) -> tuple[str, int] | None:
    """Return (token, chat_id) for this user's Telegram destination, or None.

    Resolves customerBot first, then falls back to the Quick-Link
    `telegram.chatId` paired with the shared bot token.
    """
    if not uid:
        return None
    try:
        snap = _firestore_client().collection("users").document(uid).get()
    except (gax.GoogleAPIError, FileNotFoundError, OSError, ValueError) as exc:
        log.warning("Firestore read failed for users/%s: %s", uid, exc)
        return None
    if not snap.exists:
        return None
    data = snap.to_dict() or {}

    bot = data.get("customerBot") or {}
    token = bot.get("token")
    chat_id = bot.get("chatId")
    if token and chat_id is not None:
        try:
            unwrapped = unwrap_token(str(token))
            return unwrapped, int(chat_id)
        except (TypeError, ValueError, RuntimeError) as exc:
            log.warning("users/%s.customerBot token/chatId unusable: %s", uid, exc)

    tg = data.get("telegram") or {}
    tg_chat = tg.get("chatId")
    # Read TELEGRAM_BOT_TOKEN at call time so a rotated token takes effect
    # without restarting the watcher process.
    shared_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if shared_token and tg_chat is not None:
        try:
            return shared_token, int(tg_chat)
        except (TypeError, ValueError):
            log.warning("users/%s.telegram has malformed chatId", uid)

    return None


def _resolve(uid: str) -> tuple[str, int] | None:
    return _user_creds(uid)


def _post_with_retry(
    url: str,
    *,
    label: str,
    uid: str,
    timeout: int,
    data: dict,
    files: dict | None = None,
) -> bool:
    """POST with bounded retry and explicit status-code check.

    Returns True only on a confirmed 2xx response. Without the explicit
    status check, a 502 (which raises no exception) was being treated as
    success, so Fix 4's "save state right after alert" would silently drop
    alerts. Retries on connection errors, timeouts, and the transient
    5xx/429 statuses; 4xx (except 429) propagates as a logged failure.
    """
    last_err = ""
    for attempt in range(3):
        # File pointer must rewind between attempts; otherwise retry uploads
        # an empty body and Telegram returns 400.
        if files:
            for f in files.values():
                if hasattr(f, "seek"):
                    f.seek(0)
        try:
            resp = requests.post(url, data=data, files=files, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
        else:
            if 200 <= resp.status_code < 300:
                return True
            last_err = f"HTTP {resp.status_code}"
            if resp.status_code not in _RETRY_STATUSES:
                log.warning(
                    "Telegram %s for uid=%s failed (no retry): %s",
                    label,
                    uid,
                    last_err,
                )
                return False
        if attempt < len(_RETRY_BACKOFFS):
            time.sleep(_RETRY_BACKOFFS[attempt])
    log.warning(
        "Telegram %s for uid=%s failed after 3 attempts: %s",
        label,
        uid,
        last_err,
    )
    return False


def send_alert(uid: str, text: str) -> bool:
    """Send a text message. Truncated to Telegram's 4096-char limit.

    Returns True only on confirmed 2xx delivery.
    """
    creds = _resolve(uid)
    if creds is None:
        log.warning("no Telegram creds for uid=%s; dropping message", uid)
        return False
    token, chat_id = creds
    return _post_with_retry(
        f"https://api.telegram.org/bot{token}/sendMessage",
        label="sendMessage",
        uid=uid,
        timeout=30,
        data={"chat_id": chat_id, "text": text[:4000]},
    )


def send_document(uid: str, path: Path, caption: str) -> bool:
    """Send a document (PDF/PPT/etc.) with caption.

    Returns True only on confirmed 2xx delivery.
    """
    creds = _resolve(uid)
    if creds is None:
        log.warning("no Telegram creds for uid=%s; dropping document", uid)
        return False
    token, chat_id = creds
    try:
        with open(path, "rb") as f:
            return _post_with_retry(
                f"https://api.telegram.org/bot{token}/sendDocument",
                label="sendDocument",
                uid=uid,
                timeout=120,
                data={"chat_id": chat_id, "caption": caption[:1000]},
                files={"document": f},
            )
    except OSError as exc:
        log.warning("Telegram sendDocument open failed for uid=%s: %s", uid, exc)
        return False
