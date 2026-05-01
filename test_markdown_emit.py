#!/usr/bin/env python3
"""Unit tests for the per-email markdown emission seam.

Covers:
  1. build_markdown_body — section ordering, omitted-when-empty rules,
     UTF-8 round-trip, defaults for missing fields.
  2. upload_markdown — happy path, validation guards, GCS-client failures,
     content-type, and the exact `summaries/{uid}/{slug}/{id}.md` layout
     the web reader expects.

Pure Python; no network. Run: python3 test_markdown_emit.py
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from google.api_core import exceptions as gax

import firebase_storage
from mime_extract import build_markdown_body


def _section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def test_body_full_summary() -> None:
    _section("UNIT: build_markdown_body — full summary")
    email = {
        "subject": "Q3 numbers",
        "from": "Jane Doe <jane@example.com>",
        "date": "Mon, 28 Apr 2026 10:15:00 +0000",
        "body": "Hi — please share the Q3 revenue figures.",
    }
    summary = {
        "urgency": "high",
        "key_points": ["Need Q3 revenue", "For board deck"],
        "asks": ["Send numbers by Wed"],
        "suggested_response": "Will send by Tuesday EOD.",
    }
    out = build_markdown_body(email, summary)

    assert out.startswith("# Q3 numbers\n"), f"missing H1: {out!r}"
    assert "- **From:** Jane Doe <jane@example.com>" in out
    assert "- **Date:** Mon, 28 Apr 2026 10:15:00 +0000" in out
    assert "- **Urgency:** high" in out
    assert "## Key points\n- Need Q3 revenue\n- For board deck\n" in out
    assert "## Asks\n- Send numbers by Wed\n" in out
    assert "## Suggested response\n\nWill send by Tuesday EOD." in out
    assert (
        "---\n\n## Original message\n\nHi — please share the Q3 revenue figures.\n"
        in out
    )
    # H1 must come before Key points; Key points before Asks
    assert out.index("# Q3 numbers") < out.index("## Key points") < out.index("## Asks")
    print("full-summary structure: PASS")


def test_body_omits_empty_sections() -> None:
    _section("UNIT: build_markdown_body — omit empty list sections")
    email = {
        "subject": "Just an FYI",
        "from": "ops@example.com",
        "date": "Tue, 29 Apr 2026 09:00:00 +0000",
        "body": "Heads-up: maintenance window tonight.",
    }
    summary = {
        "urgency": "low",
        "key_points": [],
        "asks": [],
        "suggested_response": "",
    }
    out = build_markdown_body(email, summary)

    assert "## Key points" not in out, "key-points header leaked despite empty list"
    assert "## Asks" not in out, "asks header leaked despite empty list"
    # Suggested response header stays — blank body is itself a result
    assert "## Suggested response" in out
    assert "## Original message" in out
    print("empty-list omission: PASS")


def test_body_korean_utf8() -> None:
    _section("UNIT: build_markdown_body — Korean UTF-8 round-trip")
    email = {
        "subject": "다음 주 화요일 미팅 일정 조정 요청",
        "from": "김지훈 <jihoon.kim@acme.co.kr>",
        "date": "Mon, 28 Apr 2026 10:15:00 +0900",
        "body": "안녕하세요. 다음 주 화요일 오후 3시 미팅을 수요일로 변경할 수 있을까요?",
    }
    summary = {
        "urgency": "med",
        "key_points": ["미팅 일정 변경 요청", "출장 일정 충돌"],
        "asks": ["수요일 오전 가능 여부 알려달라"],
        "suggested_response": "수요일 오전 10시로 변경 가능합니다.",
    }
    out = build_markdown_body(email, summary)

    assert "다음 주 화요일 미팅 일정 조정 요청" in out
    assert "김지훈" in out
    assert "미팅 일정 변경 요청" in out
    # Round-trips to bytes cleanly (no surrogates / undecodable code points)
    assert out.encode("utf-8").decode("utf-8") == out
    print("korean utf-8 round-trip: PASS")


def test_body_handles_missing_fields() -> None:
    _section("UNIT: build_markdown_body — defensive defaults")
    out = build_markdown_body({}, {})
    assert out.startswith("# (no subject)\n"), f"missing-subject default lost: {out!r}"
    assert "- **Urgency:** low" in out, "missing-urgency default lost"
    assert "## Key points" not in out
    assert "## Asks" not in out
    assert "## Original message" in out
    # Trailing newline is the only whitespace at EOF — no double-blank tail
    assert out.endswith("\n") and not out.endswith("\n\n")
    print("defensive defaults: PASS")


def _make_fake_client() -> tuple[MagicMock, MagicMock]:
    """Returns (client, blob) — blob lets the test assert upload args."""
    blob = MagicMock(name="blob")
    bucket = MagicMock(name="bucket")
    bucket.blob.return_value = blob
    client = MagicMock(name="gcs_client")
    client.bucket.return_value = bucket
    return client, blob


def test_upload_happy_path() -> None:
    _section("UNIT: upload_markdown — happy path")
    client, blob = _make_fake_client()

    with patch.object(firebase_storage, "_get_client", return_value=client):
        out = firebase_storage.upload_markdown(
            "uid-abc", "acme-deal", "2026-04-29-103000-jane", "# Hello\n\nBody."
        )

    expected = "summaries/uid-abc/acme-deal/2026-04-29-103000-jane.md"
    assert out == expected, f"unexpected path: {out!r}"
    blob.upload_from_string.assert_called_once_with(
        "# Hello\n\nBody.", content_type="text/markdown"
    )
    client.bucket.assert_called_once()
    print(f"happy path returned {out}: PASS")


def test_upload_rejects_empty_args() -> None:
    _section("UNIT: upload_markdown — guards on empty inputs")
    # Should never even touch the client when required args are blank.
    sentinel = MagicMock(name="should_not_be_called")
    with patch.object(firebase_storage, "_get_client", return_value=sentinel):
        assert firebase_storage.upload_markdown("", "slug", "id", "x") is None
        assert firebase_storage.upload_markdown("uid", "", "id", "x") is None
        assert firebase_storage.upload_markdown("uid", "slug", "", "x") is None
    sentinel.bucket.assert_not_called()
    print("empty-arg guards: PASS")


def test_upload_handles_missing_client() -> None:
    _section("UNIT: upload_markdown — degraded when GCS client unavailable")
    with patch.object(firebase_storage, "_get_client", return_value=None):
        out = firebase_storage.upload_markdown("uid", "slug", "id", "x")
    assert out is None, f"expected None when client unavailable, got {out!r}"
    print("client-unavailable: PASS")


def test_upload_swallows_gcs_errors() -> None:
    _section("UNIT: upload_markdown — GCS exception → None, no crash")
    client, blob = _make_fake_client()
    blob.upload_from_string.side_effect = gax.InternalServerError("simulated 500")

    with patch.object(firebase_storage, "_get_client", return_value=client):
        out = firebase_storage.upload_markdown("uid", "slug", "id", "x")

    assert out is None, "expected None when upload raises"
    blob.upload_from_string.assert_called_once()
    print("gcs-error swallowed: PASS")


def main() -> int:
    test_body_full_summary()
    test_body_omits_empty_sections()
    test_body_korean_utf8()
    test_body_handles_missing_fields()
    test_upload_happy_path()
    test_upload_rejects_empty_args()
    test_upload_handles_missing_client()
    test_upload_swallows_gcs_errors()
    print()
    print("=" * 70)
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
