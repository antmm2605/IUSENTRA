"""Superficie admin e wiring runtime per la coverage pipeline legale."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import current_app, g, has_request_context, request

from pct.legal_coverage_ai import CoverageAutofillEngine, load_presets
from pct.storage_postgres import build_postgres_dsn
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from pct.legal_coverage_pipeline import (
    build_dashboard_payload,
    build_gap_queue,
    generate_drafts,
    publish_approved_drafts,
    run_coverage_audit,
)
from pct.legal_coverage_repository import CoverageDbConfig, PostgresCoverageRepository
from pct.legal_coverage_sqlite_repository import CoverageSqliteConfig, SQLiteCoverageRepository
from pct.tenant import GestioneTenant, normalize_db_mode


def _runtime_app_and_config(app: Any | None = None) -> tuple[Any | None, dict[str, Any]]:
    runtime_app = app
    if runtime_app is None and current_app:
        runtime_app = current_app._get_current_object()
    cfg_source = getattr(runtime_app, "config", {}) if runtime_app is not None else {}
    return runtime_app, dict(cfg_source)


def _resolve_requested_tenant_slug(explicit_tenant_slug: str = "") -> str:
    if str(explicit_tenant_slug or "").strip():
        return str(explicit_tenant_slug).strip().lower()
    if has_request_context():
        for source in (
            request.values.get("tenant_slug"),
            request.args.get("tenant_slug"),
        ):
            slug = str(source or "").strip().lower()
            if slug:
                return slug
        tenant = getattr(g, "tenant", None)
        tenant_slug = str(getattr(tenant, "slug", "") or "").strip().lower()
        if tenant_slug:
            return tenant_slug
    return ""


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


def _load_tenant_studio_payload(manager: GestioneTenant | None, studio: Any = None) -> dict[str, Any]:
    if manager is None or studio is None:
        return {}
    slug = str(getattr(studio, "slug", "") or "").strip().lower()
    if not slug:
        return {}
    try:
        config_path = Path(manager.percorsi_dati(slug).get("CONFIG_STUDIO_DB") or "")
    except Exception:
        return {}
    if not config_path.is_file():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _display_tenant_name(manager: GestioneTenant | None, studio: Any = None) -> str:
    payload = _load_tenant_studio_payload(manager, studio)
    configured_name = str(((payload.get("studio") or {}).get("nome")) or "").strip()
    if configured_name:
        return configured_name
    return str(getattr(studio, "nome", "") or "").strip()


def _coverage_backend_code(cfg_source: dict[str, Any], studio: Any = None) -> str:
    tenant_database = getattr(studio, "database", None)
    runtime_dsn = resolve_runtime_postgres_dsn(
        "",
        database=tenant_database or cfg_source.get("TENANT_DATABASE_CONFIG"),
        config=cfg_source,
        env_url_keys=("LEGAL_COVERAGE_DB_URL", "PCT_LEGAL_COVERAGE_DB_URL"),
    )
    if not runtime_dsn:
        runtime_dsn = _legacy_tenant_postgres_dsn(tenant_database)
    if runtime_dsn:
        return "POSTGRESQL"
    normalized_mode = str(
        getattr(tenant_database, "normalized_mode", "") or normalize_db_mode(getattr(tenant_database, "mode", ""))
    ).strip()
    return normalized_mode or "JSON"


def _coverage_backend_label(cfg_source: dict[str, Any], studio: Any = None) -> str:
    code = _coverage_backend_code(cfg_source, studio)
    labels = {
        "POSTGRESQL": "PostgreSQL tenant-aware",
        "SQLITE": "SQLite locale",
        "JSON": "JSON locale",
        "MYSQL": "MySQL esterno",
    }
    return labels.get(code, code.title() if code else "Non configurato")


def _db_status(repository: PostgresCoverageRepository) -> str:
    if repository.ping():
        return "online"
    if repository.config.configured:
        return "offline"
    return "missing"


def _tenant_choices_payload(cfg_source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manager = _tenant_manager(cfg_source)
    for studio in _active_tenants(cfg_source, manager=manager):
        rows.append(
            {
                "slug": str(getattr(studio, "slug", "") or ""),
                "nome": _display_tenant_name(manager, studio),
                "db_mode": _coverage_backend_label(cfg_source, studio),
            }
        )
    return rows


def _resolve_runtime_tenant(
    cfg_source: dict[str, Any],
    *,
    explicit_tenant_slug: str = "",
) -> Any | None:
    manager = _tenant_manager(cfg_source)
    active_tenants = _active_tenants(cfg_source, manager=manager)
    requested_slug = _resolve_requested_tenant_slug(explicit_tenant_slug)
    if requested_slug:
        for studio in active_tenants:
            if str(getattr(studio, "slug", "") or "").strip().lower() == requested_slug:
                return studio
        return None

    tenant = getattr(g, "tenant", None) if has_request_context() else None
    if tenant is not None:
        return tenant

    if len(active_tenants) == 1:
        return active_tenants[0]
    return None


def _legacy_tenant_postgres_dsn(database: Any = None) -> str:
    if database is None:
        return ""
    normalized_mode = str(
        getattr(database, "normalized_mode", "") or normalize_db_mode(getattr(database, "mode", ""))
    ).strip().upper()
    if normalized_mode == "MYSQL":
        return ""

    host = str(getattr(database, "host", "") or "").strip()
    db_name = str(getattr(database, "db_name", "") or "").strip()
    user = str(getattr(database, "utente", "") or "").strip()
    password = str(getattr(database, "password", "") or "")
    port = int(getattr(database, "porta_effettiva", 0) or getattr(database, "porta", 0) or 5432)
    ssl = bool(getattr(database, "ssl", False))

    if not all((host, db_name, user)):
        return ""

    host_lower = host.lower()
    looks_postgres = normalized_mode == "POSTGRESQL" or port == 5432 or any(
        marker in host_lower for marker in ("postgres", "neon.tech", "pooler")
    )
    if not looks_postgres:
        return ""

    return build_postgres_dsn(
        host=host,
        port=port,
        db_name=db_name,
        user=user,
        password=password,
        ssl=ssl,
    )


def build_repository(
    app: Any | None = None,
    *,
    tenant_slug: str = "",
) -> Any:
    runtime_app, cfg_source = _runtime_app_and_config(app)
    base_config = CoverageDbConfig.from_mapping(cfg_source)
    resolved_tenant = _resolve_runtime_tenant(cfg_source, explicit_tenant_slug=tenant_slug)
    tenant_database = getattr(resolved_tenant, "database", None)
    tenant_slug_resolved = str(getattr(resolved_tenant, "slug", "") or "").strip().lower()
    manager = _tenant_manager(cfg_source)
    tenant_paths = manager.percorsi_dati(tenant_slug_resolved) if manager and tenant_slug_resolved else {}

    if getattr(tenant_database, "is_sqlite", False):
        sqlite_path = str(tenant_paths.get("STUDIO_DB") or "").strip()
        return SQLiteCoverageRepository(CoverageSqliteConfig(sqlite_path))

    runtime_dsn = resolve_runtime_postgres_dsn(
        base_config.dsn,
        database=tenant_database or cfg_source.get("TENANT_DATABASE_CONFIG"),
        config=cfg_source,
        env_url_keys=("LEGAL_COVERAGE_DB_URL", "PCT_LEGAL_COVERAGE_DB_URL"),
    )
    if not runtime_dsn:
        runtime_dsn = _legacy_tenant_postgres_dsn(tenant_database)
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
            ),
        )
    return PostgresCoverageRepository(base_config)


def build_generator(app: Any | None = None) -> CoverageAutofillEngine:
    runtime_app, source = _runtime_app_and_config(app)
    return CoverageAutofillEngine(
        ollama_url=str(source.get("LOCAL_AI_BASE_URL") or source.get("PCT_LOCAL_AI_BASE_URL") or "").strip(),
        ollama_model=str(source.get("LOCAL_AI_CHAT_MODEL") or source.get("OLLAMA_MODEL") or "mistral").strip(),
        presets=load_presets(),
    )


def build_legal_coverage_surface(
    app: Any | None = None,
    *,
    tenant_slug: str = "",
) -> dict[str, Any]:
    runtime_app, cfg_source = _runtime_app_and_config(app)
    resolved_tenant = _resolve_runtime_tenant(cfg_source, explicit_tenant_slug=tenant_slug)
    repository = build_repository(app, tenant_slug=tenant_slug)
    manager = _tenant_manager(cfg_source)
    runtime_status = _db_status(repository)
    tenant_name = _display_tenant_name(manager, resolved_tenant)
    runtime = {
        "db_configured": repository.config.configured,
        "db_online": runtime_status == "online",
        "db_status": runtime_status,
        "db_backend_label": _coverage_backend_label(cfg_source, resolved_tenant),
        "ollama_url": str(cfg_source.get("LOCAL_AI_BASE_URL") or ""),
        "ollama_model": str(cfg_source.get("LOCAL_AI_CHAT_MODEL") or cfg_source.get("OLLAMA_MODEL") or ""),
        "tenant_slug": str(getattr(resolved_tenant, "slug", "") or ""),
        "tenant_name": tenant_name,
        "tenant_choices": _tenant_choices_payload(cfg_source),
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
    repository = build_repository(tenant_slug=tenant_slug)
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
