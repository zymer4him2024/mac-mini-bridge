"""PII-redacting logging filter.

Worker logs sit on the host for 7 generations (B2 retention rule) and are
read by operators while triaging incidents. They must not leak the
customer's email address, the message-body excerpts, or the chat IDs that
join a Telegram identity to a uid.

Usage:

    import logging
    from log_redaction import install_redaction_filter

    install_redaction_filter(logging.getLogger())

`install_redaction_filter` attaches the filter to the given logger; pass
the root logger to cover everything. The filter walks `record.msg` and
`record.args`, replaces patterns in-place, and never raises.

Mask shape:

  shawn@example.com  -> s***@e***.com
  +14155550123       -> +14***0123    (E.164-ish)
  chat_id=123456789  -> chat_id=12***89  (preserves the field name)
"""

from __future__ import annotations

import logging
import re
from typing import Any

# Match local-part@domain.tld. Locale-friendly enough for our worker logs;
# we are not trying to pass RFC 5321.
_EMAIL_RE = re.compile(
    r"\b([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9])[A-Za-z0-9.-]*\.([A-Za-z]{2,})\b"
)
# E.164-style numbers; 7-15 digits to avoid catching everything.
_PHONE_RE = re.compile(r"\+?\d{7,15}")
# Telegram chat IDs surface as "chat_id=12345" or "chatId=12345" or in JSON.
_CHAT_ID_RE = re.compile(
    r"((?:chat[_-]?id)\s*[:=]?\s*['\"]?)(-?\d{6,})", re.IGNORECASE
)
# Bot tokens "<bot_id>:<35-char-secret>"
_BOT_TOKEN_RE = re.compile(r"\b\d{6,15}:[A-Za-z0-9_-]{30,50}\b")
# OAuth refresh-token shape: "1//0xxxx..."
_OAUTH_REFRESH_RE = re.compile(r"\b1//0[A-Za-z0-9_-]{20,}\b")


def _redact_email(match: re.Match[str]) -> str:
    return f"{match.group(1)}***@{match.group(2)}***.{match.group(3)}"


def _redact_phone(match: re.Match[str]) -> str:
    s = match.group(0)
    if len(s) <= 6:
        return "***"
    return f"{s[:3]}***{s[-3:]}"


def _redact_chat_id(match: re.Match[str]) -> str:
    label, digits = match.group(1), match.group(2)
    if len(digits) <= 4:
        return f"{label}***"
    return f"{label}{digits[:2]}***{digits[-2:]}"


def _redact(text: str) -> str:
    text = _BOT_TOKEN_RE.sub("<bot_token_redacted>", text)
    text = _OAUTH_REFRESH_RE.sub("<refresh_token_redacted>", text)
    text = _EMAIL_RE.sub(_redact_email, text)
    text = _CHAT_ID_RE.sub(_redact_chat_id, text)
    text = _PHONE_RE.sub(_redact_phone, text)
    return text


def _redact_arg(arg: Any) -> Any:
    if isinstance(arg, str):
        return _redact(arg)
    if isinstance(arg, (list, tuple)):
        redacted = [_redact_arg(a) for a in arg]
        return type(arg)(redacted)
    if isinstance(arg, dict):
        return {k: _redact_arg(v) for k, v in arg.items()}
    return arg


class PIIRedactionFilter(logging.Filter):
    """Mutate the record so the formatted output is already redacted.

    We avoid mutating record.msg pre-format because logging deferred-format
    leaves args separate; we redact both, then let the standard formatter
    do its thing.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = _redact(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: _redact_arg(v) for k, v in record.args.items()
                    }
                else:
                    record.args = tuple(_redact_arg(a) for a in record.args)
        except (TypeError, ValueError):
            # Never break logging; emit the original record unredacted on
            # error rather than swallowing the message.
            return True
        return True


def install_redaction_filter(logger: logging.Logger) -> None:
    """Attach a single PIIRedactionFilter to logger and all its handlers."""
    flt = PIIRedactionFilter()
    if not any(isinstance(f, PIIRedactionFilter) for f in logger.filters):
        logger.addFilter(flt)
    for handler in logger.handlers:
        if not any(isinstance(f, PIIRedactionFilter) for f in handler.filters):
            handler.addFilter(flt)
