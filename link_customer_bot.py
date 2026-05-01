#!/usr/bin/env python3
"""Link a Telegram chat to a portal user's customerBot field.

Usage:
  python link_customer_bot.py <uid>            # auto-pick most recent chat
  python link_customer_bot.py <uid> <chatId>   # use a specific chatId

Reads TELEGRAM_BOT_TOKEN from .env, calls getUpdates to find seen chats,
and writes users/{uid}.customerBot via Firebase Admin SDK (bypassing the
portal wizard and Firestore security rules).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import requests

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

from firestore_alerts import _firestore_client  # noqa: E402
from firebase_admin import firestore as admin_firestore  # noqa: E402

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def get_me() -> dict:
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=10)
    return r.json()


def get_updates() -> list[dict]:
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=10)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"getUpdates failed: {j}")
    return j.get("result", [])


def latest_chats() -> dict[int, dict]:
    """Returns {chatId: chat} for chats seen in current update window."""
    seen: dict[int, dict] = {}
    for u in get_updates():
        msg = u.get("message") or u.get("edited_message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is not None:
            seen[cid] = chat
    return seen


def main(argv: list[str]) -> int:
    if not TOKEN:
        print("FATAL: TELEGRAM_BOT_TOKEN not set in .env", file=sys.stderr)
        return 1
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    uid = argv[1].strip()
    explicit_chat = int(argv[2]) if len(argv) >= 3 else None

    me = get_me()
    if not me.get("ok"):
        print(f"getMe failed: {me}", file=sys.stderr)
        return 1
    bot_username = me["result"].get("username")
    print(f"bot=@{bot_username}")

    db = _firestore_client()
    user_ref = db.collection("users").document(uid)
    snap = user_ref.get()
    if not snap.exists:
        print(f"FATAL: users/{uid} does not exist", file=sys.stderr)
        return 1
    udata = snap.to_dict() or {}
    print(f"user uid={uid} email={(udata.get('gmail') or {}).get('email')}")

    if explicit_chat is not None:
        chat_id = explicit_chat
        chat_type = "private"
        chat_username = None
        print(f"using explicit chatId={chat_id}")
    else:
        chats = latest_chats()
        if not chats:
            print("getUpdates returned no chats. Have the user send a fresh message")
            print(f"to @{bot_username} in Telegram, then re-run this script.")
            return 1
        if len(chats) > 1:
            print("Multiple chats seen, pick one and pass it as the second arg:")
            for cid, c in chats.items():
                label = c.get("username") or c.get("first_name") or c.get("title")
                print(f"  chatId={cid} type={c.get('type')} label={label}")
            return 1
        chat_id, chat = next(iter(chats.items()))
        chat_type = chat.get("type", "private")
        chat_username = chat.get("username")
        label = chat_username or chat.get("first_name") or chat.get("title")
        print(f"detected chatId={chat_id} type={chat_type} label={label}")

    payload = {
        "customerBot": {
            "token": TOKEN,
            "username": bot_username,
            "chatId": chat_id,
            "chatType": chat_type,
            "linkedAt": admin_firestore.SERVER_TIMESTAMP,
        }
    }
    user_ref.set(payload, merge=True)
    print(f"wrote users/{uid}.customerBot")

    verify = user_ref.get().to_dict() or {}
    cb = verify.get("customerBot") or {}
    print(
        f"verify: username=@{cb.get('username')} chatId={cb.get('chatId')} type={cb.get('chatType')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
