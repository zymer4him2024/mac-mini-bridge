"""Pydantic models for all rag_service request and response types.

The boundary contract: anything coming off the wire is parsed through these.
Everything past the route handler can trust the field shapes and bounds.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Identifier bounds match Firestore folder slugs in firestore_folders.py:
# slugs are derived from email subjects with strip+normalize, capped well
# below 128 in practice.
_SLUG_MAX = 128
_SUBJECT_MAX = 200
_QUESTION_MAX = 2000


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=_QUESTION_MAX)
    subject_slug: str = Field(..., min_length=1, max_length=_SLUG_MAX)
    subject_display: str = Field(..., min_length=1, max_length=_SUBJECT_MAX)


class AskMeta(BaseModel):
    error: str | None = None
    hits: int
    relevant: int
    top_dist: float


class AskResponse(BaseModel):
    reply: str
    meta: AskMeta
