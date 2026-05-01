"""Pure folder-scoped RAG pipeline. Messenger-agnostic.

Embeds the question, retrieves nearest passages from a per-folder vector
index, and grounds an LLM reply on those passages (NotebookLM-style: refuse
when context is insufficient). Knows nothing about Telegram/Slack/etc.
"""

from __future__ import annotations

import logging
import os

from openai import OpenAI, OpenAIError
from google.api_core import exceptions as gax

from embeddings import embed_text
from firestore_embeddings import search_embeddings

log = logging.getLogger("rag_core")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

RAG_K = 5
# Cosine distance: 0 = identical, 1 = orthogonal. embeddinggemma is asymmetric
# (query and passage embeddings drift apart) so short queries against rich
# corpora measured ~0.61–0.68 even for direct hits ("비빔밥" against an email
# listing 비빔밥 was 0.675). 0.7 keeps NotebookLM-style refusal for truly
# unrelated content while letting through real matches.
RAG_DISTANCE_THRESHOLD = 0.7

DEFAULT_ERROR_REPLY = "Something went wrong on our end. We've logged it."

_llm = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama-local")


def grounded_answer(
    question: str,
    subject: str,
    hits: list[dict],
    *,
    style_hint: str = "short replies, not essays",
) -> str:
    """NotebookLM-style: answer ONLY from retrieved context, refuse otherwise."""
    blocks = []
    for i, h in enumerate(hits, 1):
        sender = h.get("senderName") or "(unknown)"
        subj = h.get("subject") or ""
        body = (h.get("text") or "").strip()
        blocks.append(f"[{i}] From: {sender} | Subject: {subj}\n{body}")
    context = "\n\n".join(blocks)
    system = (
        "You answer the user's question using ONLY the provided email summaries. "
        "If the answer is not contained in the context, reply exactly: "
        '"I don\'t have that in this folder." '
        "Do not invent, speculate, or use outside knowledge. "
        f"Keep replies {style_hint}. "
        "When citing, refer to senders by name."
    )
    user = (
        f"Folder: {subject}\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    )
    try:
        resp = _llm.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        return (resp.choices[0].message.content or "").strip() or "(no response)"
    except (OpenAIError, OSError) as exc:
        log.exception("grounded LLM call failed: %s", exc)
        return DEFAULT_ERROR_REPLY


def answer_question(
    db,
    uid: str,
    slug: str,
    subject: str,
    question: str,
    *,
    k: int = RAG_K,
    distance_threshold: float = RAG_DISTANCE_THRESHOLD,
    style_hint: str = "short replies, not essays",
    error_reply: str = DEFAULT_ERROR_REPLY,
) -> tuple[str, dict]:
    """Resolve scope, retrieve, ground. Returns (reply_text, debug_meta).

    `reply_text` is one of:
      - the grounded LLM answer
      - a NotebookLM refusal: "I don't have anything in folder '{subject}' about that. ..."
      - `error_reply` on infrastructure failure (embed/search/LLM)

    `debug_meta` carries hits/relevant/top_dist for the caller's log line.
    """
    try:
        qvec = embed_text(question)
        hits = search_embeddings(db, uid, slug, qvec, k=k)
    except (OpenAIError, OSError, ValueError, gax.GoogleAPIError) as exc:
        log.exception("RAG retrieval failed (uid=%s slug=%s): %s", uid, slug, exc)
        return error_reply, {
            "error": "retrieval",
            "hits": 0,
            "relevant": 0,
            "top_dist": 1.0,
        }

    relevant = [h for h in hits if h.get("distance", 1.0) <= distance_threshold]
    top_dist = hits[0]["distance"] if hits else 1.0
    meta = {
        "error": None,
        "hits": len(hits),
        "relevant": len(relevant),
        "top_dist": top_dist,
    }

    if not relevant:
        return (
            f"I don't have anything in folder '{subject[:60]}' about that. "
            f"Try /folders to switch.",
            meta,
        )

    return grounded_answer(question, subject, relevant, style_hint=style_hint), meta
