#!/usr/bin/env python3
"""Weekly health check for the email watcher. Sends a summary to Telegram."""

import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AUTHORIZED_CHAT_ID = int(os.environ["AUTHORIZED_CHAT_ID"])

STATE_FILE = BASE_DIR / "watcher_state.json"
LOG_FILE = BASE_DIR / "watcher.stderr.log"
PDF_DIR = Path.home() / "email-pdfs"
WINDOW_DAYS = 7
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(
        url,
        data={"chat_id": AUTHORIZED_CHAT_ID, "text": text[:4000]},
        timeout=30,
    )


def state_summary() -> str:
    if not STATE_FILE.exists():
        return "state: missing ❌"
    try:
        ids = json.loads(STATE_FILE.read_text()).get("processed_ids", [])
    except (json.JSONDecodeError, OSError) as exc:
        return f"state: unreadable ({exc.__class__.__name__})"
    dup = "" if len(ids) == len(set(ids)) else " ⚠ duplicates"
    return f"state: {len(ids)}/200 ids{dup}"


def log_summary(cutoff: datetime) -> tuple[str, str | None]:
    if not LOG_FILE.exists():
        return "log: missing ❌", None
    runs = errors = 0
    last_traceback: list[str] = []
    in_traceback = False
    sample: str | None = None
    with LOG_FILE.open("r", errors="replace") as f:
        for line in f:
            m = TS_RE.match(line)
            if m:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                if ts < cutoff:
                    in_traceback = False
                    continue
                if "Watcher run starting" in line:
                    runs += 1
                if in_traceback:
                    in_traceback = False
                    if not sample:
                        sample = "".join(last_traceback)[-500:]
            if line.startswith("Traceback"):
                errors += 1
                in_traceback = True
                last_traceback = [line]
            elif in_traceback:
                last_traceback.append(line)
    return f"runs: {runs}, tracebacks: {errors}", sample


def pdf_summary(cutoff: datetime) -> str:
    if not PDF_DIR.exists():
        return "pdfs: dir missing"
    recent = [p for p in PDF_DIR.iterdir() if p.is_file() and datetime.fromtimestamp(p.stat().st_mtime) >= cutoff]
    total = sum(1 for p in PDF_DIR.iterdir() if p.is_file())
    return f"pdfs: {len(recent)} new in {WINDOW_DAYS}d ({total} total)"


def main() -> None:
    now = datetime.now()
    cutoff = now - timedelta(days=WINDOW_DAYS)
    log_line, traceback_sample = log_summary(cutoff)
    parts = [
        f"📋 email2ppt weekly health ({now:%Y-%m-%d %H:%M})",
        state_summary(),
        log_line,
        pdf_summary(cutoff),
    ]
    if traceback_sample:
        parts.append(f"\nLast traceback:\n{traceback_sample}")
    send_telegram("\n".join(parts))


if __name__ == "__main__":
    main()
