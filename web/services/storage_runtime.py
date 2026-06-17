"""Tenant-aware storage runtime helpers."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context

from pct.core_storage_backend import (
    build_core_storage_backend,
    ensure_core_storage_backend_contract,
    is_postgres_core_active,
)
from pct.storage import StudioDB
from pct.tenant import DbMode, normalize_db_mode

_ROOT_LEVEL_JSON_ANCHORS = {
    "agenda",
    "auth",
    "calendar",
    "clienti",
    "config",
    "email",
    "fascicoli",
    "fatturazione",
    "intelligence",
    "messaggi",
    "penale",
    "portale",
    "preventivi",
    "privacy",
    "scadenziario",
    "search",
    "soggetti",
    "telematico",
    "template_atti",
}


@dataclass(frozen=True)
class StorageRuntimeProfile:
    selected_mode: str
    effective_mode: str
    uses_sqlite: bool
    studio_db_path: str
    data_anchor_path: str
    tenant_slug: str = ""
    source: str = "app"
    external_sql_configured: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_default_storage_mode() -> str:
    if has_app_context():
        configured = str(current_app.config.get("STORAGE_MODE_DEFAULT") or "").strip()
        if configured:
            return normalize_db_mode(configured)
        if current_app.config.get("SQLITE_MODE"):
            return DbMode.SQLITE
        return DbMode.JSON

    env_mode = str(os.getenv("PCT_STORAGE_MODE", "") or "").strip()
    if env_mode:
        return normalize_db_mode(env_mode)

    sqlite_flag = str(os.getenv("PCT_SQLITE_MODE", "") or "").strip().lower()
    if sqlite_flag in {"1", "true", "yes"}:
        return DbMode.SQLITE
    if sqlite_flag in {"0", "false", "no"}:
        return DbMode.JSON
    return DbMode.SQLITE


def _derive_studio_db_path(anchor_path: str) -> str:
    anchor = Path(anchor_path).resolve()
    if anchor.suffix.lower() != ".json":
        root = anchor.parent
    elif anchor.parent.name.lower() in _ROOT_LEVEL_JSON_ANCHORS:
        root = anchor.parent.parent
    else:
        root = anchor.parent
    return str((root / "studio.db").resolve())


def _json_anchor_has_legacy_data(anchor_path: Path) -> bool:
    if anchor_path.suffix.lower() != ".json" or not anchor_path.exists():
        return False
    try:
        payload = json.loads(anchor_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if isinstance(payload, list):
        return len(payload) > 0
    if isinstance(payload, dict):
        return len(payload) > 0
    return bool(payload)


def _anchor_seed_tables(anchor_path: Path) -> tuple[str, ...]:
    stem = anchor_path.stem.lower()
    mapping = {
        "clienti": ("clienti",),
        "fascicoli": ("fascicoli",),
        "agenda": ("appuntamenti",),
        "scadenze": ("scadenze",),
        "scadenziario": ("scadenze",),
        "utenti": ("utenti",),
        "auth": ("utenti",),
    }
    return mapping.get(stem, ("clienti", "fascicoli", "appuntamenti", "scadenze"))


def _sqlite_runtime_is_unseeded(studio_db_path: Path, anchor_path: Path) -> bool:
    if not studio_db_path.exists():
        return True
    try:
        conn = sqlite3.connect(str(studio_db_path))
        try:
            tables = _anchor_seed_tables(anchor_path)
            total = 0
            for table in tables:
                try:
                    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                except sqlite3.Error:
                    continue
                total += int((row or [0])[0] or 0)
            return total == 0
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def _resolve_tenant_mode_profile(selected_mode: str, tenant: Any, studio_db_path: str) -> tuple[str, bool, str]:
    database = getattr(tenant, "database", None)
    if selected_mode == DbMode.SQLITE:
        return DbMode.SQLITE, True, "tenant-sqlite"
    if selected_mode == DbMode.POSTGRESQL and database is not None and is_postgres_core_active(database):
        return DbMode.POSTGRESQL, False, "tenant-postgresql"
    if selected_mode == DbMode.POSTGRESQL:
        return DbMode.SQLITE, True, "tenant-postgresql-sqlite-staging"
    if selected_mode == DbMode.MYSQL:
        return DbMode.SQLITE, True, "tenant-mysql-sqlite-staging"
    return DbMode.JSON, False, "tenant-json"


def resolve_storage_runtime(*, anchor_path: str, tenant: Any = None) -> StorageRuntimeProfile:
    selected_mode = resolve_default_storage_mode()
    source = "app"
    tenant_slug = ""
    studio_db_path = _derive_studio_db_path(anchor_path)
    effective_mode = DbMode.JSON
    uses_sqlite = False

    if tenant is not None:
        tenant_slug = str(getattr(tenant, "slug", "") or "")
        try:
            selected_mode = normalize_db_mode(getattr(tenant, "database").mode)
        except Exception:
            selected_mode = DbMode.SQLITE
        effective_mode, uses_sqlite, source = _resolve_tenant_mode_profile(
            selected_mode,
            tenant,
            studio_db_path,
        )
    elif has_app_context() and current_app.config.get("STORAGE_MODE_DEFAULT"):
        source = "app-default"
        if selected_mode == DbMode.SQLITE:
            effective_mode = DbMode.SQLITE
            uses_sqlite = True
    elif has_app_context() and current_app.config.get("SQLITE_MODE"):
        selected_mode = DbMode.SQLITE
        effective_mode = DbMode.SQLITE
        uses_sqlite = True
        source = "legacy-global"
    else:
        source = "default-operational"
        if selected_mode == DbMode.SQLITE:
            effective_mode = DbMode.SQLITE
            uses_sqlite = True

    external_sql_configured = selected_mode in (DbMode.POSTGRESQL, DbMode.MYSQL)

    return StorageRuntimeProfile(
        selected_mode=selected_mode,
        effective_mode=effective_mode,
        uses_sqlite=uses_sqlite,
        studio_db_path=studio_db_path,
        data_anchor_path=str(Path(anchor_path).resolve()),
        tenant_slug=tenant_slug,
        source=source,
        external_sql_configured=external_sql_configured,
    )


def get_request_storage_runtime(anchor_path: str) -> StorageRuntimeProfile:
    if not has_request_context():
        return resolve_storage_runtime(anchor_path=anchor_path, tenant=None)

    tenant = getattr(g, "tenant", None)
    tenant_slug = str(getattr(tenant, "slug", "") or "")
    resolved_anchor = str(Path(anchor_path).resolve())
    cached = getattr(g, "_storage_runtime_profile", None)
    if (
        cached
        and cached.data_anchor_path == resolved_anchor
        and str(getattr(cached, "tenant_slug", "") or "") == tenant_slug
    ):
        return cached

    profile = resolve_storage_runtime(anchor_path=anchor_path, tenant=tenant)
    g._storage_runtime_profile = profile
    return profile


def _postgres_runtime_backend(anchor_path: str, profile: StorageRuntimeProfile):
    tenant = getattr(g, "tenant", None) if has_request_context() else None
    database = getattr(tenant, "database", None)
    backend = None
    if database is not None:
        backend = build_core_storage_backend(database, studio_db_path=profile.studio_db_path)
    if backend is None:
        message = (
            "Backend PostgreSQL attivo per i domini core ma non disponibile. "
            "Il sistema blocca l'operazione per evitare fallback invisibili a JSON."
        )
        if has_app_context():
            current_app.logger.error(
                "%s tenant=%s anchor=%s",
                message,
                profile.tenant_slug or "-",
                anchor_path,
            )
        raise RuntimeError(message)
    return backend


def _runtime_paths_for_studio_root(root: Path) -> dict[str, str]:
    return {
        "AGENDA_DB": str(root / "agenda" / "appuntamenti.json"),
        "CALENDAR_SYNC_DB": str(root / "agenda" / "calendar_sync.json"),
        "CALENDAR_SYNC_ENGINE_DB": str(root / "agenda" / "calendar_sync_engine.json"),
        "CALENDAR_CONFLICTS_DB": str(root / "agenda" / "calendar_conflicts.json"),
        "CALENDAR_TOKEN_DB": str(root / "agenda" / "cal_token.json"),
        "CLIENTI_DB": str(root / "clienti" / "anagrafica.json"),
        "CONDIVISIONI_DB": str(root / "clienti" / "condivisioni.json"),
        "NOTE_FALDONE_DB": str(root / "clienti" / "note_faldone.json"),
        "FASCICOLI_DB": str(root / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(root / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(root / "fascicoli" / "archivio"),
        "DOCUMENTI_AI_DIR": str(root / "fascicoli" / "documenti_ai"),
        "DOCUMENTI_AI_DB": str(root / "fascicoli" / "documenti_ai" / "documenti_ai.json"),
        "EDITOR_AI_DB": str(root / "fascicoli" / "editor_ai" / "editor_ai.json"),
        "FASCICOLI_IMPORTAZIONI_DIR": str(root / "fascicoli" / "importazioni"),
        "PEC_CANCELLERIA_STATE_DB": str(root / "fascicoli" / "pec_cancelleria_state.json"),
        "PRACTICE_ENGINE_DB": str(root / "fascicoli" / "practice_engine" / "practice_engine.json"),
        "MESSAGGI_DB": str(root / "messaggi" / "storico.json"),
        "BACKUP_DIR": str(root / "backup"),
        "AUTH_DB": str(root / "auth" / "utenti.json"),
        "AUDIT_DB": str(root / "auth" / "audit.json"),
        "SCADENZIARIO_DB": str(root / "scadenziario" / "scadenze.json"),
        "TIMESHEET_DB": str(root / "timesheet" / "entries.json"),
        "TIME_TRACKING_DB": str(root / "timesheet" / "time_tracking.json"),
        "SEARCH_INDEX": str(root / "search" / "index.db"),
        "PRIVACY_DB": str(root / "privacy" / "registro.json"),
        "PORTALE_DB": str(root / "portale" / "portali.json"),
        "FATTURAZIONE_DB": str(root / "fatturazione" / "parcelle.json"),
        "NOTIFICHE_LOG": str(root / "notifiche" / "log.json"),
        "PAGAMENTI_DIR": str(root / "pagamenti"),
        "PREVENTIVI_DB": str(root / "preventivi" / "preventivi.json"),
        "SOGGETTI_DB": str(root / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(root / "soggetti" / "parti.json"),
        "WIZARD_PRO_DB": str(root / "wizard_pro" / "sessioni.json"),
        "LEGAL_INTELLIGENCE_DB": str(root / "intelligence" / "motori.json"),
        "LEGAL_UPDATES_JSON": str(root / "intelligence" / "legal_updates_repository.json"),
        "NORMATIVE_TABLES_DB": str(root / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(root / "intelligence" / "giurisprudenza.json"),
        "GIURISPRUDENZA_REPOSITORY_DB": str(root / "intelligence" / "giurisprudenza_repository.json"),
        "GIURISPRUDENZA_SOURCES_REPOSITORY_DB": str(root / "intelligence" / "giurisprudenza_sources_repository.json"),
        "GIURISPRUDENZA_SYNC_REGISTRY_DB": str(root / "intelligence" / "giurisprudenza_sync_registry.json"),
        "GIURISPRUDENZA_TAXONOMY_REPOSITORY_DB": str(root / "intelligence" / "giurisprudenza_taxonomy_repository.json"),
        "GIURISPRUDENZA_USAGE_POLICY_DB": str(root / "intelligence" / "giurisprudenza_usage_policy.json"),
        "LEGAL_ENGINE_SOURCE_EDGES_DB": str(root / "intelligence" / "legal_engine_source_edges.json"),
        "LEGAL_ENGINES_REPOSITORY_DB": str(root / "intelligence" / "legal_engines_repository.json"),
        "LEGAL_INTELLIGENCE_REPOSITORY_DB": str(root / "intelligence" / "legal_intelligence_repository.json"),
        "LEGAL_KEYWORD_TO_ENGINE_DB": str(root / "intelligence" / "legal_keyword_to_engine.json"),
        "LEGAL_KEYWORD_TO_SOURCE_DB": str(root / "intelligence" / "legal_keyword_to_source.json"),
        "LEGAL_OPERATIONAL_REPOSITORY_DB": str(root / "intelligence" / "legal_operational_repository.json"),
        "LEGAL_SOURCES_REPOSITORY_DB": str(root / "intelligence" / "legal_sources_repository.json"),
        "LEX_DATASET_DIR": str(root / "intelligence" / "lex_dataset"),
        "TELEMATICO_ACTIONS_REPOSITORY_DB": str(root / "intelligence" / "telematico_actions_repository.json"),
        "TELEMATICO_CAPABILITIES_REPOSITORY_DB": str(root / "intelligence" / "telematico_capabilities_repository.json"),
        "TELEMATICO_CATALOG_SNAPSHOT_DB": str(root / "intelligence" / "telematico_catalog_snapshot.json"),
        "TELEMATICO_CATALOG_SOURCES_REPOSITORY_DB": str(root / "intelligence" / "telematico_catalog_sources_repository.json"),
        "TELEMATICO_METHODS_REPOSITORY_DB": str(root / "intelligence" / "telematico_methods_repository.json"),
        "TELEMATICO_MONITORING_REPOSITORY_DB": str(root / "intelligence" / "telematico_monitoring_repository.json"),
        "TELEMATICO_REPOSITORY_JSON": str(root / "intelligence" / "telematico_repository.json"),
        "TELEMATICO_RULES_REPOSITORY_DB": str(root / "intelligence" / "telematico_rules_repository.json"),
        "TELEMATICO_SOURCES_REPOSITORY_DB": str(root / "intelligence" / "telematico_sources_repository.json"),
        "TELEMATICO_WIZARD_SECTIONS_REPOSITORY_DB": str(root / "intelligence" / "telematico_wizard_sections_repository.json"),
        "TELEMATICO_WSDL_MODULES_REPOSITORY_DB": str(root / "intelligence" / "telematico_wsdl_modules_repository.json"),
        "TELEMATICO_XSD_CHANNELS_REPOSITORY_DB": str(root / "intelligence" / "telematico_xsd_channels_repository.json"),
        "LEGAL_SKILLS_PROFILE_DB": str(root / "intelligence" / "legal_skills" / "profile.json"),
        "LEGAL_SKILLS_RUNS_DB": str(root / "intelligence" / "legal_skills" / "runs.json"),
        "LEGAL_SKILLS_SCHEDULED_DB": str(root / "intelligence" / "legal_skills" / "scheduled.json"),
        "WORKFLOW_AGENTS_RUNS_DB": str(root / "intelligence" / "workflow_agents" / "runs.json"),
        "WORKFLOW_AGENTS_METRICS_DB": str(root / "intelligence" / "workflow_agents" / "metrics.json"),
        "WORKFLOW_AGENTS_ACTIONS_DB": str(root / "intelligence" / "workflow_agents" / "actions.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(root / "intelligence" / "workspace_intelligence.json"),
        "LOCAL_AI_DB": str(root / "intelligence" / "local_ai.db"),
        "VALIDATION_RUNS_DB": str(root / "intelligence" / "validation_runs.json"),
        "TEMPLATE_ATTI_DB": str(root / "template_atti" / "templates.json"),
        "TEMPLATE_REPOSITORY_DB": str(root / "template_atti" / "template_repository.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(root / "template_atti" / "editor_layout.json"),
        "REDACTION_ASSISTANT_DB": str(root / "intelligence" / "assistente_redazionale.json"),
        "PREVENTIVI_REPOSITORY_DB": str(root / "preventivi" / "preventivi_repository.json"),
        "PREVENTIVI_WORKFLOW_STATES_DB": str(root / "preventivi" / "preventivi_workflow_states.json"),
        "PREVENTIVI_FIELD_MAP_DB": str(root / "preventivi" / "preventivi_field_map.json"),
        "PREVENTIVI_RULES_DB": str(root / "preventivi" / "preventivi_rules.json"),
        "TERMINI_PROCESSUALI_DB": str(root / "scadenziario" / "termini_processuali.json"),
        "TELEMATICO_DB": str(root / "telematico" / "workflow.db"),
        "EMAIL_CASELLA_DB": str(root / "email" / "casella.json"),
        "EMAIL_ORDINARIA_DB": str(root / "email" / "ordinaria.json"),
        "CONFIG_STUDIO_DB": str(root / "config" / "studio.json"),
        "STORAGE_CONFIG": str(root / "config" / "storage.json"),
        "STUDIO_LOCAL_PACK_DB": str(root / "config" / "studio_local_pack.json"),
        "STUDIO_CONFIG": str(root / "config" / "studio.json"),
        "STUDIO_DB": str(root / "studio.db"),
    }


def _ensure_sqlite_runtime_from_json(profile: StorageRuntimeProfile) -> None:
    """Crea o riallinea studio.db senza usare i JSON come fallback operativo."""

    root = Path(profile.studio_db_path).resolve().parent
    root.mkdir(parents=True, exist_ok=True)
    try:
        from pct.database import GestioneDatabase
        from pct.storage import StudioDB
        from pct.storage_migration import _build_json_to_sqlite_sources

        try:
            StudioDB.get(profile.studio_db_path).chiudi()
        except Exception:
            pass
        paths = _runtime_paths_for_studio_root(root)
        result = GestioneDatabase(
            _build_json_to_sqlite_sources(paths)
        ).migra_verso_sqlite(profile.studio_db_path)
        if not getattr(result, "riuscita", False):
            errors = "; ".join(str(item) for item in getattr(result, "errori", []) or [])
            raise RuntimeError(errors or "migrazione SQL non riuscita")
        StudioDB.get(profile.studio_db_path).ensure_schema()
        if has_app_context():
            current_app.logger.info(
                "Runtime SQL tenant riallineato da mirror JSON controllati: %s",
                profile.studio_db_path,
            )
    except Exception as exc:
        message = (
            "Archivio SQL dello studio non disponibile o non popolato. "
            "IUSENTRA ha provato a crearlo, ma non può usare i JSON come verità operativa: "
            f"{exc}"
        )
        if has_app_context():
            current_app.logger.exception(message)
        raise RuntimeError(message) from exc


def get_request_studio_db(anchor_path: str):
    profile = get_request_storage_runtime(anchor_path)

    if profile.effective_mode == DbMode.POSTGRESQL:
        cached = getattr(g, "_runtime_studio_db", None) if has_request_context() else None
        if cached is not None and getattr(cached, "backend_kind", "") == "postgresql":
            return cached
        studio_db = _postgres_runtime_backend(anchor_path, profile)
        if has_request_context():
            g._runtime_studio_db = studio_db
        return studio_db

    if not profile.uses_sqlite:
        return None

    anchor = Path(profile.data_anchor_path)
    studio_db_path = Path(profile.studio_db_path)
    if _sqlite_runtime_is_unseeded(studio_db_path, anchor):
        _ensure_sqlite_runtime_from_json(profile)

    cached = getattr(g, "_runtime_studio_db", None) if has_request_context() else None
    if cached is not None and str(getattr(cached, "db_path", "")) == profile.studio_db_path:
        return cached

    try:
        studio_db = ensure_core_storage_backend_contract(StudioDB.get(profile.studio_db_path))
    except (OSError, sqlite3.Error, TypeError) as exc:
        message = (
            "Archivio SQL dello studio non disponibile. "
            "Il sistema blocca l'operazione per evitare che un JSON storico diventi fonte operativa: "
            f"{exc}"
        )
        if has_app_context():
            current_app.logger.exception(message)
        raise RuntimeError(message) from exc

    if has_request_context():
        g._runtime_studio_db = studio_db
    return studio_db
