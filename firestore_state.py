"""Firestore reads and writes for per-user execution state.

Owns `users/{uid}/state/watcher` (processedIds + lastRunAt) and the
`users/{uid}.gmail.email` self-identity read used for self-sent suppression.
Extracted from watcher.py so top-level pipeline scripts never call
`db.collection(...)` directly — see plan in
.claude/plans/in-the-senders-enable-cozy-sparrow.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

MAX_PROCESSED = 200


def load_user_state(db, uid: str) -> list[str]:
    doc = (
        db.collection("users")
        .document(uid)
        .collection("state")
        .document("watcher")
        .get()
    )
    if not doc.exists:
        return []
    data = doc.to_dict() or {}
    ids = data.get("processedIds") or []
    return [str(x) for x in ids]


def load_user_last_run_at(db, uid: str) -> datetime | None:
    """Return the last time the watcher actually processed this user, or None.

    Returns timezone-aware UTC datetime (Firestore timestamps deserialize
    as UTC-aware) or None if the user has never been processed.
    """
    doc = (
        db.collection("users")
        .document(uid)
        .collection("state")
        .document("watcher")
        .get()
    )
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    last = data.get("lastRunAt")
    if isinstance(last, datetime):
        return last
    return None


def save_user_state(db, uid: str, processed_ids: list[str]) -> None:
    db.collection("users").document(uid).collection("state").document("watcher").set(
        {
            "processedIds": processed_ids[-MAX_PROCESSED:],
            "updatedAt": datetime.now(timezone.utc),
        },
        merge=True,
    )


def save_user_last_run_at(db, uid: str, when: datetime) -> None:
    """Mark the user as having been processed at `when` (UTC)."""
    db.collection("users").document(uid).collection("state").document("watcher").set(
        {"lastRunAt": when}, merge=True
    )


def load_user_self_email(db, uid: str) -> str:
    """Return users/{uid}.gmail.email lowercased, or '' if missing.

    Used to suppress alerts on the user's own outgoing mail. When two
    portal-linked users share a Telegram chat (one as recipient via their
    inbox, the other as sender via their Sent folder), both would otherwise
    fire on the same conversation.
    """
    snap = db.collection("users").document(uid).get()
    if not snap.exists:
        return ""
    return ((snap.to_dict() or {}).get("gmail") or {}).get("email", "").strip().lower()
