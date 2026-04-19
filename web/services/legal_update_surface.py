from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context, request

from pct.legal_update_pipeline import LegalUpdatePipeline, build_legal_update_pipeline
from pct.legal_update_repository import LegalUpdateDbConfig
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from pct.tenant import GestioneTenant, normalize_db_mode


def _runtime_app_and_config(app: Any | None = None) -> tuple[Any | None, dict[str, Any]]:
    runtime_app = app
    if runtime_app is None and has_app_context():
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


def _resolve_runtime_tenant(
    cfg_source: dict[str, Any],
    *,
    explicit_tenant_slug: str = "",
) -> Any | None:
    manager = _tenant_manager(cfg_source)
    active_tenants = _active_tenants(cfg_source, manager=manager)
    requested_slug = _resolve_requested_tenant_slug(explicit_tenant_slug)
    if requested_slug:
        if manager is not None:
            return manager.get(requested_slug)
        return None

    tenant = getattr(g, "tenant", None) if has_request_context() else None
    if tenant is not None:
        return tenant

    if len(active_tenants) == 1:
        return active_tenants[0]
    if active_tenants:
        # In console piattaforma evitiamo il repository globale legacy:
        # se non e' stato scelto uno studio, usiamo comunque il primo tenant attivo.
        return active_tenants[0]
    return None


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


def _load_single_studio_payload(cfg_source: dict[str, Any]) -> dict[str, Any]:
    config_path = Path(str(cfg_source.get("STUDIO_CONFIG") or "").strip())
    if not config_path.is_file():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _tenant_name_bundle(manager: GestioneTenant | None, studio: Any = None) -> dict[str, Any]:
    payload = _load_tenant_studio_payload(manager, studio)
    registry_name = str(getattr(studio, "nome", "") or "").strip()
    configured_name = str(((payload.get("studio") or {}).get("nome")) or "").strip()
    mismatch = bool(
        registry_name
        and configured_name
        and registry_name.casefold() != configured_name.casefold()
    )
    display_name = registry_name or configured_name
    return {
        "registry_name": registry_name,
        "configured_name": configured_name,
        "display_name": display_name,
        "mismatch": mismatch,
    }


def _display_single_studio_name(cfg_source: dict[str, Any]) -> str:
    payload = _load_single_studio_payload(cfg_source)
    return str(((payload.get("studio") or {}).get("nome")) or "").strip()


def _backend_label(cfg_source: dict[str, Any], studio: Any = None) -> str:
    tenant_database = getattr(studio, "database", None)
    effective_kind = str(getattr(tenant_database, "effective_runtime_kind", "") or "").strip().lower()
    if effective_kind == "postgresql":
        return "PostgreSQL tenant-aware"
    if effective_kind == "sqlite":
        return "SQL locale tenant-aware"
    if effective_kind == "json":
        return "JSON locale tenant-aware"

    normalized_mode = str(
        getattr(tenant_database, "normalized_mode", "")
        or normalize_db_mode(getattr(tenant_database, "mode", ""))
    ).strip().upper()
    if normalized_mode == "POSTGRESQL":
        return "PostgreSQL tenant-aware"
    if normalized_mode == "SQLITE":
        return "SQL locale tenant-aware"
    if normalized_mode == "JSON":
        return "JSON locale tenant-aware"
    if not studio:
        return "Archivio locale applicativo"
    return normalized_mode or "n.d."


def _tenant_choices_payload(cfg_source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manager = _tenant_manager(cfg_source)
    for studio in _active_tenants(cfg_source, manager=manager):
        name_bundle = _tenant_name_bundle(manager, studio)
        rows.append(
            {
                "slug": str(getattr(studio, "slug", "") or ""),
                "nome": name_bundle["registry_name"] or name_bundle["display_name"],
                "configured_name": name_bundle["configured_name"],
                "name_mismatch": name_bundle["mismatch"],
                "db_mode": _backend_label(cfg_source, studio),
            }
        )
    return rows


def _repository_data_count(db_path: str) -> int:
    target = Path(str(db_path or "").strip())
    if not target.exists():
        return 0
    try:
        with sqlite3.connect(str(target)) as conn:
            total = 0
            for table in (
                "source_documents_raw",
                "ai_documents_analysis",
                "review_queue",
                "normative",
                "jurisprudence",
                "prassi",
                "news",
            ):
                try:
                    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                except sqlite3.Error:
                    continue
                total += int((row or [0])[0] or 0)
            return total
    except sqlite3.Error:
        return 0


def _bootstrap_legacy_legal_updates(
    cfg_source: dict[str, Any],
    *,
    manager: GestioneTenant | None,
    studio: Any | None,
    target_paths: dict[str, str],
) -> None:
    if manager is None or studio is None:
        return
    root_anchor = str(cfg_source.get("LEGAL_INTELLIGENCE_DB") or "").strip()
    target_anchor = str(target_paths.get("LEGAL_INTELLIGENCE_DB") or "").strip()
    if not root_anchor or not target_anchor:
        return
    root_anchor_path = Path(root_anchor).resolve()
    target_anchor_path = Path(target_anchor).resolve()
    if root_anchor_path == target_anchor_path:
        return

    target_database = getattr(studio, "database", None)
    if str(getattr(target_database, "effective_runtime_kind", "") or "").strip().lower() == "postgresql":
        return

    root_cfg = LegalUpdateDbConfig.from_anchor(str(root_anchor_path))
    target_cfg = LegalUpdateDbConfig.from_anchor(str(target_anchor_path))
    if _repository_data_count(target_cfg.db_path) > 0:
        return
    if _repository_data_count(root_cfg.db_path) <= 0:
        return

    source_db = Path(root_cfg.db_path)
    target_db = Path(target_cfg.db_path)
    if source_db.is_file():
        target_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_db, target_db)

    source_json = Path(root_cfg.json_path)
    target_json = Path(target_cfg.json_path)
    if source_json.is_file():
        target_json.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_json, target_json)


