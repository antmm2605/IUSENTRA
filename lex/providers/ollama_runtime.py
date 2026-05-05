"""Risoluzione runtime Ollama posseduta dal package Lex."""

from __future__ import annotations

from threading import Lock
from typing import Any, cast

from flask import current_app

from pct.local_ai import OllamaHttpClient, strip_api_suffix
from pct.runtime_env import is_managed_cloud_runtime

from .local_ai_service import get_local_ai_service


def _flask_app() -> Any:
    return cast(Any, current_app)._get_current_object()


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
    configured_keep_alive = (
        str(current_app.config.get("LOCAL_AI_KEEP_ALIVE") or "10m").strip() or "10m"
    )
    api_base_url = normalize_ollama_api_base_url(str(configured_base_url))
    return {
        "api_base_url": api_base_url,
        "base_url": strip_api_suffix(api_base_url),
        "chat_model": configured_model or default_model,
        "keep_alive": configured_keep_alive,
        "source": "config",
    }


def _cache_lock() -> Lock:
    app = _flask_app()
    lock = app.extensions.get("ollama_runtime_lock")
    if lock is None:
        lock = Lock()
        app.extensions["ollama_runtime_lock"] = lock
    return lock


def _chat_runtime_cache_key(default_model: str) -> tuple[str, str, str]:
    return (
        str(default_model or "mistral").strip() or "mistral",
        str(current_app.config.get("STUDIO_CONFIG") or "").strip(),
        str(current_app.config.get("LOCAL_AI_DB") or "").strip(),
    )


def _load_runtime_row(service) -> dict[str, Any]:
    try:
        with service._connect() as conn:
            row = service._runtime_row(conn)
            return dict(row or {})
    except Exception:
        return {}


def _load_active_chat_model(service) -> str:
    try:
        with service._connect() as conn:
            row = conn.execute(
                """
                SELECT model_name
                FROM local_ai_models
                WHERE role = ? AND is_active = 1
                ORDER BY last_verified_at DESC
                LIMIT 1
                """,
                ("chat",),
            ).fetchone()
            if row and row["model_name"]:
                return str(row["model_name"]).strip()
    except Exception:
        return ""
    return ""


def _cache_payload(
    *, cache_name: str, fingerprint: tuple[Any, ...], payload: dict[str, str]
) -> dict[str, str]:
    app = _flask_app()
    cached = dict(payload)
    app.extensions[cache_name] = {
        "fingerprint": fingerprint,
        "payload": cached,
    }
    return cached


def clear_ollama_runtime_resolution_cache() -> None:
    app = _flask_app()
    app.extensions.pop("ollama_runtime_resolution", None)
    app.extensions.pop("ollama_live_runtime_resolution", None)


def _compute_local_chat_runtime(
    default_model: str = "mistral",
) -> tuple[tuple[Any, ...], dict[str, str]]:
    payload = _fallback_runtime_payload(default_model)
    service = get_local_ai_service()
    settings = service._load_settings()
    runtime_row = _load_runtime_row(service)
    active_chat_model = _load_active_chat_model(service)

    configured_base_url = str(settings.base_url or "").strip()
    if configured_base_url:
        payload["api_base_url"] = normalize_ollama_api_base_url(configured_base_url)
        payload["base_url"] = strip_api_suffix(payload["api_base_url"])

    row_status = str(runtime_row.get("status") or "").strip().lower()
    row_base_url = str(runtime_row.get("api_base_url") or "").strip()
    if row_base_url and row_status == "ready":
        payload["api_base_url"] = normalize_ollama_api_base_url(row_base_url)
        payload["base_url"] = strip_api_suffix(payload["api_base_url"])

    configured_keep_alive = str(settings.keep_alive or "").strip()
    if configured_keep_alive:
        payload["keep_alive"] = configured_keep_alive

    configured_model = str(settings.chat_model or "").strip()
    if configured_model:
        payload["chat_model"] = configured_model
        payload["source"] = "settings"
    elif active_chat_model:
        payload["chat_model"] = active_chat_model
        payload["source"] = "db"
    else:
        try:
            model_policy = service._resolve_model_policy(
                service._detect_hardware(),
                settings,
                service._load_policy(),
            )
            resolved_model = str(model_policy.get("chat_model") or "").strip()
            if resolved_model:
                payload["chat_model"] = resolved_model
                payload["source"] = "policy"
        except Exception:
            pass

    return _chat_runtime_cache_key(default_model), payload


