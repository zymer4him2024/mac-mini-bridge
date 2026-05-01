#!/usr/bin/env python3
"""One-shot backfill: copy local priority_senders.txt + watcher_config.json
into users/{uid}/config/main.priorityWatchSenders and .watcherLookback for
every user with gmail.email set.

Run once before deploying the per-user-config refactor. Idempotent: re-running
overwrites any existing fields with the local file values.

Usage:
  python backfill_user_config.py            # dry-run: print what would change
  python backfill_user_config.py --apply    # write to Firestore
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

from firestore_activity import get_db  # noqa: E402
from firestore_users import enumerate_linked_users  # noqa: E402

SENDERS_FILE = BASE_DIR / "priority_senders.txt"
WATCHER_CONFIG = BASE_DIR / "watcher_config.json"


def read_local_senders() -> list[str]:
    if not SENDERS_FILE.exists():
        return []
    out = []
    for line in SENDERS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.lower())
    return sorted(set(out))


def read_local_lookback() -> str:
    if not WATCHER_CONFIG.exists():
        return "1d"
    try:
        v = json.loads(WATCHER_CONFIG.read_text()).get("lookback", "1d")
    except (json.JSONDecodeError, OSError):
        return "1d"
    return v if isinstance(v, str) and v.strip() else "1d"


def main(argv: list[str]) -> int:
    apply = "--apply" in argv

    senders = read_local_senders()
    lookback = read_local_lookback()
    print(f"Local senders ({len(senders)}): {senders}")
    print(f"Local lookback: {lookback}")
    print()

    db = get_db()
    uids = enumerate_linked_users(db)
    print(f"Users with gmail.email set ({len(uids)}): {uids}")
    print()

    for uid in uids:
        ref = db.collection("users").document(uid).collection("config").document("main")
        snap = ref.get()
        existing = snap.to_dict() if snap.exists else {}
        cur_senders = existing.get("priorityWatchSenders", [])
        cur_lookback = existing.get("watcherLookback", "(unset)")
        cur_enabled = existing.get("digestEnabled", "(unset)")
        print(f"uid={uid}")
        print(f"  before: senders={cur_senders}")
        print(f"          lookback={cur_lookback}")
        print(f"          digestEnabled={cur_enabled}")

        payload = {
            "priorityWatchSenders": senders,
            "watcherLookback": lookback,
        }
        if cur_enabled == "(unset)":
            payload["digestEnabled"] = True

        if apply:
            ref.set(payload, merge=True)
            print(f"  WROTE {payload}")
        else:
            print(f"  WOULD WRITE {payload}")
        print()

    if not apply:
        print("Dry-run only. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
