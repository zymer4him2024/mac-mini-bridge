"""Telegram link-token persistence and binding helpers.

bridge.py calls these when a user runs `/start <token-or-shortCode>` in
Telegram. Tokens are issued by the portal's `issueLinkToken` Cloud Function
and live in the `telegram_link_tokens/{tokenId}` collection with fields:

    uid                  string  — the email2ppt user this token binds to
    shortCode            string  — 6-digit manual-entry fallback
    createdAt            ts
    expiresAt            ts      — 24h TTL; Firestore TTL policy sweeps
    consumedAt           ts|null — set on successful link
    consumedByChatId     int|null

Service-account writes bypass Firestore rules, which is required because
clients are forbidden from writing the `telegram` field on their own user
doc (rule guard prevents spoofing another user's chat_id).

Soak window: a legacy `users/{uid}.telegramLink` field still exists for any
in-flight pre-M5 tokens. `consume_link_token` falls back to that path when
the new collection lookup misses. Plan removes the legacy path 30 days
after M5 ships.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

BASE_DIR = Path(__file__).parent.resolve()
SERVICE_ACCOUNT = BASE_DIR / "firebase-service-account.json"

TOKENS_COLLECTION = "telegram_link_tokens"
SHORT_CODE_PATTERN = re.compile(r"^\d{6}$")

log = logging.getLogger("firestore_telegram")


class LinkLookupStatus(str, Enum):
    OK = "ok"
    EXPIRED = "expired"
    CONSUMED_SELF = "consumed_self"
    CONSUMED_OTHER = "consumed_other"
    NOT_FOUND = "not_found"


def _client():
    if not SERVICE_ACCOUNT.exists():
        raise FileNotFoundError(f"service account missing: {SERVICE_ACCOUNT}")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.Certificate(str(SERVICE_ACCOUNT))
        )
    db_id = os.environ.get("FIRESTORE_DATABASE_ID", "email2ppt")
    return firestore.client(database_id=db_id)


def _resolve_token_ref(db, input_value: str):
    """Return the token DocumentReference for either a long token or a shortCode.

    Long token path: doc ID == input. Direct .document() handle, no read.
    Short code path: query collection where shortCode == input, return the
    most recently created unconsumed match. None if no match.
    """
    if SHORT_CODE_PATTERN.match(input_value):
        snaps = (
            db.collection(TOKENS_COLLECTION)
            .where("shortCode", "==", input_value)
            .stream()
        )
        candidate = None
        candidate_created = None
        for snap in snaps:
            data = snap.to_dict() or {}
            if data.get("consumedAt") is not None:
                continue
            created = data.get("createdAt")
            if candidate is None or (
                created is not None
                and candidate_created is not None
                and created > candidate_created
            ):
                candidate = snap.reference
                candidate_created = created
            elif candidate_created is None:
                candidate = snap.reference
                candidate_created = created
        return candidate
    return db.collection(TOKENS_COLLECTION).document(input_value)


def consume_link_token(
    input_value: str,
    chat_id: int,
    username: Optional[str],
    first_name: Optional[str],
) -> tuple[LinkLookupStatus, Optional[str]]:
    """Atomically resolve a token-or-shortCode and bind chat_id to its uid.

    Returns (status, uid_or_none). uid is set for OK and CONSUMED_SELF so
    bridge.py can render personalized copy; None otherwise.

    Falls back to the legacy `users/{uid}.telegramLink` collection when the
    new-collection lookup misses, so in-flight pre-M5 tokens still work
    during the soak window.
    """
    if not input_value:
        return (LinkLookupStatus.NOT_FOUND, None)

    db = _client()
    now = datetime.now(timezone.utc)
    token_ref = _resolve_token_ref(db, input_value)

    if token_ref is not None:
        transaction = db.transaction()
        status, uid = _consume_in_txn(transaction, token_ref, chat_id, now)
        if status is not LinkLookupStatus.NOT_FOUND:
            # Write user binding on OK and CONSUMED_SELF. The latter handles
            # the narrow race where _consume_in_txn committed but the
            # subsequent user write didn't run on a prior attempt — merge
            # write is idempotent so this is safe to repeat.
            if uid is not None and status in (
                LinkLookupStatus.OK,
                LinkLookupStatus.CONSUMED_SELF,
            ):
                _write_user_telegram(db, uid, chat_id, username, first_name)
                log.info(
                    "linked telegram chat_id=%s -> users/%s (new collection, status=%s)",
                    chat_id,
                    uid,
                    status.value,
                )
            return (status, uid)

    legacy_uid = _find_legacy_token(db, input_value, now)
    if legacy_uid is None:
        return (LinkLookupStatus.NOT_FOUND, None)

    _write_user_telegram(db, legacy_uid, chat_id, username, first_name)
    db.collection("users").document(legacy_uid).set(
        {"telegramLink": firestore.DELETE_FIELD},
        merge=True,
    )
    log.info(
        "linked telegram chat_id=%s -> users/%s (legacy path)",
        chat_id,
        legacy_uid,
    )
    return (LinkLookupStatus.OK, legacy_uid)


@firestore.transactional
def _consume_in_txn(
    transaction,
    token_ref,
    chat_id: int,
    now: datetime,
) -> tuple[LinkLookupStatus, Optional[str]]:
    snap = token_ref.get(transaction=transaction)
    if not snap.exists:
        return (LinkLookupStatus.NOT_FOUND, None)
    data = snap.to_dict() or {}
    uid = data.get("uid")
    expires_at = data.get("expiresAt")
    consumed_at = data.get("consumedAt")
    consumed_by = data.get("consumedByChatId")

    if consumed_at is not None:
        if consumed_by is not None and int(consumed_by) == int(chat_id):
            return (LinkLookupStatus.CONSUMED_SELF, uid)
        return (LinkLookupStatus.CONSUMED_OTHER, None)

    if expires_at is None or expires_at < now:
        return (LinkLookupStatus.EXPIRED, None)

    if not uid:
        log.warning("token doc %s has no uid; treating as not_found", token_ref.id)
        return (LinkLookupStatus.NOT_FOUND, None)

    transaction.update(
        token_ref,
        {
            "consumedAt": firestore.SERVER_TIMESTAMP,
            "consumedByChatId": int(chat_id),
        },
    )
    return (LinkLookupStatus.OK, uid)


def _find_legacy_token(db, token: str, now: datetime) -> Optional[str]:
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
        if expires is None or expires < now:
            return None
        return snap.id
    return None


def _write_user_telegram(
    db,
    uid: str,
    chat_id: int,
    username: Optional[str],
    first_name: Optional[str],
) -> None:
    db.collection("users").document(uid).set(
        {
            "telegram": {
                "chatId": int(chat_id),
                "username": username or "",
                "firstName": first_name or "",
                "linkedAt": datetime.now(timezone.utc),
            },
        },
        merge=True,
    )


def find_telegram_link(chat_id: int) -> Optional[dict]:
    """Return binding info for a Telegram chat_id, or None.

    Used by /whoami and /unlink to look up which uid owns this chat.
    """
    if not chat_id:
        return None
    db = _client()
    snaps = (
        db.collection("users")
        .where("telegram.chatId", "==", int(chat_id))
        .limit(1)
        .stream()
    )
    for snap in snaps:
        data = snap.to_dict() or {}
        tg = data.get("telegram") or {}
        gmail = data.get("gmail") or {}
        return {
            "uid": snap.id,
            "username": tg.get("username") or "",
            "firstName": tg.get("firstName") or "",
            "linkedAt": tg.get("linkedAt"),
            "gmailEmail": gmail.get("email") or "",
        }
    return None


def delete_telegram_link(uid: str) -> None:
    """Remove users/{uid}.telegram. Service-account write."""
    db = _client()
    db.collection("users").document(uid).set(
        {"telegram": firestore.DELETE_FIELD},
        merge=True,
    )
    log.info("unlinked telegram for users/%s", uid)
