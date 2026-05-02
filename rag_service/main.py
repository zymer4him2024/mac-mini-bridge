"""Defines FastAPI app and HTTP route handlers for the web RAG service.

Single endpoint POST /ask: validates a Firebase ID token, parses the request
through the AskRequest Pydantic model, and delegates to
`rag_core.answer_question`. Plus a /healthz for liveness checks.

The LLM client and Firestore handle are built lazily via FastAPI dependencies
so tests can swap them in via `app.dependency_overrides` without
monkeypatching imports. The LLM dependency is the seam that lets us swap
provider (Ollama → Claude / Gemini / OpenAI) by changing one env var at
deploy time.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from firestore_activity import get_db
from rag_core import answer_question

from .auth import get_uid
from .config import get_config
from .llm_config import build_llm_client
from .schemas import AskMeta, AskRequest, AskResponse

log = logging.getLogger("rag_service.main")


@lru_cache(maxsize=1)
def _build_llm_cached() -> tuple[OpenAI, str]:
    return build_llm_client(get_config())


@lru_cache(maxsize=1)
def _firestore_cached() -> Any:
    return get_db()


def llm_dep() -> tuple[OpenAI, str]:
    """FastAPI dependency: cached (client, model) for the configured provider."""
    return _build_llm_cached()


def db_dep() -> Any:
    """FastAPI dependency: cached Firestore client."""
    return _firestore_cached()


_cfg = get_config()

app = FastAPI(title="Shomery RAG service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cfg.cors_origins,
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/healthz")
def healthz(llm: tuple[OpenAI, str] = Depends(llm_dep)) -> dict[str, object]:
    _, model = llm
    return {
        "ok": True,
        "provider": _cfg.llm_provider,
        "model": model,
    }


@app.post("/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    uid: str = Depends(get_uid),
    db: Any = Depends(db_dep),
    llm: tuple[OpenAI, str] = Depends(llm_dep),
) -> AskResponse:
    client, model = llm
    reply, meta = answer_question(
        db,
        uid,
        req.subject_slug,
        req.subject_display,
        req.question,
        style_hint=_cfg.style_hint,
        # Web has its own subject switcher; suppress the Telegram /folders hint.
        refusal_suffix="",
        llm_client=client,
        llm_model=model,
    )
    log.info(
        "ask uid=%s slug=%s hits=%s relevant=%s top_dist=%.3f provider=%s",
        uid,
        req.subject_slug,
        meta.get("hits"),
        meta.get("relevant"),
        meta.get("top_dist", 1.0),
        _cfg.llm_provider,
    )
    return AskResponse(reply=reply, meta=AskMeta(**meta))
