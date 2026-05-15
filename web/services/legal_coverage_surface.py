"""Superficie admin e wiring runtime per la coverage pipeline legale."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import current_app

from pct.legal_coverage_ai import CoverageAutofillEngine, load_presets
from pct.legal_coverage_pipeline import (
    build_dashboard_payload,
    build_gap_queue,
    generate_drafts,
    publish_approved_drafts,
    run_coverage_audit,
)
from pct.legal_coverage_repository import CoverageDbConfig, PostgresCoverageRepository
from pct.legal_coverage_sqlite_repository import (
    CoverageSqliteConfig,
    SQLiteCoverageRepository,
    derive_legal_coverage_sqlite_db_path,
)
from pct.tenant import GestioneTenant


def _runtime_app_and_config(app: Any | None = None) -> tuple[Any | None, dict[str, Any]]:
    runtime_app = app
    if runtime_app is None and current_app:
        runtime_app = current_app._get_current_object()
    cfg_source = getattr(runtime_app, "config", {}) if runtime_app is not None else {}
    return runtime_app, dict(cfg_source)


def _tenant_manager(cfg_source: dict[str, Any]) -> GestioneTenant | None:
    registry_path = str(cfg_source.get("TENANTS_REGISTRY") or "").strip()
    if not registry_path:
        return None
    try:
        return GestioneTenant(registry_path=registry_path)
    except Exception:
        return None


def _active_tenants(cfg_source: dict[str, Any], manager: GestioneTenant | None = None) -> list[Any]:
    tenants = manager or _tenant_manager(cfg_source)
    if tenants is None:
        return []
    active_states = {"ATTIVO", "TRIAL"}
    return [
        studio
        for studio in tenants.lista()
        if str(getattr(studio, "stato", "") or "").upper() in active_states
    ]


def _shared_sqlite_path(cfg_source: dict[str, Any]) -> str:
    configured = str(
        cfg_source.get("LEGAL_COVERAGE_SQLITE_DB")
        or cfg_source.get("PCT_LEGAL_COVERAGE_SQLITE_DB")
        or os.getenv("LEGAL_COVERAGE_SQLITE_DB")
        or os.getenv("PCT_LEGAL_COVERAGE_SQLITE_DB")
        or ""
    ).strip()
    if configured:
        return configured

    intelligence_anchor = str(cfg_source.get("LEGAL_INTELLIGENCE_DB") or "").strip()
    if intelligence_anchor:
        return derive_legal_coverage_sqlite_db_path(intelligence_anchor)
    clienti_anchor = str(cfg_source.get("CLIENTI_DB") or "").strip()
    if clienti_anchor:
        return str(Path(clienti_anchor).resolve().parent / "intelligence" / "legal_coverage.db")
    return str(Path("intelligence") / "legal_coverage.db")


def _coverage_backend_label(cfg_source: dict[str, Any]) -> str:
    if CoverageDbConfig.from_mapping(cfg_source).configured:
        return "PostgreSQL condiviso"
    return "Archivio coverage condiviso"


def _db_status(repository: Any) -> str:
    if repository.ping():
        return "online"
    if repository.config.configured:
        return "offline"
    return "missing"


def build_repository(
    app: Any | None = None,
    *,
    tenant_slug: str = "",
) -> Any:
    _runtime_app, cfg_source = _runtime_app_and_config(app)
    base_config = CoverageDbConfig.from_mapping(cfg_source)
    if base_config.configured:
        return PostgresCoverageRepository(base_config)
    return SQLiteCoverageRepository(CoverageSqliteConfig(_shared_sqlite_path(cfg_source)))


def build_generator(app: Any | None = None) -> CoverageAutofillEngine:
    _runtime_app, source = _runtime_app_and_config(app)
    ollama_url = str(source.get("LOCAL_AI_BASE_URL") or source.get("PCT_LOCAL_AI_BASE_URL") or "").strip()
    if source.get("TESTING") and not source.get("LEGAL_COVERAGE_ENABLE_LIVE_AI_TESTS"):
        ollama_url = ""
    return CoverageAutofillEngine(
        ollama_url=ollama_url,
        ollama_model=str(source.get("LOCAL_AI_CHAT_MODEL") or source.get("OLLAMA_MODEL") or "mistral").strip(),
        presets=load_presets(),
    )


def build_legal_coverage_surface(
    app: Any | None = None,
    *,
    tenant_slug: str = "",
) -> dict[str, Any]:
    _runtime_app, cfg_source = _runtime_app_and_config(app)
    repository = build_repository(app)
    active_tenants = _active_tenants(cfg_source)
    runtime_status = _db_status(repository)
    runtime = {
        "db_configured": repository.config.configured,
        "db_online": runtime_status == "online",
        "db_status": runtime_status,
        "db_backend_label": _coverage_backend_label(cfg_source),
        "db_path": str(getattr(repository, "db_path", "") or ""),
        "ollama_url": str(cfg_source.get("LOCAL_AI_BASE_URL") or ""),
        "ollama_model": str(cfg_source.get("LOCAL_AI_CHAT_MODEL") or cfg_source.get("OLLAMA_MODEL") or ""),
        "tenant_slug": "",
        "tenant_name": "",
        "tenant_registry_name": "",
        "tenant_configured_name": "",
        "tenant_name_mismatch": False,
        "tenant_choices": [],
        "tenant_count": len(active_tenants),
        "storage_scope": "shared_platform",
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


def run_action(action: str, *, limit: int = 20, tenant_slug: str = "") -> dict[str, Any]:
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
