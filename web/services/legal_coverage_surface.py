"""Superficie admin e wiring runtime per la coverage pipeline legale."""

from __future__ import annotations

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


def _active_tenants(cfg_source: dict[str, Any]) -> list[Any]:
    registry_path = str(cfg_source.get("TENANTS_REGISTRY") or "").strip()
    if not registry_path:
        return []
    try:
        tenants = GestioneTenant(registry_path=registry_path)
    except Exception:
        return []
    active_states = {"ATTIVO", "TRIAL"}
    return [
        studio
        for studio in tenants.lista()
        if str(getattr(studio, "stato", "") or "").upper() in active_states
    ]


def _resolve_runtime_tenant(
    cfg_source: dict[str, Any],
    *,
    explicit_tenant_slug: str = "",
) -> Any | None:
    tenant = getattr(g, "tenant", None) if has_request_context() else None
    if tenant is not None:
        return tenant

    active_tenants = _active_tenants(cfg_source)
    requested_slug = _resolve_requested_tenant_slug(explicit_tenant_slug)
    if requested_slug:
        for studio in active_tenants:
            if str(getattr(studio, "slug", "") or "").strip().lower() == requested_slug:
                return studio
        return None

    if len(active_tenants) == 1:
        return active_tenants[0]
    return None


def _tenant_choices_payload(cfg_source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for studio in _active_tenants(cfg_source):
        database = getattr(studio, "database", None)
        rows.append(
            {
                "slug": str(getattr(studio, "slug", "") or ""),
                "nome": str(getattr(studio, "nome", "") or ""),
                "db_mode": str(getattr(database, "normalized_mode", "") or normalize_db_mode(getattr(database, "mode", ""))),
            }
        )
    return rows


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
) -> PostgresCoverageRepository:
    runtime_app, cfg_source = _runtime_app_and_config(app)
    base_config = CoverageDbConfig.from_mapping(cfg_source)
    resolved_tenant = _resolve_runtime_tenant(cfg_source, explicit_tenant_slug=tenant_slug)
    tenant_database = getattr(resolved_tenant, "database", None)
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
    runtime = {
        "db_configured": repository.config.configured,
        "db_online": repository.ping(),
        "ollama_url": str(cfg_source.get("LOCAL_AI_BASE_URL") or ""),
        "ollama_model": str(cfg_source.get("LOCAL_AI_CHAT_MODEL") or cfg_source.get("OLLAMA_MODEL") or ""),
        "tenant_slug": str(getattr(resolved_tenant, "slug", "") or ""),
        "tenant_name": str(getattr(resolved_tenant, "nome", "") or ""),
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