def _live_chat_runtime(
    default_model: str = "mistral",
) -> tuple[tuple[Any, ...], dict[str, str]]:
    service = get_local_ai_service()
    settings = service._load_settings()
    payload = _fallback_runtime_payload(default_model)
    runtime_row = _load_runtime_row(service)
    row_status = str(runtime_row.get("status") or "").strip().lower()
    row_base_url = str(runtime_row.get("api_base_url") if row_status == "ready" else "").strip()
    if not row_base_url:
        row_base_url = str(settings.base_url or payload["api_base_url"]).strip()
    payload["api_base_url"] = normalize_ollama_api_base_url(row_base_url)
    payload["base_url"] = strip_api_suffix(payload["api_base_url"])
    payload["keep_alive"] = (
        str(settings.keep_alive or payload["keep_alive"]).strip() or payload["keep_alive"]
    )

    client = OllamaHttpClient(payload["api_base_url"])
    version = client.get_version()
    if not version:
        return _chat_runtime_cache_key(default_model), payload

    installed_models = client.list_models()
    running_models = client.list_running_models()
    try:
        with service._connect() as conn:
            db_models = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM local_ai_models ORDER BY role, model_name"
                ).fetchall()
            ]
    except Exception:
        db_models = []

    resolved = service._resolve_effective_models(
        settings=settings,
        hardware=service._detect_hardware(),
        policy=service._load_policy(),
        installed_models=installed_models,
        running_models=running_models,
        db_models=db_models,
    )
    resolved_model = str(resolved.get("chat_model") or "").strip()
    if resolved_model:
        payload["chat_model"] = resolved_model
    payload["source"] = "live"
    payload["runtime_version"] = version
    return _chat_runtime_cache_key(default_model), payload


def resolved_ollama_runtime(
    default_model: str = "mistral",
    *,
    force_refresh: bool = False,
) -> dict[str, str]:
    app = _flask_app()
    cache_name = "ollama_runtime_resolution"
    cache_entry = app.extensions.get(cache_name) or {}
    cache_key = _chat_runtime_cache_key(default_model)
    if not force_refresh and cache_entry.get("fingerprint") == cache_key:
        return dict(cache_entry.get("payload") or {})

    try:
        fingerprint, payload = _compute_local_chat_runtime(default_model)
    except Exception:
        fingerprint, payload = cache_key, _fallback_runtime_payload(default_model)

    with _cache_lock():
        cache_entry = app.extensions.get(cache_name) or {}
        if not force_refresh and cache_entry.get("fingerprint") == cache_key:
            return dict(cache_entry.get("payload") or {})
        return _cache_payload(
            cache_name=cache_name,
            fingerprint=fingerprint,
            payload=payload,
        )


def refresh_ollama_runtime(default_model: str = "mistral") -> dict[str, str]:
    try:
        fingerprint, payload = _compute_local_chat_runtime(default_model)
    except Exception:
        fingerprint, payload = _chat_runtime_cache_key(
            default_model
        ), _fallback_runtime_payload(default_model)
    with _cache_lock():
        return _cache_payload(
            cache_name="ollama_runtime_resolution",
            fingerprint=fingerprint,
            payload=payload,
        )


def refresh_live_ollama_runtime(default_model: str = "mistral") -> dict[str, str]:
    with _cache_lock():
        try:
            fingerprint, payload = _live_chat_runtime(default_model)
        except Exception:
            fingerprint, payload = _compute_local_chat_runtime(default_model)
        _cache_payload(
            cache_name="ollama_live_runtime_resolution",
            fingerprint=fingerprint,
            payload=payload,
        )
        return _cache_payload(
            cache_name="ollama_runtime_resolution",
            fingerprint=fingerprint,
            payload=payload,
        )


def resolved_ollama_api_base_url() -> str:
    return resolved_ollama_runtime().get("api_base_url") or normalize_ollama_api_base_url("")


def resolved_ollama_base_url() -> str:
    return resolved_ollama_runtime().get("base_url") or strip_api_suffix(
        resolved_ollama_api_base_url()
    )


def resolved_ollama_chat_model(default: str = "mistral") -> str:
    return resolved_ollama_runtime(default).get("chat_model") or default


def resolved_ollama_keep_alive(default: str = "10m") -> str:
    runtime = resolved_ollama_runtime(default_model="mistral")
    keep_alive = str(runtime.get("keep_alive") or "").strip()
    return keep_alive or str(default or "10m").strip() or "10m"


def warm_ollama_chat_runtime(force_refresh: bool = False) -> dict[str, Any]:
    if is_managed_cloud_runtime():
        return {"status": "skipped", "reason": "managed_cloud"}

    if force_refresh:
        clear_ollama_runtime_resolution_cache()
    runtime = refresh_live_ollama_runtime()
    model_name = str(runtime.get("chat_model") or "").strip()
    if not model_name:
        return {"status": "skipped", "reason": "missing_model"}

    keep_alive = str(runtime.get("keep_alive") or "10m").strip() or "10m"
    try:
        client = OllamaHttpClient(
            runtime.get("api_base_url") or resolved_ollama_api_base_url()
        )
        payload = client.warmup_model(model_name, keep_alive=keep_alive)
        refreshed = refresh_live_ollama_runtime()
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
