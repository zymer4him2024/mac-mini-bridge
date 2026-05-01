#!/usr/bin/env python3
"""Manual test for persona-aware summarization.

Verifies:
  1. _build_system_message produces correct shape with/without persona.
  2. mime_extract: charset-aware body decode + RFC2047 header decode.
  3. Live: Korean email + persona='use same language' → JSON values in Korean.
  4. Live: English email + no persona → JSON values in English (control).

Live tests hit Ollama at OLLAMA_BASE_URL with OLLAMA_MODEL.
Run: python3 test_persona_summary.py
"""

import base64
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

from openai import OpenAI  # noqa: E402

import watcher  # noqa: E402
from mime_extract import extract_body, decode_header_value  # noqa: E402


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def _b64url(data: bytes) -> str:
    """Gmail returns urlsafe-b64 *with* padding."""
    return base64.urlsafe_b64encode(data).decode("ascii")


def test_unit_mime_extract() -> None:
    section("UNIT: mime_extract")

    # 1. multipart/alternative: text/plain (UTF-8) + text/html → plain wins
    plain_payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Content-Type", "value": "text/plain; charset=utf-8"}
                ],
                "body": {"data": _b64url("Hello world".encode("utf-8"))},
            },
            {
                "mimeType": "text/html",
                "headers": [
                    {"name": "Content-Type", "value": "text/html; charset=utf-8"}
                ],
                "body": {"data": _b64url(b"<p>Hello <b>world</b></p>")},
            },
        ],
    }
    out = extract_body(plain_payload)
    assert out.strip() == "Hello world", f"plain-preferred: got {out!r}"
    print("plain-preferred: PASS")

    # 2. text/plain in EUC-KR → returns Korean unicode
    korean = "안녕하세요. 한국어 테스트입니다."
    euckr_payload = {
        "mimeType": "text/plain",
        "headers": [{"name": "Content-Type", "value": "text/plain; charset=euc-kr"}],
        "body": {"data": _b64url(korean.encode("euc_kr"))},
    }
    out = extract_body(euckr_payload)
    assert out == korean, f"euc-kr decode: got {out!r}"
    print("euc-kr decode: PASS")

    # 3. text/plain in CP949 (declared as ks_c_5601-1987) → returns Korean unicode
    cp949_payload = {
        "mimeType": "text/plain",
        "headers": [
            {"name": "Content-Type", "value": 'text/plain; charset="ks_c_5601-1987"'}
        ],
        "body": {"data": _b64url(korean.encode("cp949"))},
    }
    out = extract_body(cp949_payload)
    assert out == korean, f"ks_c_5601-1987 decode: got {out!r}"
    print("ks_c_5601-1987 alias → cp949: PASS")

    # 4. HTML-only payload → tags stripped, entities decoded
    html_only_payload = {
        "mimeType": "text/html",
        "headers": [{"name": "Content-Type", "value": "text/html; charset=utf-8"}],
        "body": {
            "data": _b64url(
                b"<html><body><p>Hello&nbsp;<b>world</b></p>"
                b"<script>alert('x')</script>"
                b"<p>Line two &amp; more</p></body></html>"
            ),
        },
    }
    out = extract_body(html_only_payload)
    assert "Hello" in out and "world" in out, f"html strip: got {out!r}"
    assert "alert" not in out, f"script not stripped: {out!r}"
    assert "&amp;" not in out and "&" in out, f"entities not decoded: {out!r}"
    assert "<" not in out and ">" not in out, f"tags not stripped: {out!r}"
    print("html-only strip + entity decode: PASS")

    # 5. RFC 2047 header decode: EUC-KR encoded subject
    encoded_subject = (
        "=?euc-kr?B?"
        + base64.b64encode("다음 주 미팅".encode("euc_kr")).decode("ascii")
        + "?="
    )
    decoded = decode_header_value(encoded_subject)
    assert decoded == "다음 주 미팅", f"rfc2047 euc-kr: got {decoded!r}"
    print("rfc2047 euc-kr subject: PASS")

    # 6. RFC 2047 header decode: UTF-8 encoded From with display name
    encoded_from = (
        "=?UTF-8?B?"
        + base64.b64encode("김지훈".encode("utf-8")).decode("ascii")
        + "?= <jihoon@example.com>"
    )
    decoded = decode_header_value(encoded_from)
    assert (
        "김지훈" in decoded and "jihoon@example.com" in decoded
    ), f"rfc2047 utf-8: got {decoded!r}"
    print("rfc2047 utf-8 from: PASS")

    # 7. Plain ASCII subject (no encoding) → passthrough
    assert decode_header_value("Plain Subject") == "Plain Subject"
    assert decode_header_value("") == ""
    print("rfc2047 passthrough: PASS")


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
    test_unit_mime_extract()
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
