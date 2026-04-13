"""Helper governabile per l'accesso al servizio AI locale nell'app Flask."""

from __future__ import annotations

from pathlib import Path

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


def get_local_ai_service() -> LocalAIService:
    if not hasattr(g, "_local_ai"):
        app = current_app._get_current_object()
        g._local_ai = LocalAIService(
            db_path=_cfg_data_path("LOCAL_AI_DB"),
            policy_path=app.config.get("LOCAL_AI_POLICY", "./config/ai-policy.json"),
            config_path=app.config.get("STUDIO_CONFIG", "./config/studio.json"),
            app_root=str(Path(__file__).resolve().parents[2]),
            models_path=_cfg_data_path("LOCAL_AI_MODELS_DIR"),
        )
    return g._local_ai
