"""Reads and validates all rag_service environment variables at startup.

Failing fast at import time means a misconfigured deploy crashes loudly
instead of returning 500s on every request. Provider-specific keys are only
required when that provider is selected — see _validate().
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Literal

LLMProvider = Literal["ollama", "openai", "anthropic", "gemini"]
_VALID_PROVIDERS: tuple[LLMProvider, ...] = ("ollama", "openai", "anthropic", "gemini")


@dataclass(frozen=True)
class Config:
    # Service
    port: int
    cors_origins: list[str]

    # LLM provider selection
    llm_provider: LLMProvider

    # Provider-specific (only the selected provider's fields are required)
    ollama_base_url: str
    ollama_model: str
    openai_api_key: str
    openai_model: str
    anthropic_api_key: str
    anthropic_model: str
    gemini_api_key: str
    gemini_model: str

    # Reply tuning
    style_hint: str = field(default="short, plain English, like a smart colleague")


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"FATAL: {name} is not set", file=sys.stderr)
        sys.exit(1)
    return val


def _load_config() -> Config:
    provider_raw = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()
    if provider_raw not in _VALID_PROVIDERS:
        print(
            f"FATAL: LLM_PROVIDER={provider_raw!r} not in {_VALID_PROVIDERS}",
            file=sys.stderr,
        )
        sys.exit(1)
    provider: LLMProvider = provider_raw  # type: ignore[assignment]

    port_raw = os.environ.get("RAG_PORT", "8001").strip()
    try:
        port = int(port_raw)
    except ValueError:
        print(f"FATAL: RAG_PORT={port_raw!r} is not an integer", file=sys.stderr)
        sys.exit(1)

    cors_raw = os.environ.get(
        "RAG_CORS_ORIGINS",
        "http://localhost:3000,https://shomeryai.web.app",
    )
    cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]

    cfg = Config(
        port=port,
        cors_origins=cors_origins,
        llm_provider=provider,
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
    )
    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    """Fail fast if the selected provider is missing its required key."""
    if cfg.llm_provider == "openai" and not cfg.openai_api_key:
        _require("OPENAI_API_KEY")
    elif cfg.llm_provider == "anthropic" and not cfg.anthropic_api_key:
        _require("ANTHROPIC_API_KEY")
    elif cfg.llm_provider == "gemini" and not cfg.gemini_api_key:
        _require("GEMINI_API_KEY")
    # ollama is keyless (local) — no validation needed.


# Lazy: only load when actually requested. Tests import Config directly and
# pass their own values without triggering the env read.
_cached: Config | None = None


def get_config() -> Config:
    global _cached
    if _cached is None:
        _cached = _load_config()
    return _cached
