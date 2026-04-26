#!/usr/bin/env python3
"""One-shot migration to the multi-tenant Firestore data model.

Copies legacy single-tenant docs into per-customer paths:
  config/email2ppt          -> customers/{uid}/config/main
  activity/{auto-id}        -> customers/{uid}/activity/{same-id}
  meta/admins               -> meta/operators

Resolves {uid} by looking up the Firebase Auth user for OWNER_EMAIL. The
legacy docs are NOT deleted — keep them as a rollback for 1-2 weeks, then
remove in a follow-up.

Idempotent: safe to re-run. Each upsert is a `set(merge=True)` and activity
records are written by source ID so duplicates collapse.

Usage: python migrate_to_multitenant.py
Prints the resolved UID at the end — copy into Mac Mini .env as
EMAIL2PPT_CUSTOMER_UID.
"""

import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import auth, credentials, firestore
from google.api_core import exceptions as gax

BASE_DIR = Path(__file__).parent.resolve()
SERVICE_ACCOUNT = BASE_DIR / "firebase-service-account.json"
FIRESTORE_DB_ID = os.environ.get("FIRESTORE_DATABASE_ID", "email2ppt")
OWNER_EMAIL = os.environ.get("EMAIL2PPT_OWNER_EMAIL", "zymer4him@gmail.com")

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(message)s"
)
log = logging.getLogger("migrate")


def init_app() -> None:
    if not SERVICE_ACCOUNT.exists():
        log.error("service account missing: %s", SERVICE_ACCOUNT)
        sys.exit(1)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(SERVICE_ACCOUNT)))


def resolve_uid(email: str) -> str:
    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        log.error(
            "no Firebase Auth user found for %s — sign in once at email2ppt.web.app first, then re-run",
            email,
        )
        sys.exit(1)
    log.info("resolved %s -> uid=%s", email, user.uid)
    return user.uid


def migrate_config(db, uid: str) -> None:
    src = db.collection("config").document("email2ppt").get()
    if not src.exists:
        log.info("legacy config/email2ppt does not exist; skipping")
        return
    payload = src.to_dict() or {}
    payload["migratedAt"] = datetime.now(timezone.utc)
    payload["migratedFrom"] = "config/email2ppt"
    db.collection("customers").document(uid).collection("config").document("main").set(
        payload, merge=True
    )
    log.info("config -> customers/%s/config/main (fields: %s)", uid, sorted(payload))


def migrate_activity(db, uid: str) -> int:
    coll = db.collection("activity")
    docs = list(coll.stream())
    if not docs:
        log.info("legacy activity/* is empty; skipping")
        return 0
    target = db.collection("customers").document(uid).collection("activity")
    n = 0
    for d in docs:
        target.document(d.id).set(d.to_dict() or {}, merge=True)
        n += 1
    log.info("activity -> customers/%s/activity (%d records)", uid, n)
    return n


def migrate_admins(db) -> None:
    src = db.collection("meta").document("admins").get()
    if not src.exists:
        log.info("legacy meta/admins does not exist; skipping")
        return
    payload = src.to_dict() or {}
    payload["migratedAt"] = datetime.now(timezone.utc)
    payload["migratedFrom"] = "meta/admins"
    db.collection("meta").document("operators").set(payload, merge=True)
    log.info("admins -> meta/operators (emails: %s)", payload.get("emails"))


def upsert_customer_profile(db, uid: str, email: str) -> None:
    db.collection("customers").document(uid).set(
        {
            "email": email,
            "status": "active",
            "createdAt": datetime.now(timezone.utc),
            "migratedAt": datetime.now(timezone.utc),
        },
        merge=True,
    )
    log.info("customer profile upserted: customers/%s", uid)


def main() -> None:
    init_app()
    db = firestore.client(database_id=FIRESTORE_DB_ID)
    log.info("Firestore database: %s", FIRESTORE_DB_ID)

    uid = resolve_uid(OWNER_EMAIL)
    try:
        upsert_customer_profile(db, uid, OWNER_EMAIL)
        migrate_config(db, uid)
        migrate_activity(db, uid)
        migrate_admins(db)
    except gax.GoogleAPIError as exc:
        log.error("Firestore error during migration: %s", exc)
        sys.exit(2)

    print()
    print("=" * 60)
    print("Migration complete. Set this in your .env:")
    print(f"  EMAIL2PPT_CUSTOMER_UID={uid}")
    print("=" * 60)


if __name__ == "__main__":
    main()
