"""Servizio AI locale posseduto dal package Lex."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from flask import current_app, g, has_request_context

from pct.local_ai import LocalAIService
from pct.runtime_env import is_managed_cloud_runtime


def _cfg_data_path(key: str) -> str:
    app = current_app._get_current_object()
    if is_managed_cloud_runtime() and key in {"LOCAL_AI_DB", "LOCAL_AI_MODELS_DIR"}:
        return app.config[key]
    if has_request_context():
        paths = getattr(g, "data_paths", {}) or {}
        return paths.get(key, app.config[key])
    return app.config[key]


def _service_config(app) -> dict[str, str]:
    return {
        "db_path": _cfg_data_path("LOCAL_AI_DB"),
        "policy_path": app.config.get("LOCAL_AI_POLICY", "./config/ai-policy.json"),
        "config_path": app.config.get("STUDIO_CONFIG", "./config/studio.json"),
        "app_root": str(Path(__file__).resolve().parents[2]),
        "models_path": _cfg_data_path("LOCAL_AI_MODELS_DIR"),
    }


def _service_key(app) -> tuple[str, str, str, str, str]:
    cfg = _service_config(app)
    return (
        cfg["db_path"],
        cfg["policy_path"],
        cfg["config_path"],
        cfg["app_root"],
        cfg["models_path"],
    )


def _service_registry(app) -> dict[tuple[str, str, str, str, str], LocalAIService]:
    return app.extensions.setdefault("local_ai_services", {})


def _service_lock(app) -> Lock:
    lock = app.extensions.get("local_ai_services_lock")
    if lock is None:
        lock = Lock()
        app.extensions["local_ai_services_lock"] = lock
    return lock


def get_local_ai_service() -> LocalAIService:
    app = current_app._get_current_object()
    key = _service_key(app)
    registry = _service_registry(app)
    service = registry.get(key)
    if service is not None:
        return service

    with _service_lock(app):
        service = registry.get(key)
        if service is not None:
            return service

        cfg = _service_config(app)
        service = LocalAIService(
            db_path=cfg["db_path"],
            policy_path=cfg["policy_path"],
            config_path=cfg["config_path"],
            app_root=cfg["app_root"],
            models_path=cfg["models_path"],
        )
        registry[key] = service
        return service


__all__ = ["get_local_ai_service"]
