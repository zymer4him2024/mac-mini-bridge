#!/usr/bin/env python3
"""One-shot migration to the unified users-collection data model.

Copies legacy multi-tenant docs into per-user paths, adding a `role` field
on each user doc:

  customers/{uid}                    -> users/{uid}                (role="customer")
  customers/{uid}/config/main        -> users/{uid}/config/main
  customers/{uid}/activity/{auto-id} -> users/{uid}/activity/{same-id}

After copying, reads `meta/operators.emails` and promotes those accounts
to `users/{uid}.role = "admin"` via Firebase Auth UID lookup. The legacy
`customers/*` and `meta/operators` docs are NOT deleted — keep them as a
rollback for 1-2 weeks, then remove in a follow-up.

Idempotent: safe to re-run. Writes use `set(merge=True)`. Existing role
values are preserved (the merge does not overwrite an explicit role).

Usage: python migrate_to_users.py
Prints summary at the end. Copy the admin UID into Mac Mini .env as
EMAIL2PPT_USER_UID.
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("migrate")


def init_app() -> None:
    if not SERVICE_ACCOUNT.exists():
        log.error("service account missing: %s", SERVICE_ACCOUNT)
        sys.exit(1)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(SERVICE_ACCOUNT)))


def copy_user_from_customer(db, uid: str) -> None:
    src = db.collection("customers").document(uid).get()
    payload = src.to_dict() or {} if src.exists else {}

    target_ref = db.collection("users").document(uid)
    existing = target_ref.get()
    existing_role = (existing.to_dict() or {}).get("role") if existing.exists else None

    payload["role"] = existing_role or "customer"
    payload["migratedAt"] = datetime.now(timezone.utc)
    payload["migratedFrom"] = f"customers/{uid}"
    target_ref.set(payload, merge=True)
    log.info("user upserted: users/%s (role=%s)", uid, payload["role"])


def copy_subcollection(db, uid: str, sub: str) -> int:
    src = db.collection("customers").document(uid).collection(sub).stream()
    target = db.collection("users").document(uid).collection(sub)
    n = 0
    for d in src:
        target.document(d.id).set(d.to_dict() or {}, merge=True)
        n += 1
    if n:
        log.info("copied %d %s docs -> users/%s/%s", n, sub, uid, sub)
    return n


def promote_admins(db) -> tuple[int, list[str]]:
    src = db.collection("meta").document("operators").get()
    if not src.exists:
        log.info("meta/operators does not exist; no admin promotions")
        return 0, []
    emails = (src.to_dict() or {}).get("emails") or []
    promoted: list[str] = []
    for email in emails:
        try:
            user = auth.get_user_by_email(email)
        except auth.UserNotFoundError:
            log.warning(
                "operator %s has no Firebase Auth user; skipping promotion",
                email,
            )
            continue
        db.collection("users").document(user.uid).set(
            {
                "email": email,
                "role": "admin",
                "promotedAt": datetime.now(timezone.utc),
            },
            merge=True,
        )
        promoted.append(f"{email} (uid={user.uid})")
        log.info("promoted %s -> users/%s.role=admin", email, user.uid)
    return len(promoted), promoted


def main() -> None:
    init_app()
    db = firestore.client(database_id=FIRESTORE_DB_ID)
    log.info("Firestore database: %s", FIRESTORE_DB_ID)

    try:
        customer_docs = list(db.collection("customers").stream())
        log.info("found %d customer doc(s) to migrate", len(customer_docs))

        for cd in customer_docs:
            uid = cd.id
            copy_user_from_customer(db, uid)
            copy_subcollection(db, uid, "config")
            copy_subcollection(db, uid, "activity")

        admin_count, promoted = promote_admins(db)
    except gax.GoogleAPIError as exc:
        log.error("Firestore error during migration: %s", exc)
        sys.exit(2)

    users = list(db.collection("users").stream())
    admins = [u for u in users if (u.to_dict() or {}).get("role") == "admin"]
    customers = [u for u in users if (u.to_dict() or {}).get("role") != "admin"]

    print()
    print("=" * 60)
    print(
        f"Migration complete. {len(users)} user(s) "
        f"({len(admins)} admin, {len(customers)} customer)"
    )
    if promoted:
        print()
        print("Admins promoted:")
        for line in promoted:
            print(f"  - {line}")
    print()
    print("Set this in Mac Mini .env (replacing EMAIL2PPT_CUSTOMER_UID):")
    if admins:
        print(f"  EMAIL2PPT_USER_UID={admins[0].id}")
    else:
        print("  (no admin uid found — promote one manually)")
    print("=" * 60)


if __name__ == "__main__":
    main()
