"""Charset-aware MIME extraction helpers for Gmail API payloads."""

import base64
import logging
import re
from email.header import decode_header, make_header
from html import unescape

log = logging.getLogger(__name__)

# IANA / vendor charset names that Python's codec registry doesn't recognize
# directly. Korean mail in particular still uses ks_c_5601-1987 in headers.
_CHARSET_ALIASES = {
    "utf8": "utf-8",
    "ks_c_5601-1987": "cp949",
    "ks_c_5601-1989": "cp949",
    "ksc5601": "cp949",
    "ksc-5601": "cp949",
    "euckr": "euc_kr",
    "euc-kr": "euc_kr",
    "shift-jis": "shift_jis",
    "shift_jis": "shift_jis",
    "iso-2022-jp": "iso2022_jp",
}


def _normalize_charset(name: str) -> str:
    cs = name.strip().lower().strip('"').strip("'")
    return _CHARSET_ALIASES.get(cs, cs)


def _part_headers(part: dict) -> dict:
    return {
        h.get("name", "").lower(): h.get("value", "") for h in part.get("headers") or []
    }


def _charset_from_headers(headers: dict) -> str:
    ct = headers.get("content-type", "")
    m = re.search(r'charset\s*=\s*"?([^";\s]+)"?', ct, re.IGNORECASE)
    return _normalize_charset(m.group(1)) if m else "utf-8"


def _decode_part(data_b64: str, headers: dict) -> str:
    raw = base64.urlsafe_b64decode(data_b64)
    charset = _charset_from_headers(headers)
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        # Unknown codec name: fall back to UTF-8 with replacement.
        return raw.decode("utf-8", errors="replace")


def _strip_html(text: str) -> str:
    """Coarse HTML to text: drop scripts/styles, convert breaks, strip tags,
    decode entities, collapse whitespace."""
    text = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"<\s*(br\s*/?|/p|/div|/li|/tr)\s*>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _walk(payload: dict):
    """Yield (mimeType, headers_lowercase, data_b64) for every part with body data."""
    if not isinstance(payload, dict):
        return
    body_data = (payload.get("body") or {}).get("data")
    if body_data:
        yield (
            payload.get("mimeType", ""),
            _part_headers(payload),
            body_data,
        )
    for part in payload.get("parts") or []:
        yield from _walk(part)


def extract_body(payload: dict) -> str:
    """Extract email body text from a Gmail API payload.

    Prefers text/plain at any nesting depth; falls back to HTML-stripped
    text/html if no plain part is present. Decodes each part using its
    declared charset (Content-Type header), so EUC-KR / CP949 / Shift-JIS
    bodies are not mangled to mojibake.
    """
    plain: list[str] = []
    html: list[str] = []
    for mime_type, headers, data in _walk(payload):
        if mime_type == "text/plain":
            plain.append(_decode_part(data, headers))
        elif mime_type == "text/html":
            html.append(_decode_part(data, headers))
    if plain:
        return "\n".join(plain).strip()
    if html:
        return _strip_html("\n".join(html))
    # No text/* parts found — return any other body data we have so the
    # caller at least sees something rather than an empty string.
    for _, headers, data in _walk(payload):
        return _decode_part(data, headers)
    return ""


def decode_header_value(raw: str) -> str:
    """RFC 2047 decode a header value (Subject, From, etc.).

    Gmail returns header values as raw strings, so an EUC-KR-encoded
    Korean Subject like '=?euc-kr?B?ufa48bChx9G/...?=' arrives as
    that literal sequence and must be decoded before being shown to
    a user or fed to the LLM.
    """
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except (UnicodeDecodeError, LookupError, ValueError) as exc:
        log.warning("decode_header_value failed: %s — value=%r", exc, raw[:80])
        return raw


def build_markdown_body(email: dict, summary: dict) -> str:
    """Render the canonical .md document for an email.

    The web reader at `/[locale]/subjects/[slug]/items/[itemId]` fetches
    the upload produced by this function from `summaries/{uid}/{slug}/{id}.md`
    and renders it via react-markdown + GFM. Keep the structure stable —
    section headers double as anchors and as parse hints for future RAG
    chunkers.

    Empty list sections are omitted entirely so low-signal docs stay tidy.
    Empty `suggested_response` keeps its header but a blank body, which
    matches the intended user expectation that "no draft" is itself a result.
    """
    subject = (email.get("subject") or "(no subject)").strip() or "(no subject)"
    sender = email.get("from") or ""
    date = email.get("date") or ""
    urgency = (summary.get("urgency") or "low").strip() or "low"
    key_points = [str(p).strip() for p in (summary.get("key_points") or []) if p]
    asks = [str(a).strip() for a in (summary.get("asks") or []) if a]
    suggested_response = (summary.get("suggested_response") or "").strip()
    body = (email.get("body") or "").strip()

    parts: list[str] = [f"# {subject}", ""]

    meta_lines: list[str] = []
    if sender:
        meta_lines.append(f"- **From:** {sender}")
    if date:
        meta_lines.append(f"- **Date:** {date}")
    meta_lines.append(f"- **Urgency:** {urgency}")
    parts.extend(meta_lines)
    parts.append("")

    if key_points:
        parts.append("## Key points")
        parts.extend(f"- {p}" for p in key_points)
        parts.append("")

    if asks:
        parts.append("## Asks")
        parts.extend(f"- {a}" for a in asks)
        parts.append("")

    parts.append("## Suggested response")
    parts.append("")
    if suggested_response:
        parts.append(suggested_response)
        parts.append("")

    parts.append("---")
    parts.append("")
    parts.append("## Original message")
    parts.append("")
    if body:
        parts.append(body)
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"
