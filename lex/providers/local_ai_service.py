"""Servizio AI locale posseduto dal package Lex."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from flask import current_app, g, has_request_context

from pct.local_ai import LocalAIService


def _cfg_data_path(key: str) -> str:
    app = current_app._get_current_object()
    paths = getattr(g, "data_paths", {}) or {}
    multi_tenant = app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False)
    if multi_tenant:
        from web.services.tenant_isolation_runtime import assert_tenant_data_path

        if not paths.get(key) or getattr(g, "tenant_context_missing", False):
            raise RuntimeError("Contesto studio non disponibile per la ricerca locale")
        return assert_tenant_data_path(paths[key], key=key)
    if has_request_context():
        return paths.get(key, app.config[key])
    return app.config[key]


def _service_config(app) -> dict[str, str]:
    return {
        "db_path": _cfg_data_path("LOCAL_AI_DB"),
        "policy_path": app.config.get("LOCAL_AI_POLICY", "./config/ai-policy.json"),
        "config_path": _cfg_data_path("CONFIG_STUDIO_DB") if app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False) else app.config.get("STUDIO_CONFIG", "./config/studio.json"),
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
        service.registro_letture = _registro_letture_corrente
        service.source_verifier = _verifica_fonti_sql_correnti
        registry[key] = service
        return service


def _registro_letture_corrente():
    """Il registro delle letture dello studio della richiesta corrente; None fuori da Flask."""
    try:
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        return registro_corrente(), tenant_corrente()
    except Exception:
        return None


def _verifica_fonti_sql_correnti(rows):
    from pct.document_intelligence.security import assert_user_can_read
    from pct.rag_source_provenance import verify_current_sql
    from web.services.document_intelligence_runtime import (
        document_ai_tenant_id,
        document_ai_user_context, fascicoli_db_path,
    )
    from web.services.storage_runtime import get_request_studio_db

    assert_user_can_read(document_ai_user_context())
    tenant = document_ai_tenant_id()
    core = get_request_studio_db(fascicoli_db_path())
    if core is None:
        raise RuntimeError("Riscontro delle fonti SQL non disponibile")
    accepted, checks = verify_current_sql(rows, tenant=tenant, core=core)
    if has_request_context():
        g.rag_source_checks = checks
    return accepted, checks


__all__ = ["get_local_ai_service"]
