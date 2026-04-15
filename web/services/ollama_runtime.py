"""Facciata legacy: il runtime Ollama vive in ``lex.providers``."""

from __future__ import annotations

from lex.providers.ollama_runtime import (
    clear_ollama_runtime_resolution_cache,
    normalize_ollama_api_base_url,
    refresh_live_ollama_runtime,
    refresh_ollama_runtime,
    resolved_ollama_api_base_url,
    resolved_ollama_base_url,
    resolved_ollama_chat_model,
    resolved_ollama_keep_alive,
    resolved_ollama_runtime,
    warm_ollama_chat_runtime,
)

__all__ = [
    "clear_ollama_runtime_resolution_cache",
    "normalize_ollama_api_base_url",
    "refresh_live_ollama_runtime",
    "refresh_ollama_runtime",
    "resolved_ollama_api_base_url",
    "resolved_ollama_base_url",
    "resolved_ollama_chat_model",
    "resolved_ollama_keep_alive",
    "resolved_ollama_runtime",
    "warm_ollama_chat_runtime",
]
