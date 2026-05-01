#!/usr/bin/env python3
"""One-shot backfill: rewrite users/{uid}/folders/*.folderPath so the host
path segment uses the user's gmail address instead of the opaque uid.

The watcher started writing PDFs to ~/email-pdfs/{email}/{slug}/ in commit
f1cd6b8, but folder docs created before that commit still hold the old
~/email-pdfs/{uid}/{slug}/ string. The dashboard's "Path on host" column
reads this field, so old docs keep showing uids until the watcher reprocesses
those subjects.

Usage:
  python backfill_folder_paths.py            # dry-run
  python backfill_folder_paths.py --apply    # write to Firestore
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

from firestore_activity import get_db  # noqa: E402
from firestore_state import load_user_self_email  # noqa: E402
from firestore_users import enumerate_linked_users  # noqa: E402


def main(argv: list[str]) -> int:
    apply = "--apply" in argv

    db = get_db()
    uids = enumerate_linked_users(db)
    print(f"Users with gmail.email set: {len(uids)}")
    print()

    rewrites = 0
    skipped_no_email = 0
    skipped_no_uid_in_path = 0

    for uid in uids:
        email = load_user_self_email(db, uid)
        if not email:
            skipped_no_email += 1
            print(f"uid={uid}: no gmail.email; skipping all folders")
            continue

        folders_ref = db.collection("users").document(uid).collection("folders")
        for snap in folders_ref.stream():
            data = snap.to_dict() or {}
            old_path = data.get("folderPath") or ""
            if not old_path or f"/{uid}/" not in old_path:
                skipped_no_uid_in_path += 1
                continue

            new_path = old_path.replace(f"/{uid}/", f"/{email}/", 1)
            print(f"uid={uid} folder={snap.id}")
            print(f"  before: {old_path}")
            print(f"  after:  {new_path}")
            rewrites += 1

            if apply:
                snap.reference.set({"folderPath": new_path}, merge=True)

    print()
    print(f"rewrites: {rewrites}")
    print(f"skipped (no email): {skipped_no_email}")
    print(f"skipped (uid not in path): {skipped_no_uid_in_path}")
    if not apply:
        print("Dry-run only. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
