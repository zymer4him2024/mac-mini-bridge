"""Unit tests for mime_extract.strip_quoted_reply.

Run: python test_mime_extract.py

No network or Firestore access. Pure-function tests against in-memory strings.
Exit code: 0 if all checks pass, 1 otherwise.
"""

from __future__ import annotations

import sys

from mime_extract import strip_quoted_reply

_PASS = 0
_FAIL = 0


def _check(name: str, ok: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    print(f"{'[PASS]' if ok else '[FAIL]'} {name}{f' — {detail}' if detail else ''}")
    if ok:
        _PASS += 1
    else:
        _FAIL += 1


def _section(title: str) -> None:
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
# Trivial inputs
# ---------------------------------------------------------------------------


def test_empty() -> None:
    _section("empty / unchanged")
    _check("empty string returns empty", strip_quoted_reply("") == "")
    plain = "Hello, this is the new content.\nNo reply markers here."
    _check(
        "no reply markers → returned unchanged",
        strip_quoted_reply(plain) == plain,
    )


# ---------------------------------------------------------------------------
# English "On … wrote:" reply header
# ---------------------------------------------------------------------------


def test_english_reply() -> None:
    _section("english reply header")
    body = (
        "Thanks for the update — looks good to me.\n"
        "Let's plan to ship Friday.\n"
        "\n"
        "On Wed, Apr 30, 2026 at 9:12 AM John Doe <john@x.com> wrote:\n"
        "> hi team, can we ship this week?\n"
        "> let me know\n"
    )
    out = strip_quoted_reply(body)
    _check(
        "new content kept",
        "Thanks for the update" in out and "ship Friday" in out,
    )
    _check(
        "wrote: marker dropped",
        "wrote:" not in out and "John Doe" not in out,
    )
    _check("> quoted lines dropped", "ship this week" not in out)


def test_english_reply_multiline_header() -> None:
    """Some clients wrap the 'On … wrote:' header across multiple lines."""
    _section("english reply header — multi-line wrap")
    body = (
        "New reply here.\n"
        "\n"
        "On Wed, Apr 30, 2026 at 9:12 AM John Doe\n"
        "<john@x.com> wrote:\n"
        "> quoted parent body\n"
    )
    out = strip_quoted_reply(body)
    _check("new content kept", "New reply here" in out)
    _check("multi-line wrote: header still cut", "John Doe" not in out)
    _check("quoted body dropped", "quoted parent body" not in out)


# ---------------------------------------------------------------------------
# Korean "… 작성:" reply header
# ---------------------------------------------------------------------------


def test_korean_reply() -> None:
    _section("korean reply header")
    body = (
        "회신 본문 — 새로 쓴 내용입니다.\n"
        "내일까지 답변 드리겠습니다.\n"
        "\n"
        "2026년 4월 30일 (수) 오전 9:12, John Doe <john@x.com>님이 작성:\n"
        "> 안녕하세요, 이번 주에 출시 가능할까요?\n"
    )
    out = strip_quoted_reply(body)
    _check("new content kept", "회신 본문" in out and "내일까지" in out)
    _check("작성: marker dropped", "작성:" not in out and "John Doe" not in out)
    _check("> quoted parent dropped", "안녕하세요" not in out)


def test_korean_reply_fullwidth_colon() -> None:
    """Some clients use a full-width colon (：) after 작성 instead of ASCII (:)."""
    _section("korean reply header — full-width colon")
    body = (
        "새 답장 내용입니다.\n"
        "\n"
        "2026년 4월 30일, 홍길동 <hong@x.com>님이 작성：\n"
        "> 이전 메시지 본문\n"
    )
    out = strip_quoted_reply(body)
    _check("new content kept", "새 답장 내용" in out)
    _check("full-width 작성： cut", "홍길동" not in out)
    _check("> quoted parent dropped", "이전 메시지" not in out)


# ---------------------------------------------------------------------------
# > quoted-line stripping (no reply header)
# ---------------------------------------------------------------------------


def test_quote_prefix_only() -> None:
    _section("> quoted lines without reply header")
    body = (
        "My reply line one.\n"
        "My reply line two.\n"
        "> previous message line A\n"
        "  > indented quoted line\n"
        ">> nested quote\n"
        "Trailing reply line.\n"
    )
    out = strip_quoted_reply(body)
    _check("reply lines kept", "My reply line one." in out)
    _check("trailing reply line kept", "Trailing reply line." in out)
    _check("flat > line dropped", "previous message line A" not in out)
    _check(
        "indented > line dropped (lstrip-aware)",
        "indented quoted line" not in out,
    )
    _check("nested >> line dropped", "nested quote" not in out)


# ---------------------------------------------------------------------------
# Forwarded message — must NOT be stripped
# ---------------------------------------------------------------------------


def test_forwarded_not_stripped() -> None:
    _section("forwarded body must NOT be stripped — the forward IS the content")
    body = (
        "FYI — see below.\n"
        "\n"
        "---------- Forwarded message ----------\n"
        "From: Alice <alice@x.com>\n"
        "Subject: Q3 plan\n"
        "\n"
        "We need to lock in the Q3 hiring plan by next Friday.\n"
        "Two engineering hires plus one designer.\n"
    )
    out = strip_quoted_reply(body)
    _check("forwarded preamble kept", "FYI — see below." in out)
    _check(
        "forwarded body content kept",
        "Q3 hiring plan" in out and "Two engineering hires" in out,
    )
    _check("forwarded marker line itself kept", "Forwarded message" in out)


# ---------------------------------------------------------------------------
# Earliest marker wins
# ---------------------------------------------------------------------------


def test_earliest_marker_wins() -> None:
    """If a body has both English and Korean reply markers, cut at whichever
    appears first. (Real-world: a reply-to-a-reply where the inner thread is
    in a different language.)"""
    _section("earliest reply marker wins")
    body = (
        "New reply on top.\n"
        "\n"
        "2026년 4월 30일, A님이 작성:\n"
        "> quoted Korean body\n"
        "\n"
        "On Tue, Apr 29, 2026 at 10:00 AM B <b@x.com> wrote:\n"
        "> deeper English quote\n"
    )
    out = strip_quoted_reply(body)
    _check("new content kept", "New reply on top." in out)
    _check("everything after Korean marker dropped", "wrote:" not in out)
    _check("Korean marker itself dropped", "작성:" not in out)


# ---------------------------------------------------------------------------
# Whitespace normalization
# ---------------------------------------------------------------------------


def test_whitespace_normalization() -> None:
    _section("collapse 3+ blank lines and trim ends")
    body = "Line one.\n\n\n\n\nLine two.\n\n\n"
    out = strip_quoted_reply(body)
    _check("3+ blanks collapsed to single blank", "\n\n\n" not in out)
    _check("leading/trailing whitespace stripped", out == out.strip())
    _check("content preserved", "Line one." in out and "Line two." in out)


# ---------------------------------------------------------------------------
def main() -> int:
    test_empty()
    test_english_reply()
    test_english_reply_multiline_header()
    test_korean_reply()
    test_korean_reply_fullwidth_colon()
    test_quote_prefix_only()
    test_forwarded_not_stripped()
    test_earliest_marker_wins()
    test_whitespace_normalization()

    print(f"\n{'=' * 50}")
    print(f"Passed: {_PASS}    Failed: {_FAIL}")
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
