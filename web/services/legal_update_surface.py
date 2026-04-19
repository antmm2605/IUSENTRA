from __future__ import annotations

from typing import Any

from flask import current_app

from pct.legal_update_pipeline import LegalUpdatePipeline, build_legal_update_pipeline
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn


def build_legal_update_pipeline_runtime(app: Any | None = None) -> LegalUpdatePipeline:
    source = (app or current_app)._get_current_object().config if app or current_app else {}
    return build_legal_update_pipeline(
        str(source.get("LEGAL_INTELLIGENCE_DB") or "./intelligence/motori.json"),
        giurisprudenza_db_path=str(source.get("GIURISPRUDENZA_DB") or ""),
        ai_base_url=str(source.get("LOCAL_AI_BASE_URL") or source.get("PCT_LOCAL_AI_BASE_URL") or "").strip(),
        ai_model=str(source.get("LOCAL_AI_CHAT_MODEL") or source.get("OLLAMA_MODEL") or "mistral").strip(),
        postgres_dsn=resolve_runtime_postgres_dsn(config=source),
    )


def build_legal_update_surface(app: Any | None = None) -> dict[str, Any]:
    pipeline = build_legal_update_pipeline_runtime(app)
    snapshot = pipeline.dashboard_snapshot()
    snapshot["runtime"] = {
        "db_path": pipeline.repository.db_path,
        "json_path": pipeline.repository.json_path,
        "backend_kind": getattr(pipeline.repository, "backend_kind", "sqlite"),
        "postgres_enabled": bool(getattr(pipeline, "postgres_dsn", "")),
        "ollama_url": pipeline.ai_base_url,
        "ollama_model": pipeline.ai_model,
        "giurisprudenza_db_path": pipeline.giurisprudenza_db_path,
    }
    return snapshot


def run_legal_update_action(action: str, *, source_codes: list[str] | None = None) -> dict[str, Any]:
    pipeline = build_legal_update_pipeline_runtime()
    if action == "scan":
        return pipeline.run_cycle(source_codes=source_codes)
    if action == "autopublish":
        return pipeline.publish_auto_news(limit=40)
    raise ValueError(f"Azione non supportata: {action}")
