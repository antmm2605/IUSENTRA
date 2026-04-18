"""Superficie admin e wiring runtime per la coverage pipeline legale."""

from __future__ import annotations

from typing import Any

from flask import current_app

from pct.legal_coverage_ai import CoverageAutofillEngine, load_presets
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from pct.legal_coverage_pipeline import (
    build_dashboard_payload,
    build_gap_queue,
    generate_drafts,
    publish_approved_drafts,
    run_coverage_audit,
)
from pct.legal_coverage_repository import CoverageDbConfig, PostgresCoverageRepository


def build_repository(app: Any | None = None) -> PostgresCoverageRepository:
    runtime_app = app
    if runtime_app is None and current_app:
        runtime_app = current_app._get_current_object()
    cfg_source = getattr(runtime_app, "config", {}) if runtime_app is not None else {}
    base_config = CoverageDbConfig.from_mapping(cfg_source)
    runtime_dsn = resolve_runtime_postgres_dsn(
        base_config.dsn,
        database=cfg_source.get("TENANT_DATABASE_CONFIG"),
        config=cfg_source,
        env_url_keys=("LEGAL_COVERAGE_DB_URL", "PCT_LEGAL_COVERAGE_DB_URL"),
    )
    if runtime_dsn:
        return PostgresCoverageRepository(
            CoverageDbConfig(
                dsn=runtime_dsn,
                host=base_config.host,
                port=base_config.port,
                dbname=base_config.dbname,
                user=base_config.user,
                password=base_config.password,
                explicit=True,
            )
        )
    return PostgresCoverageRepository(base_config)


def build_generator(app: Any | None = None) -> CoverageAutofillEngine:
    runtime_app = app
    if runtime_app is None and current_app:
        runtime_app = current_app._get_current_object()
    source = getattr(runtime_app, "config", {}) if runtime_app is not None else {}
    return CoverageAutofillEngine(
        ollama_url=str(source.get("LOCAL_AI_BASE_URL") or source.get("PCT_LOCAL_AI_BASE_URL") or "").strip(),
        ollama_model=str(source.get("LOCAL_AI_CHAT_MODEL") or source.get("OLLAMA_MODEL") or "mistral").strip(),
        presets=load_presets(),
    )


def build_legal_coverage_surface(app: Any | None = None) -> dict[str, Any]:
    runtime_app = app
    if runtime_app is None and current_app:
        runtime_app = current_app._get_current_object()
    repository = build_repository(app)
    runtime = {
        "db_configured": repository.config.configured,
        "db_online": repository.ping(),
        "ollama_url": str(getattr(runtime_app, "config", {}).get("LOCAL_AI_BASE_URL") or ""),
        "ollama_model": str(getattr(runtime_app, "config", {}).get("LOCAL_AI_CHAT_MODEL") or getattr(runtime_app, "config", {}).get("OLLAMA_MODEL") or ""),
    }
    if not runtime["db_online"]:
        return {
            "runtime": runtime,
            "headline": {
                "coverage_medio": 0,
                "subbranch_ready": 0,
                "subbranch_parziali": 0,
                "gap_aperti": 0,
                "draft_review": 0,
                "training_implicito": 0,
            },
            "snapshots": [],
            "gaps": [],
            "drafts": [],
            "history": [],
        }

    payload = build_dashboard_payload(repository)
    payload["runtime"] = runtime
    return payload


def run_action(action: str, *, limit: int = 20) -> dict[str, Any]:
    repository = build_repository()
    if not repository.ping():
        raise RuntimeError("Database coverage non raggiungibile.")

    if action == "audit":
        return run_coverage_audit(repository)
    if action == "gaps":
        return build_gap_queue(repository)
    if action == "drafts":
        return generate_drafts(repository, build_generator(), limit=limit)
    if action == "publish":
        return publish_approved_drafts(repository, limit=limit, apply_to_db=True)
    raise ValueError(f"Azione non supportata: {action}")
