from __future__ import annotations

from flask import current_app

from pct.local_ai import strip_api_suffix
from web.services.local_ai_runtime import get_local_ai_service


def normalize_ollama_api_base_url(value: str) -> str:
    raw = str(value or "http://127.0.0.1:11434/api").strip().rstrip("/")
    if raw.endswith("/api"):
        return raw
    return f"{raw}/api"


def resolved_ollama_api_base_url() -> str:
    try:
        snapshot = get_local_ai_service().health_snapshot()
        live_base_url = str(snapshot.get("runtime_base_url_live") or "").strip()
        if live_base_url:
            return normalize_ollama_api_base_url(live_base_url)

        settings = snapshot.get("settings") or {}
        configured_base_url = str(settings.get("base_url") or "").strip()
        if configured_base_url:
            return normalize_ollama_api_base_url(configured_base_url)
    except Exception:
        pass

    configured = (
        current_app.config.get("LOCAL_AI_BASE_URL")
        or current_app.config.get("OLLAMA_URL")
        or "http://127.0.0.1:11434"
    )
    return normalize_ollama_api_base_url(str(configured))


def resolved_ollama_base_url() -> str:
    return strip_api_suffix(resolved_ollama_api_base_url())


def resolved_ollama_chat_model(default: str = "mistral") -> str:
    try:
        snapshot = get_local_ai_service().health_snapshot()
        model_name = str((snapshot.get("resolved_models") or {}).get("chat") or "").strip()
        if model_name:
            return model_name
    except Exception:
        pass

    return str(
        current_app.config.get("LOCAL_AI_CHAT_MODEL")
        or current_app.config.get("OLLAMA_MODEL")
        or default
    ).strip()
