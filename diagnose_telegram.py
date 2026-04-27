#!/usr/bin/env python3
"""Diagnose Telegram routing for portal-linked users.

Prints, in order:
  1. Bot identity (getMe) for the shared TELEGRAM_BOT_TOKEN.
  2. Chats the bot has seen recently (getUpdates).
  3. Each user in Firestore: gmail.email, role, customerBot status.

Run on Mac Mini (where firebase-service-account.json + .env live).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import requests

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

from firestore_alerts import _firestore_client  # noqa: E402

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def get_me() -> dict:
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=10)
    return r.json()


def get_updates() -> dict:
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=10)
    return r.json()


def main() -> int:
    if not TOKEN:
        print("FATAL: TELEGRAM_BOT_TOKEN not set in .env", file=sys.stderr)
        return 1

    section("Bot identity (getMe)")
    me = get_me()
    if not me.get("ok"):
        print(f"getMe failed: {me}")
        return 1
    bot = me["result"]
    print(f"id={bot.get('id')} username=@{bot.get('username')} name={bot.get('first_name')}")

    section("Recent chats seen by bot (getUpdates)")
    upd = get_updates()
    if not upd.get("ok"):
        print(f"getUpdates failed: {upd}")
        return 1
    seen: dict[int, dict] = {}
    for u in upd.get("result", []):
        msg = u.get("message") or u.get("edited_message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is None:
            continue
        seen[cid] = chat
    if not seen:
        print("(no recent updates — Telegram only retains updates for ~24h)")
        print("If gil4him already pressed Detect, his message was consumed and dropped.")
        print("To re-test: open @%s in Telegram, send a fresh message, then re-run." % bot.get('username'))
    else:
        for cid, chat in seen.items():
            label = chat.get("username") or chat.get("first_name") or chat.get("title") or "?"
            print(f"chatId={cid} type={chat.get('type')} label={label}")

    section("Firestore users")
    db = _firestore_client()
    for snap in db.collection("users").stream():
        data = snap.to_dict() or {}
        email = (data.get("gmail") or {}).get("email") or data.get("email") or "(none)"
        cb = data.get("customerBot") or {}
        cb_state = "set" if cb.get("token") else "(empty)"
        if cb.get("token"):
            cb_state += f" username=@{cb.get('username')} chatId={cb.get('chatId')} type={cb.get('chatType')}"
        print(f"uid={snap.id}")
        print(f"  email={email}  role={data.get('role')}")
        print(f"  customerBot={cb_state}")

    section("Suggested next action")
    if seen:
        print("Pick a chatId from the seen list above that belongs to gil4him,")
        print("then run write_customerbot.py <uid> <chatId> to link it.")
    else:
        print("Have gil4him send a fresh message to @%s in Telegram, then re-run." % bot.get('username'))

    return 0


if __name__ == "__main__":
    sys.exit(main())
