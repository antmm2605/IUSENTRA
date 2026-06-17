"""Audit bloccante della struttura dati tenant IUSENTRA.

Controlla per ogni studio:
- JSON runtime previsti;
- `studio.db` SQLite con schema core e mirror `moduli_*`;
- `notifications.db`;
- presenza degli schemi PostgreSQL equivalenti per mirror JSON e notifiche.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.database import GestioneDatabase
from pct.storage_migration import _build_json_to_sqlite_sources
from pct.tenant import GestioneTenant, TENANT_FILE_SEED_PATHS


REQUIRED_STUDIO_TABLES = {
    "clienti",
    "fascicoli",
    "appuntamenti",
    "scadenze",
    "utenti",
    "audit_log",
    "time_tracking_timers",
    "notifiche_log",
    "backup_records",
    "moduli_dati",
    "moduli_json_records",
}

REQUIRED_NOTIFICATION_TABLES = {
    "notifications",
    "push_subscriptions",
    "notification_preferences",
    "notification_deliveries",
}

VOLATILE_MIRROR_MODULES = {
    "audit",
}

POSTGRES_SCHEMA_CHECKS = {
    "pct/sql/20260503_moduli_json_records_postgres.sql": {
        "moduli_dati",
        "moduli_json_records",
    },
    "pct/sql/20260512_notifications_postgres.sql": REQUIRED_NOTIFICATION_TABLES,
}


def _repo_root() -> Path:
    return REPO_ROOT


def _registry_default() -> str:
    data_root = os.environ.get("PCT_DATA_ROOT")
    return (
        os.environ.get("TENANTS_REGISTRY")
        or os.environ.get("IUSENTRA_TENANTS_REGISTRY")
        or os.environ.get("PCT_TENANTS_REGISTRY")
        or (str(Path(data_root) / "tenants.json") if data_root else "")
        or str(_repo_root() / "data" / "tenants.json")
    )


def _tenant_paths_for_base(base: Path) -> dict[str, str]:
    raw = {
        "AGENDA_DB": base / "agenda" / "appuntamenti.json",
        "CALENDAR_SYNC_DB": base / "agenda" / "calendar_sync.json",
        "CALENDAR_SYNC_ENGINE_DB": base / "agenda" / "calendar_sync_engine.json",
        "CALENDAR_CONFLICTS_DB": base / "agenda" / "calendar_conflicts.json",
        "CALENDAR_TOKEN_DB": base / "agenda" / "cal_token.json",
        "CLIENTI_DB": base / "clienti" / "anagrafica.json",
        "CONDIVISIONI_DB": base / "clienti" / "condivisioni.json",
        "NOTE_FALDONE_DB": base / "clienti" / "note_faldone.json",
        "FASCICOLI_DB": base / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": base / "fascicoli" / "documenti",
        "FASCICOLI_ARCH": base / "fascicoli" / "archivio",
        "DOCUMENTI_AI_DIR": base / "fascicoli" / "documenti_ai",
        "DOCUMENTI_AI_DB": base / "fascicoli" / "documenti_ai" / "documenti_ai.json",
        "EDITOR_AI_DB": base / "fascicoli" / "editor_ai" / "editor_ai.json",
        "FASCICOLI_IMPORTAZIONI_DIR": base / "fascicoli" / "importazioni",
        "PEC_CANCELLERIA_STATE_DB": base / "fascicoli" / "pec_cancelleria_state.json",
        "PRACTICE_ENGINE_DB": base / "fascicoli" / "practice_engine" / "practice_engine.json",
        "MESSAGGI_DB": base / "messaggi" / "storico.json",
        "BACKUP_DIR": base / "backup",
        "AUTH_DB": base / "auth" / "utenti.json",
        "AUDIT_DB": base / "auth" / "audit.json",
        "SCADENZIARIO_DB": base / "scadenziario" / "scadenze.json",
        "TIMESHEET_DB": base / "timesheet" / "entries.json",
        "TIME_TRACKING_DB": base / "timesheet" / "time_tracking.json",
        "SEARCH_INDEX": base / "search" / "index.db",
        "PRIVACY_DB": base / "privacy" / "registro.json",
        "PORTALE_DB": base / "portale" / "portali.json",
        "FATTURAZIONE_DB": base / "fatturazione" / "parcelle.json",
        "NOTIFICHE_LOG": base / "notifiche" / "log.json",
        "NOTIFICATIONS_DB": base / "notifications" / "notifications.db",
        "EMAIL_CASELLA_DB": base / "email" / "casella.json",
        "EMAIL_ORDINARIA_DB": base / "email" / "ordinaria.json",
        "PAGAMENTI_DIR": base / "pagamenti",
        "TEMPLATE_ATTI_DB": base / "template_atti" / "templates.json",
        "TEMPLATE_REPOSITORY_DB": base / "template_atti" / "template_repository.json",
        "TEMPLATE_ATTI_PREFS_DB": base / "template_atti" / "editor_layout.json",
        "WIZARD_PRO_DB": base / "wizard_pro" / "sessioni.json",
        "LEGAL_INTELLIGENCE_DB": base / "intelligence" / "motori.json",
        "LEGAL_UPDATES_JSON": base / "intelligence" / "legal_updates_repository.json",
        "NORMATIVE_TABLES_DB": base / "intelligence" / "tabelle_normative.json",
        "GIURISPRUDENZA_DB": base / "intelligence" / "giurisprudenza.json",
        "GIURISPRUDENZA_REPOSITORY_DB": base / "intelligence" / "giurisprudenza_repository.json",
        "GIURISPRUDENZA_SOURCES_REPOSITORY_DB": base / "intelligence" / "giurisprudenza_sources_repository.json",
        "GIURISPRUDENZA_SYNC_REGISTRY_DB": base / "intelligence" / "giurisprudenza_sync_registry.json",
        "GIURISPRUDENZA_TAXONOMY_REPOSITORY_DB": base / "intelligence" / "giurisprudenza_taxonomy_repository.json",
        "GIURISPRUDENZA_USAGE_POLICY_DB": base / "intelligence" / "giurisprudenza_usage_policy.json",
        "LEGAL_ENGINE_SOURCE_EDGES_DB": base / "intelligence" / "legal_engine_source_edges.json",
        "LEGAL_ENGINES_REPOSITORY_DB": base / "intelligence" / "legal_engines_repository.json",
        "LEGAL_INTELLIGENCE_REPOSITORY_DB": base / "intelligence" / "legal_intelligence_repository.json",
        "LEGAL_KEYWORD_TO_ENGINE_DB": base / "intelligence" / "legal_keyword_to_engine.json",
        "LEGAL_KEYWORD_TO_SOURCE_DB": base / "intelligence" / "legal_keyword_to_source.json",
        "LEGAL_OPERATIONAL_REPOSITORY_DB": base / "intelligence" / "legal_operational_repository.json",
        "LEGAL_SOURCES_REPOSITORY_DB": base / "intelligence" / "legal_sources_repository.json",
        "LEX_DATASET_DIR": base / "intelligence" / "lex_dataset",
        "TELEMATICO_ACTIONS_REPOSITORY_DB": base / "intelligence" / "telematico_actions_repository.json",
        "TELEMATICO_CAPABILITIES_REPOSITORY_DB": base / "intelligence" / "telematico_capabilities_repository.json",
        "TELEMATICO_CATALOG_SNAPSHOT_DB": base / "intelligence" / "telematico_catalog_snapshot.json",
        "TELEMATICO_CATALOG_SOURCES_REPOSITORY_DB": base / "intelligence" / "telematico_catalog_sources_repository.json",
        "TELEMATICO_METHODS_REPOSITORY_DB": base / "intelligence" / "telematico_methods_repository.json",
        "TELEMATICO_MONITORING_REPOSITORY_DB": base / "intelligence" / "telematico_monitoring_repository.json",
        "TELEMATICO_REPOSITORY_JSON": base / "intelligence" / "telematico_repository.json",
        "TELEMATICO_RULES_REPOSITORY_DB": base / "intelligence" / "telematico_rules_repository.json",
        "TELEMATICO_SOURCES_REPOSITORY_DB": base / "intelligence" / "telematico_sources_repository.json",
        "TELEMATICO_WIZARD_SECTIONS_REPOSITORY_DB": base / "intelligence" / "telematico_wizard_sections_repository.json",
        "TELEMATICO_WSDL_MODULES_REPOSITORY_DB": base / "intelligence" / "telematico_wsdl_modules_repository.json",
        "TELEMATICO_XSD_CHANNELS_REPOSITORY_DB": base / "intelligence" / "telematico_xsd_channels_repository.json",
        "LEGAL_SKILLS_PROFILE_DB": base / "intelligence" / "legal_skills" / "profile.json",
        "LEGAL_SKILLS_RUNS_DB": base / "intelligence" / "legal_skills" / "runs.json",
        "LEGAL_SKILLS_SCHEDULED_DB": base / "intelligence" / "legal_skills" / "scheduled.json",
        "WORKFLOW_AGENTS_RUNS_DB": base / "intelligence" / "workflow_agents" / "runs.json",
        "WORKFLOW_AGENTS_METRICS_DB": base / "intelligence" / "workflow_agents" / "metrics.json",
        "WORKFLOW_AGENTS_ACTIONS_DB": base / "intelligence" / "workflow_agents" / "actions.json",
        "WORKSPACE_INTELLIGENCE_DB": base / "intelligence" / "workspace_intelligence.json",
        "VALIDATION_RUNS_DB": base / "intelligence" / "validation_runs.json",
        "REDACTION_ASSISTANT_DB": base / "intelligence" / "assistente_redazionale.json",
        "CONFIG_STUDIO_DB": base / "config" / "studio.json",
        "STORAGE_CONFIG": base / "config" / "storage.json",
        "STUDIO_LOCAL_PACK_DB": base / "config" / "studio_local_pack.json",
        "STUDIO_CONFIG": base / "config" / "studio.json",
        "STUDIO_DB": base / "studio.db",
        "PREVENTIVI_DB": base / "preventivi" / "preventivi.json",
        "PREVENTIVI_REPOSITORY_DB": base / "preventivi" / "preventivi_repository.json",
        "PREVENTIVI_WORKFLOW_STATES_DB": base / "preventivi" / "preventivi_workflow_states.json",
        "PREVENTIVI_FIELD_MAP_DB": base / "preventivi" / "preventivi_field_map.json",
        "PREVENTIVI_RULES_DB": base / "preventivi" / "preventivi_rules.json",
        "TERMINI_PROCESSUALI_DB": base / "scadenziario" / "termini_processuali.json",
        "SOGGETTI_DB": base / "soggetti" / "anagrafica.json",
        "SOGGETTI_PARTI_DB": base / "soggetti" / "parti.json",
    }
    return {key: str(value) for key, value in raw.items()}


def _sqlite_tables(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with sqlite3.connect(str(path)) as conn:
        return {
            str(row[0])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }


def _json_entries_count(raw: Any) -> int:
    return len(GestioneDatabase._json_record_entries(raw))


def _rel_to_base(path: Path, base: Path) -> str:
    hidden_json: list[dict[str, Any]] = []

    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _untracked_json_role(relative: str) -> str:
    parts = [part.lower() for part in Path(relative).parts]
    name = Path(relative).name.lower()
    if parts and parts[0] == "backup":
        return "archivio_backup"
    if "demo_calendar" in parts or "demo" in parts:
        return "cache_demo"
    if "downloads" in parts or "models" in parts:
        return "cache_rigenerabile"
    if name.startswith(("pre_migration_", "storage_migration_", "operational_backup_")):
        return "archivio_backup"
    if "archive" in parts or "archivio" in parts:
        return "archivio_documentale"
    return "operativo_non_censito"


def _check_postgres_schema(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for relative, required_names in POSTGRES_SCHEMA_CHECKS.items():
        path = repo_root / relative
        if not path.exists():
            errors.append(f"Schema PostgreSQL mancante: {relative}")
            continue
        text = path.read_text(encoding="utf-8").lower()
        for table_name in required_names:
            if table_name.lower() not in text:
                errors.append(f"Schema PostgreSQL {relative} senza tabella {table_name}.")
    return errors


def _audit_studio(tm: GestioneTenant, slug: str, *, repair: bool = False) -> dict[str, Any]:
    if repair:
        tm.ensure_runtime_baseline(slug, force=True)
    studio = tm.get(slug)
    effective_runtime_kind = (
        str(getattr(getattr(studio, "database", None), "effective_runtime_kind", "") or "json")
        .strip()
        .lower()
    )
    sql_authoritative = effective_runtime_kind in {"sqlite", "postgresql"}
    base = tm._data_dir(slug)
    paths = _tenant_paths_for_base(base)
    sqlite_path = Path(paths["STUDIO_DB"])
    notifications_path = Path(paths["NOTIFICATIONS_DB"])
    errors: list[str] = []
    warnings: list[str] = []
    json_results: dict[str, Any] = {}

    studio_tables = _sqlite_tables(sqlite_path)
    missing_tables = sorted(REQUIRED_STUDIO_TABLES - studio_tables)
    if not sqlite_path.exists():
        errors.append(f"{slug}: studio.db mancante.")
    elif missing_tables:
        errors.append(f"{slug}: studio.db senza tabelle {', '.join(missing_tables)}.")

    notification_tables = _sqlite_tables(notifications_path)
    missing_notification_tables = sorted(REQUIRED_NOTIFICATION_TABLES - notification_tables)
    if not notifications_path.exists():
        errors.append(f"{slug}: notifications.db mancante.")
    elif missing_notification_tables:
        errors.append(
            f"{slug}: notifications.db senza tabelle {', '.join(missing_notification_tables)}."
        )

    mirror_sources = {
        str(Path(path).resolve()): module
        for module, path in _build_json_to_sqlite_sources(paths).items()
        if str(path or "").strip() and Path(str(path)).suffix.lower() == ".json"
    }

    conn: sqlite3.Connection | None = None
    if sqlite_path.exists() and {"moduli_dati", "moduli_json_records"}.issubset(studio_tables):
        conn = sqlite3.connect(str(sqlite_path))
    mirror_resynced = False

    def _repair_json_mirror() -> None:
        nonlocal conn, mirror_resynced
        if mirror_resynced or not repair:
            return
        if conn is not None:
            conn.close()
            conn = None
        paths_for_mirror = dict(paths)
        paths_for_mirror["STUDIO_CONFIG"] = paths.get("CONFIG_STUDIO_DB", "")
        GestioneDatabase(
            _build_json_to_sqlite_sources(paths_for_mirror)
        ).sincronizza_moduli_json_sqlite(
            paths["STUDIO_DB"],
            include_structured=True,
        )
        conn = sqlite3.connect(str(sqlite_path))
        mirror_resynced = True

    def _metadata_and_count(module: str) -> tuple[Any, int]:
        if conn is None:
            return None, 0
        metadata_row = conn.execute(
            "SELECT percorso FROM moduli_dati WHERE nome = ?",
            (module,),
        ).fetchone()
        count_row = conn.execute(
            "SELECT COUNT(*) FROM moduli_json_records WHERE modulo = ?",
            (module,),
        ).fetchone()
        return metadata_row, int(count_row[0] if count_row else 0)

    try:
        for relative in TENANT_FILE_SEED_PATHS:
            if not relative.endswith(".json"):
                continue
            path = base / relative
            result: dict[str, Any] = {
                "path": str(path),
                "exists": path.exists(),
                "valid_json": False,
                "module": "",
                "entries": 0,
                "sqlite_metadata": False,
                "sqlite_records": 0,
                "role": "mirror_compatibilita" if sql_authoritative else "sorgente_json",
                "authoritative": not sql_authoritative,
            }
            if not path.exists():
                message = f"{slug}: JSON mirror mancante {relative}."
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(f"{slug}: JSON mancante {relative}.")
                json_results[relative] = result
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                result["valid_json"] = True
                result["entries"] = _json_entries_count(raw)
            except json.JSONDecodeError as exc:
                message = f"{slug}: JSON mirror non valido {relative}: {exc}"
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(f"{slug}: JSON non valido {relative}: {exc}")
                json_results[relative] = result
                continue

            module = mirror_sources.get(str(path.resolve()), "")
            result["module"] = module
            if not module:
                message = f"{slug}: JSON mirror senza modulo SQL {relative}."
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(f"{slug}: JSON senza modulo SQL {relative}.")
                json_results[relative] = result
                continue
            if conn is None:
                message = f"{slug}: impossibile verificare mirror SQL per {relative}."
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(message)
                json_results[relative] = result
                continue
            volatile_mirror = bool(sql_authoritative and module in VOLATILE_MIRROR_MODULES)
            result["volatile_mirror"] = volatile_mirror
            metadata, actual_count = _metadata_and_count(module)
            stored_path = Path(str(metadata[0] or "")).resolve() if metadata else None
            count_mismatch = actual_count != int(result["entries"])
            mirror_mismatch = (
                metadata is None
                or stored_path != path.resolve()
                or (count_mismatch and not volatile_mirror)
            )
            if mirror_mismatch and repair:
                _repair_json_mirror()
                metadata, actual_count = _metadata_and_count(module)
                stored_path = Path(str(metadata[0] or "")).resolve() if metadata else None
                count_mismatch = actual_count != int(result["entries"])
            result["sqlite_metadata"] = metadata is not None
            if metadata is None:
                message = f"{slug}: moduli_dati senza record mirror per {module} ({relative})."
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(f"{slug}: moduli_dati senza record per {module} ({relative}).")
            else:
                if stored_path != path.resolve():
                    message = (
                        f"{slug}: percorso mirror SQL incoerente per {module}: "
                        f"{stored_path} != {path}."
                    )
                    if sql_authoritative:
                        warnings.append(message)
                    else:
                        errors.append(
                            f"{slug}: percorso SQL incoerente per {module}: {stored_path} != {path}."
                        )
            result["sqlite_records"] = actual_count
            if count_mismatch and not volatile_mirror:
                message = (
                    f"{slug}: mirror moduli_json_records non allineato per {module} "
                    f"({actual_count}/{result['entries']})."
                )
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(message)
            json_results[relative] = result

        for absolute, module in sorted(mirror_sources.items(), key=lambda item: item[1]):
            path = Path(absolute)
            if not path.exists() or not path.is_file():
                continue
            relative = _rel_to_base(path, base)
            if relative in json_results:
                continue
            result = {
                "path": str(path),
                "exists": True,
                "valid_json": False,
                "module": module,
                "entries": 0,
                "sqlite_metadata": False,
                "sqlite_records": 0,
                "role": "mirror_compatibilita" if sql_authoritative else "sorgente_json",
                "authoritative": not sql_authoritative,
            }
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                result["valid_json"] = True
                result["entries"] = _json_entries_count(raw)
            except json.JSONDecodeError as exc:
                message = f"{slug}: JSON mirror non valido {relative}: {exc}"
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(f"{slug}: JSON non valido {relative}: {exc}")
                json_results[relative] = result
                continue
            if conn is None:
                message = f"{slug}: impossibile verificare mirror SQL per {relative}."
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(message)
                json_results[relative] = result
                continue
            volatile_mirror = bool(sql_authoritative and module in VOLATILE_MIRROR_MODULES)
            result["volatile_mirror"] = volatile_mirror
            metadata, actual_count = _metadata_and_count(module)
            stored_path = Path(str(metadata[0] or "")).resolve() if metadata else None
            count_mismatch = actual_count != int(result["entries"])
            mirror_mismatch = (
                metadata is None
                or stored_path != path.resolve()
                or (count_mismatch and not volatile_mirror)
            )
            if mirror_mismatch and repair:
                _repair_json_mirror()
                metadata, actual_count = _metadata_and_count(module)
                stored_path = Path(str(metadata[0] or "")).resolve() if metadata else None
                count_mismatch = actual_count != int(result["entries"])
            result["sqlite_metadata"] = metadata is not None
            result["sqlite_records"] = actual_count
            if metadata is None:
                message = f"{slug}: moduli_dati senza record mirror per {module} ({relative})."
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(f"{slug}: moduli_dati senza record per {module} ({relative}).")
            elif stored_path != path.resolve():
                message = (
                    f"{slug}: percorso mirror SQL incoerente per {module}: "
                    f"{stored_path} != {path}."
                )
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(
                        f"{slug}: percorso SQL incoerente per {module}: {stored_path} != {path}."
                    )
            if count_mismatch and not volatile_mirror:
                message = (
                    f"{slug}: mirror moduli_json_records non allineato per {module} "
                    f"({actual_count}/{result['entries']})."
                )
                if sql_authoritative:
                    warnings.append(message)
                else:
                    errors.append(message)
            json_results[relative] = result

        hidden_json = []
        for path in sorted(base.rglob("*.json")):
            relative = _rel_to_base(path, base)
            if relative in json_results:
                continue
            role = _untracked_json_role(relative)
            item = {
                "path": str(path),
                "relative": relative,
                "role": role,
                "tracked": False,
                "entries": 0,
            }
            try:
                item["entries"] = _json_entries_count(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                item["entries"] = 0
            hidden_json.append(item)
            if role == "operativo_non_censito":
                errors.append(
                    f"{slug}: JSON operativo non censito in studio.db: {relative}. "
                    "Aggiungere il modulo al contratto dati e popolare il mirror SQL."
                )
    finally:
        if conn is not None:
            conn.close()

    return {
        "ok": not errors,
        "slug": slug,
        "data_dir": str(base),
        "source_of_truth": effective_runtime_kind,
        "json_authoritative": not sql_authoritative,
        "studio_db": str(sqlite_path),
        "notifications_db": str(notifications_path),
        "json": json_results,
        "hidden_json": hidden_json,
        "hidden_json_summary": {
            "total": len(hidden_json),
            "operational_untracked": sum(1 for item in hidden_json if item.get("role") == "operativo_non_censito"),
            "archive_or_cache": sum(1 for item in hidden_json if item.get("role") != "operativo_non_censito"),
        },
        "warnings": warnings,
        "errors": errors,
    }


def audit_tenant_data_structure(
    *,
    registry: str | Path = "",
    tenant: str = "",
    repair: bool = False,
) -> dict[str, Any]:
    registry_path = Path(str(registry or _registry_default()))
    tm = GestioneTenant(str(registry_path))
    if not registry_path.exists():
        return {
            "ok": False,
            "registry": str(registry_path),
            "errors": [f"Registry tenant mancante: {registry_path}"],
            "studios": {},
            "postgres_schema": {},
        }

    requested = str(tenant or "").strip().lower()
    studios = [
        studio for studio in tm.lista()
        if not requested or str(studio.slug or "").strip().lower() == requested
    ]
    report: dict[str, Any] = {
        "ok": True,
        "registry": str(registry_path),
        "studios": {},
        "postgres_schema": {
            "ok": True,
            "errors": [],
        },
        "warnings": [],
        "errors": [],
    }
    if requested and not studios:
        report["ok"] = False
        report["errors"].append(f"Studio non trovato: {requested}")
        return report

    pg_errors = _check_postgres_schema(_repo_root())
    report["postgres_schema"]["errors"] = pg_errors
    report["postgres_schema"]["ok"] = not pg_errors
    report["errors"].extend(pg_errors)

    for studio in studios:
        slug = str(studio.slug or "").strip().lower()
        if not slug:
            continue
        studio_report = _audit_studio(tm, slug, repair=repair)
        report["studios"][slug] = studio_report
        report["errors"].extend(studio_report["errors"])
        report["warnings"].extend(studio_report.get("warnings", []))

    report["ok"] = not report["errors"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit struttura dati tenant IUSENTRA")
    parser.add_argument("--registry", default=_registry_default(), help="Percorso tenants.json")
    parser.add_argument("--tenant", default="", help="Slug studio da verificare")
    parser.add_argument("--repair", action="store_true", help="Riallinea prima di verificare")
    parser.add_argument("--json", action="store_true", help="Stampa report JSON completo")
    args = parser.parse_args(argv)

    report = audit_tenant_data_structure(
        registry=args.registry,
        tenant=args.tenant,
        repair=bool(args.repair),
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["ok"]:
        print("Audit struttura dati tenant completato: nessuna mancanza rilevata.")
    else:
        print("Audit struttura dati tenant fallito:")
        for error in report.get("errors", []):
            print(f"- {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
