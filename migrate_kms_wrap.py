#!/usr/bin/env python3
"""One-shot migration: KMS-wrap every plaintext token in Firestore.

Run AFTER `KMS_KEY_NAME` is set in `.env` and the worker service account
has `roles/cloudkms.cryptoKeyEncrypterDecrypter` on the key.

Idempotent: a value already prefixed with `kms:v1:` is left alone.

Touched fields:

  - `users/{uid}/secrets/gmail.refreshToken`
  - `users/{uid}.customerBot.token`

Re-run safe. Prints a summary of how many docs were wrapped vs already
wrapped vs skipped.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore

from kms_envelope import CIPHERTEXT_PREFIX, kms_configured, wrap_token

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

SERVICE_ACCOUNT = BASE_DIR / "firebase-service-account.json"
FIRESTORE_DB_ID = os.environ.get("FIRESTORE_DATABASE_ID", "email2ppt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("migrate_kms_wrap")


def _client():
    if not SERVICE_ACCOUNT.exists():
        log.error("service account missing: %s", SERVICE_ACCOUNT)
        sys.exit(1)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(SERVICE_ACCOUNT)))
    return firestore.client(database_id=FIRESTORE_DB_ID)


def main() -> None:
    if not kms_configured():
        log.error("KMS_KEY_NAME is not set; refusing to migrate")
        sys.exit(2)

    db = _client()
    refresh_wrapped = refresh_skipped = bot_wrapped = bot_skipped = 0

    for snap in db.collection("users").stream():
        uid = snap.id
        data = snap.to_dict() or {}

        # 1. customerBot.token
        bot = data.get("customerBot") or {}
        token = bot.get("token")
        if isinstance(token, str) and token:
            if token.startswith(CIPHERTEXT_PREFIX):
                bot_skipped += 1
            else:
                wrapped = wrap_token(token)
                db.collection("users").document(uid).set(
                    {"customerBot": {"token": wrapped}}, merge=True
                )
                bot_wrapped += 1
                log.info("uid=%s customerBot.token wrapped", uid)

        # 2. secrets/gmail.refreshToken
        secret_ref = (
            db.collection("users").document(uid).collection("secrets").document("gmail")
        )
        secret_snap = secret_ref.get()
        if secret_snap.exists:
            sdata = secret_snap.to_dict() or {}
            rt = sdata.get("refreshToken")
            if isinstance(rt, str) and rt:
                if rt.startswith(CIPHERTEXT_PREFIX):
                    refresh_skipped += 1
                else:
                    wrapped = wrap_token(rt)
                    secret_ref.set({"refreshToken": wrapped}, merge=True)
                    refresh_wrapped += 1
                    log.info("uid=%s secrets/gmail.refreshToken wrapped", uid)

    log.info(
        "done. refresh_wrapped=%d refresh_skipped=%d bot_wrapped=%d bot_skipped=%d",
        refresh_wrapped,
        refresh_skipped,
        bot_wrapped,
        bot_skipped,
    )


if __name__ == "__main__":
    main()
