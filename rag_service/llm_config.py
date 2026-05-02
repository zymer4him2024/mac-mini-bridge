"""Builds the OpenAI-compatible client for the configured LLM provider.

Every supported provider exposes an OpenAI-compatible chat-completions
endpoint, so a single `OpenAI` client with the right `base_url` + API key is
enough — no per-provider adapter classes. To add a new provider, add its
literal to LLMProvider in config.py and a branch here.
"""

from __future__ import annotations

from openai import OpenAI

from .config import Config

# OpenAI-compatible base URLs for hosted providers. The model strings live in
# Config so they're env-overridable without code changes.
_ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def build_llm_client(cfg: Config) -> tuple[OpenAI, str]:
    """Return (client, model) for the configured provider."""
    if cfg.llm_provider == "ollama":
        return (
            OpenAI(base_url=cfg.ollama_base_url, api_key="ollama-local"),
            cfg.ollama_model,
        )
    if cfg.llm_provider == "openai":
        return OpenAI(api_key=cfg.openai_api_key), cfg.openai_model
    if cfg.llm_provider == "anthropic":
        return (
            OpenAI(base_url=_ANTHROPIC_BASE_URL, api_key=cfg.anthropic_api_key),
            cfg.anthropic_model,
        )
    if cfg.llm_provider == "gemini":
        return (
            OpenAI(base_url=_GEMINI_BASE_URL, api_key=cfg.gemini_api_key),
            cfg.gemini_model,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {cfg.llm_provider}")
