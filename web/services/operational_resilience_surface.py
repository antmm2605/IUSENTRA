"""Superficie admin per crash test operativo, repair loop e backup blindato."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import current_app

from pct.backup import GestioneBackup, backup_operations_disabled
from pct.core_storage_backend import is_postgres_core_active
from pct.operational_resilience import (
    OPERATIONAL_BACKUP_SCHEDULE,
    OPERATIONAL_CRASH_SCHEDULES,
    run_operational_backup_plan,
    run_operational_crash_test,
)
from pct.operational_resilience_repository import OperationalResilienceRepository
from pct.postgres_runtime_support import database_config_to_dsn
from pct.tenant import GestioneTenant
from web.services.system_health_surface import build_system_health_api_payload


def _tenant_manager() -> GestioneTenant | None:
    registry = str(current_app.config.get("TENANTS_REGISTRY") or "").strip()
    if not registry:
        return None
    try:
        return GestioneTenant(registry_path=registry)
    except Exception:
        return None


def _active_tenants() -> list[Any]:
    manager = _tenant_manager()
    if manager is None:
        return []
    active_states = {"ATTIVO", "TRIAL"}
    return [
        studio
        for studio in manager.lista()
        if str(getattr(studio, "stato", "") or "").upper() in active_states
    ]


def _resolve_context(selected_slug: str = "") -> dict[str, Any]:
    manager = _tenant_manager()
    active_tenants = _active_tenants()
    requested = str(selected_slug or "").strip().lower()
    studio = None
    if requested and manager is not None:
        studio = manager.get(requested)
    elif len(active_tenants) == 1:
        studio = active_tenants[0]

    if studio is not None and manager is not None:
        slug = str(getattr(studio, "slug", "") or "").strip().lower()
        paths = manager.percorsi_dati(slug)
        studio_name = str(getattr(studio, "nome", "") or "").strip()
        config_path = Path(paths.get("CONFIG_STUDIO_DB") or "")
        configured_name = ""
        if config_path.is_file():
            try:
                payload = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            configured_name = str(((payload.get("studio") or {}).get("nome")) or "").strip()
        sqlite_path = str(Path(paths["BACKUP_DIR"]) / "operational_resilience.db")
        postgres_dsn = ""
        if is_postgres_core_active(getattr(studio, "database", None)):
            postgres_dsn = database_config_to_dsn(getattr(studio, "database", None))
        return {
            "tenant_slug": slug,
            "studio_nome": studio_name or configured_name or slug,
            "configured_name": configured_name,
            "tenant_choices": [
                {
                    "slug": str(getattr(item, "slug", "") or ""),
                    "nome": str(getattr(item, "nome", "") or ""),
                    "selected_mode": str(getattr(getattr(item, "database", None), "normalized_mode", "") or ""),
                    "selected": str(getattr(item, "slug", "") or "").strip().lower() == slug,
                }
                for item in active_tenants
            ],
            "paths": paths,
            "sqlite_path": sqlite_path,
            "postgres_dsn": postgres_dsn,
            "backend_label": "PostgreSQL tenant-aware" if postgres_dsn else "SQL locale tenant-aware",
        }

    backup_dir = str(current_app.config.get("BACKUP_DIR") or "./backup")
    studio_name = str(((json.loads(Path(current_app.config.get("STUDIO_CONFIG", "")).read_text(encoding="utf-8")) if Path(str(current_app.config.get("STUDIO_CONFIG", "") or "")).is_file() else {}).get("studio") or {}).get("nome") or "").strip()
    return {
        "tenant_slug": "",
        "studio_nome": studio_name or "Studio locale",
        "configured_name": studio_name,
        "tenant_choices": [],
        "paths": {
            "AGENDA_DB": str(current_app.config.get("AGENDA_DB") or ""),
            "AUTH_DB": str(current_app.config.get("AUTH_DB") or ""),
            "AUDIT_DB": str(current_app.config.get("AUDIT_DB") or ""),
            "BACKUP_DIR": backup_dir,
            "CLIENTI_DB": str(current_app.config.get("CLIENTI_DB") or ""),
            "FASCICOLI_DB": str(current_app.config.get("FASCICOLI_DB") or ""),
            "FASCICOLI_DOCS": str(current_app.config.get("FASCICOLI_DOCS") or ""),
            "FASCICOLI_ARCH": str(current_app.config.get("FASCICOLI_ARCH") or ""),
            "SCADENZIARIO_DB": str(current_app.config.get("SCADENZIARIO_DB") or ""),
            "PREVENTIVI_DB": str(current_app.config.get("PREVENTIVI_DB") or ""),
            "FATTURAZIONE_DB": str(current_app.config.get("FATTURAZIONE_DB") or ""),
            "STUDIO_DB": str(current_app.config.get("STUDIO_DB") or ""),
            "TEMPLATE_ATTI_DB": str(current_app.config.get("TEMPLATE_ATTI_DB") or ""),
            "GIURISPRUDENZA_DB": str(current_app.config.get("GIURISPRUDENZA_DB") or ""),
            "LEGAL_INTELLIGENCE_DB": str(current_app.config.get("LEGAL_INTELLIGENCE_DB") or ""),
            "TELEMATICO_DB": str(current_app.config.get("TELEMATICO_DB") or ""),
        },
        "sqlite_path": str(Path(backup_dir) / "operational_resilience.db"),
        "postgres_dsn": "",
        "backend_label": "SQL locale tenant-aware",
    }


def _backup_manager(paths: dict[str, str]) -> GestioneBackup:
    return GestioneBackup(
        directory_backup=str(paths.get("BACKUP_DIR") or "./backup"),
        percorsi_dati={
            "agenda": str(paths.get("AGENDA_DB") or ""),
            "clienti": str(paths.get("CLIENTI_DB") or ""),
            "fascicoli": str(paths.get("FASCICOLI_DB") or ""),
            "documenti": str(paths.get("FASCICOLI_DOCS") or ""),
            "archivio": str(paths.get("FASCICOLI_ARCH") or ""),
            "scadenziario": str(paths.get("SCADENZIARIO_DB") or ""),
            "auth": str(paths.get("AUTH_DB") or ""),
            "audit": str(paths.get("AUDIT_DB") or ""),
            "preventivi": str(paths.get("PREVENTIVI_DB") or ""),
            "fatturazione": str(paths.get("FATTURAZIONE_DB") or ""),
            "template_atti": str(paths.get("TEMPLATE_ATTI_DB") or ""),
            "giurisprudenza": str(paths.get("GIURISPRUDENZA_DB") or ""),
            "legal_intelligence": str(paths.get("LEGAL_INTELLIGENCE_DB") or ""),
            "telematico": str(paths.get("TELEMATICO_DB") or ""),
            "studio_db": str(paths.get("STUDIO_DB") or ""),
        },
    )


def _repository(context: dict[str, Any]) -> OperationalResilienceRepository:
    return OperationalResilienceRepository(
        sqlite_path=context["sqlite_path"],
        postgres_dsn=context["postgres_dsn"],
    )


def _backup_execution_disabled() -> bool:
    return backup_operations_disabled(current_app.config)


def _disabled_backup_report(
    *,
    tenant_slug: str = "",
    trigger_source: str = "manual",
    schedule_code: str = "",
) -> dict[str, Any]:
    return {
        "success": True,
        "skipped": True,
        "reason": "backup_operations_disabled",
        "message": "Archivi e copie automatiche sono disattivati dalla politica operativa dello studio.",
        "tenant_slug": str(tenant_slug or ""),
        "trigger_source": str(trigger_source or "manual"),
        "schedule_code": str(schedule_code or ""),
        "runs": [],
    }


def _load_json_report(path_value: str) -> dict[str, Any]:
    path = Path(str(path_value or "").strip())
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


_RESERVED_TECHNICAL_DETAIL = "Dettaglio tecnico disponibile solo nei log operativi riservati."
_RESERVED_REPORT_KEYS = {
    "exception",
    "exc_info",
    "output_excerpt",
    "stack",
    "stacktrace",
    "stack_trace",
    "stderr",
    "stdout",
    "traceback",
}
_EXCEPTION_TEXT_MARKERS = (
    "Traceback (most recent call last):",
    "\n  File ",
    "RuntimeError:",
    "ValueError:",
    "Exception:",
    "sqlite3.",
    "psycopg",
)


def _looks_like_exception_text(value: str) -> bool:
    return any(marker in value for marker in _EXCEPTION_TEXT_MARKERS)


def _public_operational_payload(value: Any, key: str = "") -> Any:
    normalized_key = str(key or "").strip().lower()
    if isinstance(value, dict):
        return {
            str(item_key): _public_operational_payload(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_public_operational_payload(item) for item in value]
    if isinstance(value, str):
        if normalized_key in _RESERVED_REPORT_KEYS or _looks_like_exception_text(value):
            return _RESERVED_TECHNICAL_DETAIL
        return value
    return value


def build_operational_crash_surface(selected_slug: str = "") -> dict[str, Any]:
    context = _resolve_context(selected_slug)
    repository = _repository(context)
    latest_run = repository.latest_crash_run(tenant_slug=context["tenant_slug"])
    latest_backup = repository.latest_backup_run(tenant_slug=context["tenant_slug"])
    latest_report = _load_json_report(str((latest_run or {}).get("report_path") or ""))
    latest_backup_payload = dict((latest_backup or {}).get("payload_json") or {})
    latest_backup_report = _load_json_report(str(latest_backup_payload.get("report_path") or ""))
    return {
        "context": context,
        "schedule_plan": {
            "crash_tests": list(OPERATIONAL_CRASH_SCHEDULES),
            "backup": dict(OPERATIONAL_BACKUP_SCHEDULE),
        },
        "latest_run": _public_operational_payload(latest_run or {}),
        "latest_report": _public_operational_payload(latest_report),
        "repair_tickets": _public_operational_payload(
            repository.list_repair_tickets(tenant_slug=context["tenant_slug"], limit=12)
        ),
        "backup_runs": _public_operational_payload(
            repository.list_backup_runs(tenant_slug=context["tenant_slug"], limit=12)
        ),
        "latest_backup_report": _public_operational_payload(latest_backup_report),
        "latest_backup_payload": _public_operational_payload(latest_backup_payload),
        "system_health": _public_operational_payload(build_system_health_api_payload()),
        "backend_label": context["backend_label"],
    }


def execute_operational_crash_surface(
    *,
    selected_slug: str = "",
    trigger_source: str = "manual",
    schedule_code: str = "",
    auto_repair: bool = True,
    max_attempts: int = 3,
) -> dict[str, Any]:
    context = _resolve_context(selected_slug)
    repository = _repository(context)
    backup_manager = _backup_manager(context["paths"])
    local_mirror_dir = str(current_app.config.get("BACKUP_LOCAL_MIRROR_DIR") or "")
    secondary_mirror_dir = str(current_app.config.get("BACKUP_SECONDARY_MIRROR_DIR") or "")
    secondary_label = str(current_app.config.get("BACKUP_SECONDARY_LABEL") or "")

    def _backup_executor(reason: str) -> dict[str, Any]:
        if _backup_execution_disabled():
            return _disabled_backup_report(
                tenant_slug=context["tenant_slug"],
                trigger_source=trigger_source,
                schedule_code=f"{schedule_code or 'manual'}:{reason}",
            )
        return run_operational_backup_plan(
            tenant_slug=context["tenant_slug"],
            backup_manager=backup_manager,
            backup_dir=context["paths"]["BACKUP_DIR"],
            repository=repository,
            trigger_source=trigger_source,
            schedule_code=f"{schedule_code or 'manual'}:{reason}",
            local_mirror_dir=local_mirror_dir,
            secondary_mirror_dir=secondary_mirror_dir,
            secondary_label=secondary_label,
        )

    report = run_operational_crash_test(
        tenant_slug=context["tenant_slug"],
        report_dir=str(Path(context["paths"]["BACKUP_DIR"]) / "operational_crash_tests"),
        repair_dir=str(Path(context["paths"]["BACKUP_DIR"]) / "repair_queue"),
        repository=repository,
        health_snapshot_factory=build_system_health_api_payload,
        backup_executor=_backup_executor,
        trigger_source=trigger_source,
        schedule_code=schedule_code,
        auto_repair=bool(auto_repair),
        max_attempts=max_attempts,
        cwd=str(Path(current_app.root_path).parent),
        runtime_context={
            "base_config": dict(current_app.config),
            "tenant_slug": context["tenant_slug"],
            "backend_label": context["backend_label"],
        },
    )
    return report


def execute_operational_backup_surface(
    *,
    selected_slug: str = "",
    trigger_source: str = "manual",
    schedule_code: str = "",
) -> dict[str, Any]:
    if _backup_execution_disabled():
        return _disabled_backup_report(
            tenant_slug=selected_slug,
            trigger_source=trigger_source,
            schedule_code=schedule_code,
        )
    context = _resolve_context(selected_slug)
    repository = _repository(context)
    backup_manager = _backup_manager(context["paths"])
    return run_operational_backup_plan(
        tenant_slug=context["tenant_slug"],
        backup_manager=backup_manager,
        backup_dir=context["paths"]["BACKUP_DIR"],
        repository=repository,
        trigger_source=trigger_source,
        schedule_code=schedule_code,
        local_mirror_dir=str(current_app.config.get("BACKUP_LOCAL_MIRROR_DIR") or ""),
        secondary_mirror_dir=str(current_app.config.get("BACKUP_SECONDARY_MIRROR_DIR") or ""),
        secondary_label=str(current_app.config.get("BACKUP_SECONDARY_LABEL") or ""),
    )
