"""Bridge di salute e runtime provider posseduti dal package Lex."""

from __future__ import annotations

from typing import Any

from web.services.ollama_runtime import (
    resolved_ollama_runtime,
    warm_ollama_chat_runtime,
)


def resolved_runtime() -> dict[str, Any]:
    return dict(resolved_ollama_runtime() or {})


def warm_runtime() -> dict[str, Any]:
    return dict(warm_ollama_chat_runtime() or {})


def provider_health() -> dict[str, Any]:
    runtime = resolved_runtime()
    return {
        "ok": bool(runtime.get("api_base_url") and runtime.get("chat_model")),
        "provider": "ollama",
        "runtime": runtime,
    }
