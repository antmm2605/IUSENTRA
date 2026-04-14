from __future__ import annotations

from threading import Lock
from time import monotonic
from typing import Any

from flask import current_app

from pct.local_ai import OllamaHttpClient, strip_api_suffix
from pct.runtime_env import is_managed_cloud_runtime
from web.services.local_ai_runtime import get_local_ai_service


_RUNTIME_CACHE_TTL_SECONDS = 20.0


def normalize_ollama_api_base_url(value: str) -> str:
    raw = str(value or "http://127.0.0.1:11434/api").strip().rstrip("/")
    if raw.endswith("/api"):
        return raw
    return f"{raw}/api"


def _fallback_runtime_payload(default_model: str = "mistral") -> dict[str, str]:
    configured_base_url = (
        current_app.config.get("LOCAL_AI_BASE_URL")
        or current_app.config.get("OLLAMA_URL")
        or "http://127.0.0.1:11434"
    )
    configured_model = str(
        current_app.config.get("LOCAL_AI_CHAT_MODEL")
        or current_app.config.get("OLLAMA_MODEL")
        or default_model
    ).strip()
    configured_keep_alive = str(current_app.config.get("LOCAL_AI_KEEP_ALIVE") or "10m").strip() or "10m"
    api_base_url = normalize_ollama_api_base_url(str(configured_base_url))
    return {
        "api_base_url": api_base_url,
        "base_url": strip_api_suffix(api_base_url),
        "chat_model": configured_model or default_model,
        "keep_alive": configured_keep_alive,
        "source": "config",
    }


def _cache_key(default_model: str) -> tuple[str, str, str]:
    return (
        str(current_app.config.get("LOCAL_AI_BASE_URL") or current_app.config.get("OLLAMA_URL") or "").strip(),
        str(current_app.config.get("LOCAL_AI_CHAT_MODEL") or current_app.config.get("OLLAMA_MODEL") or "").strip(),
        str(default_model or "mistral").strip(),
    )


def _cache_lock() -> Lock:
    app = current_app._get_current_object()
    lock = app.extensions.get("ollama_runtime_lock")
    if lock is None:
        lock = Lock()
        app.extensions["ollama_runtime_lock"] = lock
    return lock


def _cache_payload(default_model: str, payload: dict[str, str], max_age_seconds: float) -> dict[str, str]:
    app = current_app._get_current_object()
    cached = dict(payload)
    app.extensions["ollama_runtime_resolution"] = {
        "key": _cache_key(default_model),
        "expires_at": monotonic() + max(max_age_seconds, 1.0),
        "payload": cached,
    }
    return cached


def clear_ollama_runtime_resolution_cache() -> None:
    app = current_app._get_current_object()
    app.extensions.pop("ollama_runtime_resolution", None)


def resolved_ollama_runtime(
    default_model: str = "mistral",
    *,
    force_refresh: bool = False,
    max_age_seconds: float = _RUNTIME_CACHE_TTL_SECONDS,
) -> dict[str, str]:
    app = current_app._get_current_object()
    cache_entry = app.extensions.get("ollama_runtime_resolution") or {}
    cache_key = _cache_key(default_model)
    now = monotonic()

    if (
        not force_refresh
        and cache_entry.get("key") == cache_key
        and float(cache_entry.get("expires_at") or 0.0) > now
    ):
        return dict(cache_entry.get("payload") or {})

    with _cache_lock():
        cache_entry = app.extensions.get("ollama_runtime_resolution") or {}
        if (
            not force_refresh
            and cache_entry.get("key") == cache_key
            and float(cache_entry.get("expires_at") or 0.0) > monotonic()
        ):
            return dict(cache_entry.get("payload") or {})

        payload = _fallback_runtime_payload(default_model)
        service = None
        try:
            service = get_local_ai_service()
            keep_alive = str(service._load_settings().keep_alive or "").strip()
            if keep_alive:
                payload["keep_alive"] = keep_alive
        except Exception:
            service = None
        try:
            if service is None:
                service = get_local_ai_service()
            snapshot = service.health_snapshot()
            live_base_url = str(snapshot.get("runtime_base_url_live") or "").strip()
            if live_base_url:
                payload["api_base_url"] = normalize_ollama_api_base_url(live_base_url)
                payload["base_url"] = strip_api_suffix(payload["api_base_url"])
            configured_base_url = str((snapshot.get("settings") or {}).get("base_url") or "").strip()
            if configured_base_url and not live_base_url:
                payload["api_base_url"] = normalize_ollama_api_base_url(configured_base_url)
                payload["base_url"] = strip_api_suffix(payload["api_base_url"])
            resolved_model = str((snapshot.get("resolved_models") or {}).get("chat") or "").strip()
            if resolved_model:
                payload["chat_model"] = resolved_model
            payload["source"] = "snapshot"
        except Exception:
            pass

        return _cache_payload(default_model, payload, max_age_seconds)


def refresh_ollama_runtime(default_model: str = "mistral") -> dict[str, str]:
    return resolved_ollama_runtime(default_model, force_refresh=True)


def resolved_ollama_api_base_url() -> str:
    return resolved_ollama_runtime().get("api_base_url") or normalize_ollama_api_base_url("")


def resolved_ollama_base_url() -> str:
    return resolved_ollama_runtime().get("base_url") or strip_api_suffix(resolved_ollama_api_base_url())


def resolved_ollama_chat_model(default: str = "mistral") -> str:
    return resolved_ollama_runtime(default).get("chat_model") or default


def resolved_ollama_keep_alive(default: str = "10m") -> str:
    runtime = resolved_ollama_runtime()
    keep_alive = str(runtime.get("keep_alive") or "").strip()
    if keep_alive:
        return keep_alive
    try:
        keep_alive = str(get_local_ai_service()._load_settings().keep_alive or "").strip()
        if keep_alive:
            return keep_alive
    except Exception:
        pass
    return str(default or "10m").strip() or "10m"


def warm_ollama_chat_runtime(force_refresh: bool = False) -> dict[str, Any]:
    if is_managed_cloud_runtime():
        return {"status": "skipped", "reason": "managed_cloud"}

    runtime = resolved_ollama_runtime(force_refresh=force_refresh)
    model_name = str(runtime.get("chat_model") or "").strip()
    if not model_name:
        return {"status": "skipped", "reason": "missing_model"}

    keep_alive = resolved_ollama_keep_alive()
    try:
        client = OllamaHttpClient(runtime.get("api_base_url") or resolved_ollama_api_base_url())
        payload = client.warmup_model(model_name, keep_alive=keep_alive)
        refreshed = refresh_ollama_runtime()
        return {
            "status": "ready",
            "chat_model": refreshed.get("chat_model") or model_name,
            "base_url": refreshed.get("base_url") or runtime.get("base_url") or "",
            "keep_alive": keep_alive,
            "load_duration": payload.get("load_duration"),
            "prompt_eval_count": payload.get("prompt_eval_count"),
        }
    except Exception as exc:
        current_app.logger.debug("Warmup runtime Ollama non riuscito: %s", exc)
        return {
            "status": "error",
            "chat_model": model_name,
            "base_url": runtime.get("base_url") or "",
            "keep_alive": keep_alive,
            "error": str(exc),
        }
