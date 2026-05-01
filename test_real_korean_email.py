#!/usr/bin/env python3
"""End-to-end test: pull a real Korean email from a linked Gmail account and
run it through the new summarization pipeline.

Verifies the full path:
  RFC2047 header decode → charset-aware body extract → language-directive
  injection → Gemma summary in Korean.

Usage: venv/bin/python test_real_korean_email.py [UID]
  If UID omitted, picks the first linked user.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

from openai import OpenAI  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402

import watcher  # noqa: E402
from firestore_activity import get_db  # noqa: E402
from firestore_users import (  # noqa: E402
    enumerate_linked_users,
    load_user_config,
    load_user_credentials,
)
from mime_extract import extract_body, decode_header_value  # noqa: E402
from lang_hint import detect_dominant_script  # noqa: E402


def main() -> int:
    db = get_db()

    if len(sys.argv) >= 2:
        uid = sys.argv[1]
    else:
        uids = enumerate_linked_users(db)
        if not uids:
            print("no linked users", file=sys.stderr)
            return 1
        uid = uids[0]
    print(f"uid: {uid}")

    cfg = load_user_config(db, uid)
    print(f"summaryPersona: {cfg.get('summaryPersona')!r}")
    print(f"displayName:    {cfg.get('displayName')!r}")

    creds = load_user_credentials(db, uid)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # Search broadly; we'll filter client-side on actual Hangul content.
    queries = [
        "lang:ko newer_than:90d",
        "newer_than:14d",  # widest fallback — scan recent inbox
    ]
    chosen = None
    for q in queries:
        print(f"query: {q}")
        result = (
            service.users().messages().list(userId="me", q=q, maxResults=30).execute()
        )
        msgs = result.get("messages", [])
        print(f"  candidates: {len(msgs)}")
        for m in msgs:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=m["id"], format="full")
                .execute()
            )
            payload = msg.get("payload") or {}
            headers = {h["name"]: h["value"] for h in payload.get("headers") or []}
            body = extract_body(payload)
            if detect_dominant_script(body) == "korean":
                chosen = (msg, payload, headers, body)
                break
        if chosen:
            break
    if not chosen:
        print("no email with dominant Korean body found", file=sys.stderr)
        return 1
    msg, payload, headers, body = chosen

    subject = decode_header_value(headers.get("Subject", "")) or "(no subject)"
    sender = decode_header_value(headers.get("From", ""))
    date = headers.get("Date", "")

    print()
    print("=" * 70)
    print("REAL KOREAN EMAIL")
    print("=" * 70)
    print(f"From:    {sender}")
    print(f"Subject: {subject}")
    print(f"Date:    {date}")
    print(f"Script:  {detect_dominant_script(body)}")
    print()
    print("Body excerpt (first 600 chars, after charset-aware decode):")
    print("-" * 70)
    print(body[:600])
    print("-" * 70)

    email = {
        "id": msg["id"],
        "from": sender,
        "subject": subject,
        "date": date,
        "body": body[:8000],
    }

    print()
    print("=" * 70)
    print("SUMMARIZING via gemma4:e4b")
    print("=" * 70)
    print(f"OLLAMA_BASE_URL: {os.environ.get('OLLAMA_BASE_URL')}")
    print(f"OLLAMA_MODEL:    {os.environ.get('OLLAMA_MODEL')}")
    print()

    client = OpenAI(
        base_url=watcher.OLLAMA_BASE_URL, api_key="ollama-local", timeout=120
    )
    summary = watcher.summarize_email(client, email, cfg)
    print("Summary JSON:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    pdf_path = Path("/tmp/test_korean.pdf")
    watcher.build_pdf(email, summary, pdf_path)
    print()
    print(f"PDF written: {pdf_path}  ({pdf_path.stat().st_size} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
