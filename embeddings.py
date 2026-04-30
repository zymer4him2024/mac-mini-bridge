"""Ollama embedding wrapper for email2ppt RAG.

Turns text into a 768-dim vector using `embeddinggemma` over the
OpenAI-compatible /v1/embeddings endpoint at OLLAMA_BASE_URL — same Ollama
endpoint the rest of the pipeline uses for chat/summarization.

Raises on failure. Callers in the best-effort path (watcher.py RAG hook)
wrap calls in try/except so RAG outages can't block alert delivery.
"""

from __future__ import annotations

import os

from openai import OpenAI

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "embeddinggemma")
# v2 (2026-04-29): index context + key_points + asks + suggested_response,
# not just suggested_response. The v1 corpus was answer-prompts only, so the
# bot couldn't ground questions about the email's actual content.
EMBEDDING_VERSION = "embeddinggemma-v2-rich-content"
EMBEDDING_DIM = 768

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")

_client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama-local")


def embed_text(text: str) -> list[float]:
    """Return a 768-dim embedding for the given text. Raises on failure."""
    if not text or not text.strip():
        raise ValueError("embed_text: empty text")
    resp = _client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    vec = resp.data[0].embedding
    if len(vec) != EMBEDDING_DIM:
        raise RuntimeError(
            f"unexpected embedding dim {len(vec)} (want {EMBEDDING_DIM})"
        )
    return list(vec)


def build_rag_text(
    *,
    subject: str,
    sender_name: str,
    context: list[str] | None,
    key_points: list[str] | None,
    asks: list[str] | None,
    suggested_response: str,
) -> str:
    """Compose the text we embed for one email. Shared by the live watcher
    hook and the backfill script so v2 corpora stay consistent."""
    parts: list[str] = []
    if subject:
        parts.append(subject)
    if sender_name:
        parts.append(f"From: {sender_name}")
    for chunk in (context or []):
        if chunk:
            parts.append(str(chunk))
    for chunk in (key_points or []):
        if chunk:
            parts.append(str(chunk))
    for chunk in (asks or []):
        if chunk:
            parts.append(str(chunk))
    sr = (suggested_response or "").strip()
    if sr:
        parts.append(sr)
    return "\n".join(parts)
