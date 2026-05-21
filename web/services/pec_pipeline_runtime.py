"""Runtime tenant-aware per worker e digest della pipeline PEC."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flask import current_app, g, has_app_context

from pct.pec_pipeline import PecAuditRepository


def _path_from_mapping(paths: Mapping[str, Any], key: str, default: str) -> str:
    value = paths.get(key)
    if value:
        return str(value)
    if has_app_context() and current_app.config.get(key):
        return str(current_app.config[key])
    return default


def repository_from_paths(paths: Mapping[str, Any], *, tenant_label: str = "default") -> PecAuditRepository:
    email_db = Path(_path_from_mapping(paths, "EMAIL_CASELLA_DB", "./email/casella.json"))
    audit_db = Path(str(paths.get("PEC_AUDIT_DB") or email_db.parent / "pec_audit.sqlite"))
    return PecAuditRepository(
        audit_db,
        tenant_id=str(tenant_label or "default"),
        fascicoli_db_path=_path_from_mapping(paths, "FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        fascicoli_docs_path=_path_from_mapping(paths, "FASCICOLI_DOCS", "./fascicoli/documenti"),
        scadenziario_db_path=_path_from_mapping(paths, "SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
    )


def repository_for_current_request() -> PecAuditRepository:
    paths = getattr(g, "data_paths", {}) if has_app_context() else {}
    tenant = ""
    if has_app_context():
        tenant = str(g.get("tenant_slug", "") or g.get("auth_tenant_slug", "") or "")
    return repository_from_paths(paths or {}, tenant_label=tenant or "default")


def run_workers_for_paths(paths: Mapping[str, Any], *, tenant_label: str, limit: int = 200) -> dict[str, Any]:
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    return repo.run_pending_jobs(limit=limit, actor="scheduler")


def build_digest_for_paths(paths: Mapping[str, Any], *, tenant_label: str, digest_date: str | None = None) -> dict[str, Any]:
    repo = repository_from_paths(paths, tenant_label=tenant_label)
    return repo.build_daily_digest(digest_date=digest_date, actor="scheduler")
