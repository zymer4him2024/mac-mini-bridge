#!/usr/bin/env python3
"""Manual test for persona-aware summarization.

Verifies:
  1. _build_system_message produces correct shape with/without persona.
  2. Live: Korean email + persona='use same language' → JSON values in Korean.
  3. Live: English email + no persona → JSON values in English (control).

Live tests hit Ollama at OLLAMA_BASE_URL with OLLAMA_MODEL.
Run: python3 test_persona_summary.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

from openai import OpenAI  # noqa: E402

import watcher  # noqa: E402


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def test_unit_system_message() -> None:
    section("UNIT: watcher._build_system_message")

    default = watcher._build_system_message({})
    with_persona = watcher._build_system_message(
        {"summaryPersona": "Use the same language as the original contents."}
    )

    print(f"default        = {default!r}")
    print(f"with persona   = {with_persona!r}")

    assert "Additional instructions" not in default, "default leaked persona block"
    assert default == watcher.DEFAULT_PERSONA_LINE
    assert "Additional instructions: Use the same language" in with_persona
    assert with_persona.startswith(watcher.DEFAULT_PERSONA_LINE)

    print("PASS")


def test_live_korean_with_persona(client: OpenAI) -> None:
    section("LIVE: Korean email + 'use same language' persona")
    print("Expected: JSON string values in Korean (context, key_points, asks, ...)")

    email = {
        "from": "김지훈 <jihoon.kim@acme.co.kr>",
        "subject": "다음 주 화요일 미팅 일정 조정 요청",
        "date": "Mon, 28 Apr 2026 10:15:00 +0900",
        "body": (
            "안녕하세요. 다음 주 화요일 오후 3시에 예정되어 있던 미팅을 "
            "수요일 오전 10시로 변경할 수 있을까요? 갑작스러운 출장 일정이 잡혀서 "
            "조정이 필요합니다. 변경 가능하시면 알려주시고, 어렵다면 다른 시간을 "
            "제안해 주시기 바랍니다. 또한 지난번 논의한 견적서 1억 5천만원 건은 "
            "내부 검토가 마무리되어 다음 주 금요일까지 회신드릴 예정입니다.\n\n"
            "감사합니다.\n김지훈"
        ),
    }
    cfg = {
        "summaryPersona": "Use the same language as the original email content for all values.",
        "summaryKeyPointsMax": 6,
        "summaryAsksMax": 4,
    }

    print(f"\nmodel: {os.environ.get('OLLAMA_MODEL')}")
    print(f"system_msg:\n  {watcher._build_system_message(cfg)}\n")

    summary = watcher.summarize_email(client, email, cfg)
    print("Summary JSON:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def test_live_english_no_persona(client: OpenAI) -> None:
    section("LIVE (control): English email + no persona")
    print("Expected: JSON string values in English; default behaviour preserved.")

    email = {
        "from": "Jane Doe <jane@example.com>",
        "subject": "Quick question about Q3 numbers",
        "date": "Mon, 28 Apr 2026 10:15:00 +0000",
        "body": (
            "Hi — could you share the Q3 revenue figures we discussed last "
            "Friday? Need them for the board deck on Wednesday. Also, the "
            "$120K proposal from Acme is now approved by legal, so we can "
            "move forward when you're ready."
        ),
    }
    cfg: dict = {}

    summary = watcher.summarize_email(client, email, cfg)
    print("Summary JSON:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    test_unit_system_message()

    base_url = os.environ.get("OLLAMA_BASE_URL")
    if not base_url:
        print("\nSKIP live tests: OLLAMA_BASE_URL not set", file=sys.stderr)
        return 0

    client = OpenAI(base_url=base_url, api_key="ollama-local")

    try:
        test_live_korean_with_persona(client)
        test_live_english_no_persona(client)
    except Exception as exc:  # noqa: BLE001 - surface the real error to operator
        print(f"\nLIVE TEST ERROR: {exc!r}", file=sys.stderr)
        return 1

    print()
    print("=" * 70)
    print("Done. Eyeball Korean output above — values should be in Korean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