def build_legal_update_pipeline_runtime(
    app: Any | None = None,
    *,
    tenant_slug: str = "",
) -> LegalUpdatePipeline:
    runtime_app, cfg_source = _runtime_app_and_config(app)
    manager = _tenant_manager(cfg_source)
    studio = _resolve_runtime_tenant(cfg_source, explicit_tenant_slug=tenant_slug)
    tenant_paths = (
        manager.percorsi_dati(str(getattr(studio, "slug", "") or "").strip().lower())
        if manager is not None and studio is not None
        else {}
    )
    if tenant_paths:
        _bootstrap_legacy_legal_updates(
            cfg_source,
            manager=manager,
            studio=studio,
            target_paths=tenant_paths,
        )

    intelligence_db = str(
        tenant_paths.get("LEGAL_INTELLIGENCE_DB")
        or cfg_source.get("LEGAL_INTELLIGENCE_DB")
        or "./intelligence/motori.json"
    )
    giurisprudenza_db_path = str(
        tenant_paths.get("GIURISPRUDENZA_DB")
        or cfg_source.get("GIURISPRUDENZA_DB")
        or ""
    )
    postgres_dsn = resolve_runtime_postgres_dsn(
        database=getattr(studio, "database", None),
        config=cfg_source,
    )
    return build_legal_update_pipeline(
        intelligence_db,
        giurisprudenza_db_path=giurisprudenza_db_path,
        ai_base_url=str(
            cfg_source.get("LOCAL_AI_BASE_URL")
            or cfg_source.get("PCT_LOCAL_AI_BASE_URL")
            or ""
        ).strip(),
        ai_model=str(
            cfg_source.get("LOCAL_AI_CHAT_MODEL")
            or cfg_source.get("OLLAMA_MODEL")
            or "mistral"
        ).strip(),
        postgres_dsn=postgres_dsn,
    )


def build_legal_update_surface(
    app: Any | None = None,
    *,
    tenant_slug: str = "",
) -> dict[str, Any]:
    runtime_app, cfg_source = _runtime_app_and_config(app)
    manager = _tenant_manager(cfg_source)
    studio = _resolve_runtime_tenant(cfg_source, explicit_tenant_slug=tenant_slug)
    tenant_name_bundle = _tenant_name_bundle(manager, studio) if studio is not None else {
        "registry_name": "",
        "configured_name": "",
        "display_name": "",
        "mismatch": False,
    }
    pipeline = build_legal_update_pipeline_runtime(runtime_app, tenant_slug=tenant_slug)
    snapshot = pipeline.dashboard_snapshot()
    snapshot["runtime"] = {
        "db_path": pipeline.repository.db_path,
        "json_path": pipeline.repository.json_path,
        "backend_kind": getattr(pipeline.repository, "backend_kind", "sqlite"),
        "db_backend_label": _backend_label(cfg_source, studio),
        "postgres_enabled": bool(getattr(pipeline, "postgres_dsn", "")),
        "ollama_url": pipeline.ai_base_url,
        "ollama_model": pipeline.ai_model,
        "giurisprudenza_db_path": pipeline.giurisprudenza_db_path,
        "tenant_slug": str(getattr(studio, "slug", "") or _resolve_requested_tenant_slug(tenant_slug)).strip().lower(),
        "tenant_name": (
            tenant_name_bundle["display_name"]
            or ("" if manager is not None else _display_single_studio_name(cfg_source))
        ),
        "tenant_registry_name": tenant_name_bundle["registry_name"],
        "tenant_configured_name": tenant_name_bundle["configured_name"],
        "tenant_name_mismatch": tenant_name_bundle["mismatch"],
        "tenant_choices": _tenant_choices_payload(cfg_source),
    }
    return snapshot


def run_legal_update_action(
    action: str,
    *,
    source_codes: list[str] | None = None,
    tenant_slug: str = "",
) -> dict[str, Any]:
    pipeline = build_legal_update_pipeline_runtime(tenant_slug=tenant_slug)
    if action == "scan":
        return pipeline.run_cycle(source_codes=source_codes)
    if action == "autopublish":
        return pipeline.publish_auto_news(limit=40)
    raise ValueError(f"Azione non supportata: {action}")
