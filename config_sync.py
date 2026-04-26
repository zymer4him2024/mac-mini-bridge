#!/usr/bin/env python3
"""Pull email2ppt config from Firestore and apply to local files.

Reads doc `config/email2ppt` and writes:
  - priority_senders.txt   (one address per line, same shape watcher.py/digest.py expect)
  - watcher_config.json    ({"lookback": "<gmail newer_than: value>"})

Runs every 5 min via LaunchAgent. On any field diff, sends a Telegram ping so
config changes have a visible audit trail.
"""

import os
import sys
import json
import logging
from pathlib import Path

import requests
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core import exceptions as gax

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AUTHORIZED_CHAT_ID = int(os.environ["AUTHORIZED_CHAT_ID"])

SERVICE_ACCOUNT = BASE_DIR / "firebase-service-account.json"
SENDERS_FILE = BASE_DIR / "priority_senders.txt"
WATCHER_CONFIG = BASE_DIR / "watcher_config.json"
DOC_PATH = ("config", "email2ppt")
FIRESTORE_DB_ID = os.environ.get("FIRESTORE_DATABASE_ID", "email2ppt")

DEFAULT_LOOKBACK = "1d"

LOG_PATH = BASE_DIR / "config_sync.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("config_sync")


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(
        url,
        data={"chat_id": AUTHORIZED_CHAT_ID, "text": text[:4000]},
        timeout=30,
    )


def read_local_senders() -> list[str]:
    if not SENDERS_FILE.exists():
        return []
    return [
        line.strip()
        for line in SENDERS_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def read_local_lookback() -> str:
    if not WATCHER_CONFIG.exists():
        return DEFAULT_LOOKBACK
    try:
        return json.loads(WATCHER_CONFIG.read_text()).get("lookback", DEFAULT_LOOKBACK)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("watcher_config.json unreadable (%s); treating as default", exc)
        return DEFAULT_LOOKBACK


def fetch_remote() -> dict | None:
    if not SERVICE_ACCOUNT.exists():
        log.error("service account missing: %s", SERVICE_ACCOUNT)
        sys.exit(1)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(SERVICE_ACCOUNT)))
    db = firestore.client(database_id=FIRESTORE_DB_ID)
    try:
        snap = db.collection(DOC_PATH[0]).document(DOC_PATH[1]).get()
    except gax.GoogleAPIError as exc:
        log.warning("Firestore unreachable (%s); skipping run", exc)
        return None
    if not snap.exists:
        log.warning("doc %s/%s does not exist; skipping run", *DOC_PATH)
        return None
    return snap.to_dict() or {}


def normalize_remote(doc: dict) -> tuple[list[str], str]:
    senders = doc.get("priorityWatchSenders", [])
    if not isinstance(senders, list) or not all(isinstance(s, str) for s in senders):
        log.warning("priorityWatchSenders is not list[str]; ignoring field")
        senders = read_local_senders()
    senders = [s.strip().lower() for s in senders if s.strip()]
    senders = sorted(set(senders))

    lookback = doc.get("watcherLookback", DEFAULT_LOOKBACK)
    if not isinstance(lookback, str) or not lookback.strip():
        log.warning("watcherLookback is not a non-empty string; using default")
        lookback = DEFAULT_LOOKBACK
    return senders, lookback.strip()


def write_senders(senders: list[str]) -> None:
    SENDERS_FILE.write_text("\n".join(senders) + "\n")


def write_lookback(lookback: str) -> None:
    WATCHER_CONFIG.write_text(json.dumps({"lookback": lookback}, indent=2) + "\n")


def main() -> None:
    log.info("=" * 60)
    log.info("config_sync starting")

    doc = fetch_remote()
    if doc is None:
        return
    remote_senders, remote_lookback = normalize_remote(doc)
    local_senders = sorted(set(s.lower() for s in read_local_senders()))
    local_lookback = read_local_lookback()

    diffs: list[str] = []
    if remote_senders != local_senders:
        added = set(remote_senders) - set(local_senders)
        removed = set(local_senders) - set(remote_senders)
        write_senders(remote_senders)
        diffs.append(f"senders: +{len(added)} -{len(removed)} (now {len(remote_senders)})")
        log.info("senders updated: added=%s removed=%s", sorted(added), sorted(removed))

    if remote_lookback != local_lookback:
        write_lookback(remote_lookback)
        diffs.append(f"lookback: {local_lookback} → {remote_lookback}")
        log.info("lookback updated: %s → %s", local_lookback, remote_lookback)

    initial = not WATCHER_CONFIG.exists() or not SENDERS_FILE.exists()
    if initial and not diffs:
        write_senders(remote_senders)
        write_lookback(remote_lookback)
        diffs.append("initial sync")

    if diffs:
        send_telegram("⚙️ email2ppt config synced\n" + "\n".join(diffs))
        log.info("diffs applied: %s", diffs)
    else:
        log.info("no changes")


if __name__ == "__main__":
    main()
