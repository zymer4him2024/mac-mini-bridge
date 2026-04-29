"""Pydantic input validation for the Telegram boundary.

Per CLAUDE.md Tier-1: all data crossing a system boundary must be validated
against a schema before use. These models guard the two free-form-string
inputs that reach our code from Telegram users:

  - `LinkTokenInput` — the argument to `/start <token>`. Already used to
    look up a Firestore doc by ID, so length + character class need to be
    bounded.
  - `PPTQuery` — the Gmail search query passed to `/ppt`. Forwarded into
    a `subprocess.Popen([..., query])` argv (no shell), then into the
    Gmail API `q=` parameter. Restricting to known Gmail search operators
    keeps the LLM/users from feeding the worker pathological inputs.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, ValidationError, field_validator


# Long-form token: alphanum/underscore/hyphen, 6..64 chars.
# Short code: exactly 6 digits.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_SHORT_CODE_RE = re.compile(r"^\d{6}$")

# Gmail search operators we accept. Anything outside this set is rejected.
# Reference: https://support.google.com/mail/answer/7190
_GMAIL_OPERATOR_RE = re.compile(
    r"^(?:from|to|cc|bcc|subject|label|has|is|in|after|before|"
    r"older|newer|older_than|newer_than|filename|category|"
    r"deliveredto|list|size|larger|smaller|rfc822msgid):",
    re.IGNORECASE,
)
# Allowed PPT-query characters: word chars, common punctuation,
# parentheses (for OR groups), colon, hyphen, dot, plus, slash, @.
_PPT_QUERY_RE = re.compile(r"^[A-Za-z0-9_\s:@.\-+/()\"']+$")


class InvalidLinkInput(ValueError):
    """Raised by parse_link_input when the user-supplied token is malformed."""


class InvalidPPTQuery(ValueError):
    """Raised by parse_ppt_query when /ppt is given an unsafe argument."""


class LinkTokenInput(BaseModel):
    raw: str = Field(min_length=1, max_length=80)

    @field_validator("raw")
    @classmethod
    def _shape(cls, v: str) -> str:
        cleaned = v.replace("-", "").replace(" ", "")
        if _SHORT_CODE_RE.match(cleaned):
            return cleaned
        if _TOKEN_RE.match(v):
            return v
        raise ValueError("token must be 6 digits or 6-64 chars [A-Za-z0-9_-]")


class PPTQuery(BaseModel):
    query: str = Field(min_length=1, max_length=200)

    @field_validator("query")
    @classmethod
    def _shape(cls, v: str) -> str:
        v = v.strip()
        if not _PPT_QUERY_RE.match(v):
            raise ValueError("query contains disallowed characters")
        # Require at least one Gmail-search operator. Free-text-only
        # queries are rejected because they widen the worker's reach
        # over the mailbox without intent.
        for token in v.split():
            if _GMAIL_OPERATOR_RE.match(token):
                return v
        raise ValueError(
            "query must include at least one Gmail operator "
            "(from:, to:, subject:, is:, newer_than:, ...)"
        )


def parse_link_input(raw: str) -> str:
    """Return a clean token-or-shortCode string. Raises InvalidLinkInput."""
    try:
        return LinkTokenInput(raw=raw).raw
    except ValidationError as exc:
        raise InvalidLinkInput(str(exc)) from exc


def parse_ppt_query(raw: str) -> str:
    """Return the validated /ppt query. Raises InvalidPPTQuery."""
    try:
        return PPTQuery(query=raw).query
    except ValidationError as exc:
        raise InvalidPPTQuery(str(exc)) from exc
