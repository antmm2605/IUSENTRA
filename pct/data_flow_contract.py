"""Contratto operativo dati, tenant e route React per IUSENTRA.

Questo modulo non esegue migrazioni: descrive cio' che ogni area
applicativa deve presidiare e fornisce un audit riutilizzabile nei test.
L'obiettivo e' impedire che un flusso resti solo JSON, solo SQLite,
solo PostgreSQL o solo UI senza essere collegato al tenant corretto.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DataFlowArea:
    label: str
    react_routes: tuple[str, ...] = ()
    menu_items: tuple[tuple[str, str], ...] = ()
    api_routes: tuple[str, ...] = ()
    tenant_path_keys: tuple[str, ...] = ()
    json_modules: tuple[str, ...] = ()
    sqlite_tables: tuple[str, ...] = ()
    postgres_tables: tuple[str, ...] = ()
    external_repositories: tuple[str, ...] = ()
    topbar_hooks: tuple[str, ...] = ()


APPLICATION_DATA_FLOW_AREAS: dict[str, DataFlowArea] = {
    "panoramica": DataFlowArea(
        label="Panoramica",
        react_routes=("/",),
        menu_items=(("Panoramica", "/"),),
        api_routes=("/api/dashboard/data", "/api/dashboard/today"),
        tenant_path_keys=("AGENDA_DB", "SCADENZIARIO_DB", "FASCICOLI_DB", "CLIENTI_DB"),
        json_modules=("appuntamenti", "scadenze", "fascicoli", "clienti"),
        sqlite_tables=("appuntamenti", "scadenze", "fascicoli", "clienti"),
        postgres_tables=("appuntamenti", "scadenze", "fascicoli", "clienti"),
    ),
    "regia_operativa": DataFlowArea(
        label="Regia Operativa",
        react_routes=("/workspace-intelligente",),
        menu_items=(("Regia Operativa", "/workspace-intelligente"),),
        api_routes=("/api/v1/ui/workspace-intelligente",),
        tenant_path_keys=("WORKSPACE_INTELLIGENCE_DB", "AGENDA_DB", "FASCICOLI_DB"),
        json_modules=("appuntamenti", "fascicoli", "scadenze"),
        sqlite_tables=("appuntamenti", "fascicoli", "scadenze"),
        postgres_tables=("appuntamenti", "fascicoli", "scadenze"),
        external_repositories=("workspace_intelligence",),
    ),
    "ricerca_studio": DataFlowArea(
        label="Ricerca Studio",
        react_routes=("/global-search",),
        menu_items=(("Ricerca Studio", "/global-search"),),
        api_routes=("/api/search/global",),
        tenant_path_keys=("SEARCH_INDEX", "FASCICOLI_DB", "CLIENTI_DB", "MESSAGGI_DB"),
        json_modules=("fascicoli", "clienti", "messaggi"),
        sqlite_tables=("fascicoli", "clienti", "messaggi"),
        postgres_tables=("fascicoli", "clienti", "messaggi"),
    ),
    "agenda": DataFlowArea(
        label="Agenda",
        react_routes=("/agenda", "/agenda/nuovo", "/timesheet"),
        menu_items=(
            ("Calendario", "/agenda"),
            ("Nuovo Appuntamento", "/agenda/nuovo"),
            ("Timesheet", "/timesheet"),
        ),
        api_routes=("/api/v1/ui/agenda", "/api/dashboard/today"),
        tenant_path_keys=("AGENDA_DB", "CLIENTI_DB", "FASCICOLI_DB", "CALENDAR_SYNC_DB"),
        json_modules=("appuntamenti", "clienti", "fascicoli"),
        sqlite_tables=("appuntamenti", "clienti", "fascicoli"),
        postgres_tables=("appuntamenti", "clienti", "fascicoli"),
        external_repositories=("calendar_sync",),
    ),
    "fascicoli": DataFlowArea(
        label="Fascicoli",
        react_routes=(
            "/fascicoli",
            "/fascicoli/nuovo",
            "/fascicoli/archivio",
            "/fascicoli/:id/deposito/prepara",
        ),
        menu_items=(
            ("Tutti i Fascicoli", "/fascicoli"),
            ("Nuovo Fascicolo", "/fascicoli/nuovo"),
            ("Archivio", "/fascicoli/archivio"),
        ),
        api_routes=("/api/v1/ui/fascicoli", "/api/v1/ui/fascicoli/deposito/prepara"),
        tenant_path_keys=("FASCICOLI_DB", "FASCICOLI_DOCS", "FASCICOLI_ARCH", "TELEMATICO_DB"),
        json_modules=("fascicoli",),
        sqlite_tables=("fascicoli",),
        postgres_tables=("fascicoli",),
        external_repositories=("telematico_repository", "portal_repository"),
    ),
    "clienti_anagrafiche": DataFlowArea(
        label="Clienti e Anagrafiche",
        react_routes=("/clienti", "/clienti/nuovo", "/cartelle-condivise", "/app/portale-clienti"),
        menu_items=(
            ("Anagrafica", "/clienti"),
            ("Nuovo Cliente", "/clienti/nuovo"),
            ("Cartelle Condivise", "/cartelle-condivise"),
            ("Portale Clienti", "/app/portale-clienti"),
        ),
        api_routes=("/api/v1/ui/clienti",),
        tenant_path_keys=("CLIENTI_DB",),
        json_modules=("clienti",),
        sqlite_tables=("clienti",),
        postgres_tables=("clienti",),
    ),
    "soggetti_parti": DataFlowArea(
        label="Soggetti e Parti",
        react_routes=("/soggetti", "/soggetti/nuovo"),
        menu_items=(
            ("Anagrafica", "/soggetti"),
            ("Nuovo Soggetto", "/soggetti/nuovo"),
        ),
        api_routes=("/api/v1/ui/soggetti",),
        tenant_path_keys=("SOGGETTI_DB", "SOGGETTI_PARTI_DB"),
        json_modules=("soggetti", "soggetti_parti"),
        sqlite_tables=("soggetti", "soggetti_parti"),
        postgres_tables=("soggetti", "soggetti_parti"),
    ),
    "comunicazioni": DataFlowArea(
        label="Comunicazioni",
        react_routes=("/email", "/email-ordinaria", "/messaggi", "/messaggi/nuovo", "/notifiche-legali"),
        menu_items=(
            ("Email PEC", "/email/"),
            ("PEC", "/email/"),
            ("Notifiche legali", "/notifiche-legali"),
            ("L.53", "/notifiche-legali"),
            ("Email ordinaria", "/email-ordinaria/"),
            ("SMTP", "/email-ordinaria/"),
            ("Messaggi", "/messaggi"),
            ("Nuovo SMS/WA", "/messaggi/nuovo"),
        ),
        api_routes=(
            "/api/v1/ui/email",
            "/api/v1/ui/email-ordinaria",
            "/api/v1/ui/messaggi",
            "/api/v1/ui/notifiche-legali",
        ),
        tenant_path_keys=("EMAIL_CASELLA_DB", "EMAIL_ORDINARIA_DB", "MESSAGGI_DB", "NOTIFICHE_LOG"),
        json_modules=("email_casella", "email_ordinaria", "messaggi", "notifiche"),
        sqlite_tables=("messaggi", "notifiche_log"),
        postgres_tables=("messaggi", "notifiche_log"),
    ),
    "scadenze_termini": DataFlowArea(
        label="Scadenze e Termini",
        react_routes=("/scadenziario", "/scadenziario/nuova", "/wizard-pro", "/deposito/checklist"),
        menu_items=(
            ("Scadenziario", "/scadenziario"),
            ("Nuova Scadenza", "/scadenziario/nuova"),
            ("Preparazione Udienza Guidata", "/wizard-pro/"),
            ("Controlli Atti", "/deposito/checklist"),
        ),
        api_routes=("/api/v1/ui/scadenziario", "/api/deadlines/quick-summary"),
        tenant_path_keys=("SCADENZIARIO_DB", "AGENDA_DB", "FASCICOLI_DB"),
        json_modules=("scadenze", "appuntamenti", "fascicoli"),
        sqlite_tables=("scadenze", "appuntamenti", "fascicoli"),
        postgres_tables=("scadenze", "appuntamenti", "fascicoli"),
    ),
    "servizi_telematici": DataFlowArea(
        label="Servizi Telematici",
        react_routes=(
            "/telematico",
            "/servizi-telematici",
            "/polisWeb",
            "/pdp",
            "/pat",
            "/sigit",
            "/tribunali",
            "/deposito/checklist",
            "/guida/firma-digitale",
        ),
        menu_items=(
            ("Centro Servizi Telematici", "/telematico"),
            ("PolisWeb / PST", "/polisWeb"),
            ("PDP Penale", "/pdp"),
            ("PAT Amministrativo", "/pat"),
            ("PTT Tributario", "/sigit"),
            ("Tribunali / PEC", "/tribunali"),
            ("Checklist deposito", "/deposito/checklist"),
            ("Guida firma digitale", "/guida/firma-digitale"),
        ),
        api_routes=("/api/v1/ui/telematico", "/api/v1/ui/telematico/surface/checklist"),
        tenant_path_keys=("PORTALE_DB", "PORTALE_UPLOADS", "TELEMATICO_DB", "LOCAL_AI_DB"),
        json_modules=("portale",),
        sqlite_tables=("moduli_dati", "moduli_json_records"),
        postgres_tables=("moduli_dati", "moduli_json_records"),
        external_repositories=("telematico_repository", "portal_repository", "local_signer"),
    ),
    "studio": DataFlowArea(
        label="Studio",
        react_routes=(
            "/studio",
            "/fatturazione",
            "/preventivi",
            "/compensi-forensi",
            "/documenti",
            "/redazione-atti",
            "/statistiche",
            "/ricerca-legale",
            "/legal-skills",
            "/workflow-agents",
            "/giurisprudenza",
            "/strumenti-legali",
            "/strumenti-operativi",
        ),
        menu_items=(
            ("Studio", "/studio"),
            ("Parcelle e Fatture", "/fatturazione/"),
            ("Preventivi e Incarichi", "/preventivi/"),
            ("Compensi Forensi", "/compensi-forensi"),
            ("Documenti", "/documenti"),
            ("Redazione Atti", "/redazione-atti"),
            ("Statistiche", "/statistiche/"),
            ("Ricerca Legale", "/ricerca-legale"),
            ("Legal Skills", "/legal-skills"),
            ("Regia Agentica", "/workflow-agents"),
            ("Archivio Giurisprudenza", "/giurisprudenza/"),
            ("Strumenti Forensi", "/strumenti-legali/"),
            ("Strumenti Operativi", "/strumenti-operativi"),
        ),
        api_routes=(
            "/api/v1/ui/studio",
            "/api/v1/ui/fatturazione",
            "/api/v1/ui/preventivi",
            "/api/v1/ui/studio-modules/strumenti-forensi",
            "/api/v1/legal-skills/packs",
            "/api/v1/ui/workflow-agents",
        ),
        tenant_path_keys=(
            "TIMESHEET_DB",
            "TIME_TRACKING_DB",
            "PREVENTIVI_DB",
            "FATTURAZIONE_DB",
            "LEGAL_INTELLIGENCE_DB",
            "GIURISPRUDENZA_DB",
        ),
        json_modules=("timesheet", "time_tracking", "preventivi", "fatturazione"),
        sqlite_tables=(
            "timesheet_entries",
            "time_tracking_timers",
            "preventivi_records",
            "conferimenti_records",
            "parcelle",
        ),
        postgres_tables=(
            "timesheet_entries",
            "time_tracking_timers",
            "preventivi_records",
            "conferimenti_records",
            "parcelle",
        ),
        external_repositories=(
            "legal_intelligence",
            "giurisprudenza",
            "template_atti",
            "legal_skills",
            "workflow_agents",
        ),
    ),
    "sito_studio": DataFlowArea(
        label="Sito Studio",
        react_routes=("/sito-studio", "/sito-studio/builder", "/sito-studio/redazione-ai", "/sito-studio/contatti"),
        menu_items=(
            ("Sito Studio", "/sito-studio/"),
            ("Builder Sito", "/sito-studio/builder"),
            ("Redazione AI Sito", "/sito-studio/redazione-ai"),
            ("Contatti Sito", "/sito-studio/contatti"),
        ),
        api_routes=("/api/v1/ui/sito-studio",),
        tenant_path_keys=("STUDIO_DB", "CONFIG_STUDIO_DB"),
        json_modules=("impostazioni",),
        sqlite_tables=("settings_config", "moduli_dati", "moduli_json_records"),
        postgres_tables=("settings_config", "moduli_dati", "moduli_json_records"),
    ),
    "impostazioni": DataFlowArea(
        label="Impostazioni",
        react_routes=("/impostazioni", "/impostazioni/sdi", "/impostazioni/calendario", "/backup"),
        menu_items=(
            ("Impostazioni Studio", "/impostazioni"),
            ("Notifiche", "/impostazioni?tab=notifiche"),
            ("Pagamenti", "/impostazioni?tab=pagamenti"),
            ("Canali SdI", "/impostazioni/sdi"),
            ("Backup", "/impostazioni?tab=backup"),
            ("Sincronizzazione Calendari", "/impostazioni/calendario"),
        ),
        api_routes=("/api/v1/ui/impostazioni", "/api/v1/ui/backup"),
        tenant_path_keys=("CONFIG_STUDIO_DB", "STORAGE_CONFIG", "BACKUP_DIR", "CALENDAR_SYNC_DB"),
        json_modules=("impostazioni", "backup_config", "backup"),
        sqlite_tables=("settings_config", "backup_config", "backup_records"),
        postgres_tables=("settings_config", "backup_config", "backup_records"),
        external_repositories=("calendar_sync",),
    ),
    "amministrazione": DataFlowArea(
        label="Amministrazione",
        react_routes=(
            "/amministrazione",
            "/utenti",
            "/profili",
            "/registro-attivita",
            "/registro-gdpr",
            "/audit",
            "/privacy/registro",
            "/importa-pratiche-studio-telematico",
            "/admin/database",
        ),
        menu_items=(
            ("Amministrazione", "/amministrazione"),
            ("Utenti", "/utenti"),
            ("Profili e Permessi", "/profili"),
            ("Registro Attività", "/audit"),
            ("Importa pratiche da Studio Telematico", "/importa-pratiche-studio-telematico"),
            ("Database", "/admin/database"),
            ("Registro GDPR", "/privacy/registro"),
        ),
        api_routes=("/api/v1/ui/amministrazione", "/api/v1/ui/admin/database"),
        tenant_path_keys=("AUTH_DB", "AUDIT_DB", "PRIVACY_DB", "STUDIO_DB"),
        json_modules=("utenti", "audit", "privacy"),
        sqlite_tables=("utenti", "audit_log", "privacy_trattamenti"),
        postgres_tables=("utenti", "audit_log", "privacy_trattamenti"),
    ),
    "topbar": DataFlowArea(
        label="Topbar operativa",
        api_routes=(
            "/api/search/global",
            "/api/dashboard/today",
            "/api/notifications",
            "/api/deadlines/quick-summary",
            "/api/recent",
            "/api/recent/search",
            "/api/time-tracking/active",
            "/support/studio/sessione",
        ),
        tenant_path_keys=(
            "AGENDA_DB",
            "SCADENZIARIO_DB",
            "EMAIL_CASELLA_DB",
            "FASCICOLI_DB",
            "CLIENTI_DB",
            "SOGGETTI_DB",
            "TIMESHEET_DB",
            "TIME_TRACKING_DB",
            "MESSAGGI_DB",
            "NOTIFICATIONS_DB",
        ),
        json_modules=("appuntamenti", "scadenze", "fascicoli", "clienti", "soggetti", "timesheet", "time_tracking", "messaggi"),
        sqlite_tables=(
            "appuntamenti",
            "scadenze",
            "fascicoli",
            "clienti",
            "soggetti",
            "timesheet_entries",
            "time_tracking_timers",
            "messaggi",
        ),
        postgres_tables=(
            "appuntamenti",
            "scadenze",
            "fascicoli",
            "clienti",
            "soggetti",
            "timesheet_entries",
            "time_tracking_timers",
            "messaggi",
        ),
        external_repositories=("notifications_db", "support_remote"),
        topbar_hooks=(
            "Voce Studio",
            "Assistenza remota",
            "data italiana",
            "nuovo elemento",
            "notifiche operative",
            "ultimi elementi aperti",
            "ricerche recenti",
            "scadenze rapide",
            "timer attività",
        ),
    ),
}


def required_sqlite_tables() -> set[str]:
    return {
        table
        for area in APPLICATION_DATA_FLOW_AREAS.values()
        for table in area.sqlite_tables
    }


def required_postgres_tables() -> set[str]:
    return {
        table
        for area in APPLICATION_DATA_FLOW_AREAS.values()
        for table in area.postgres_tables
    }


def required_tenant_path_keys() -> set[str]:
    return {
        key
        for area in APPLICATION_DATA_FLOW_AREAS.values()
        for key in area.tenant_path_keys
    }


def required_json_modules() -> set[str]:
    return {
        module
        for area in APPLICATION_DATA_FLOW_AREAS.values()
        for module in area.json_modules
    }


def required_react_routes() -> set[str]:
    return {
        route
        for area in APPLICATION_DATA_FLOW_AREAS.values()
        for route in area.react_routes
    }


def required_menu_items() -> dict[str, set[str]]:
    items: dict[str, set[str]] = {}
    for area in APPLICATION_DATA_FLOW_AREAS.values():
        for label, href in area.menu_items:
            items.setdefault(label, set()).add(_normalise_href(href))
    return items


def _normalise_href(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    path = clean.split("?", 1)[0].rstrip("/") or "/"
    return path


def _extract_sidebar_items(app_tsx_path: str | Path = "frontend/src/App.tsx") -> dict[str, set[str]]:
    source = Path(app_tsx_path).read_text(encoding="utf-8")
    pattern = re.compile(
        r"label:\s*'([^']+)'\s*,\s*icon:\s*[A-Za-z0-9_]+,\s*href:\s*'([^']+)'(?:\s*,\s*badge:\s*'([^']+)')?",
        re.MULTILINE,
    )
    items: dict[str, set[str]] = {}
    for match in pattern.finditer(source):
        label, href, badge = match.groups()
        normalised = _normalise_href(href)
        items.setdefault(label, set()).add(normalised)
        if badge:
            items.setdefault(badge, set()).add(normalised)
    return items


def _extract_create_tables(sql_text: str) -> set[str]:
    pattern = re.compile(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    )
    return {match.group(1) for match in pattern.finditer(sql_text or "")}


def sqlite_schema_tables() -> set[str]:
    from pct.database import SCHEMA_SQL

    return _extract_create_tables(SCHEMA_SQL)


def postgres_schema_tables() -> set[str]:
    from pct.storage_postgres import CORE_POSTGRES_SCHEMA_SQL

    if isinstance(CORE_POSTGRES_SCHEMA_SQL, str):
        return _extract_create_tables(CORE_POSTGRES_SCHEMA_SQL)
    value = _literal_from_storage_postgres("CORE_POSTGRES_SCHEMA_SQL")
    return _extract_create_tables(value if isinstance(value, str) else "")


def postgres_contract_tables() -> set[str]:
    from pct.storage_postgres import CORE_TABLE_COLUMNS

    if isinstance(CORE_TABLE_COLUMNS, dict):
        return set(CORE_TABLE_COLUMNS)
    value = _literal_from_storage_postgres("CORE_TABLE_COLUMNS")
    return set(value) if isinstance(value, dict) else set()


def _literal_from_storage_postgres(name: str) -> Any:
    source_path = Path(__file__).with_name("storage_postgres.py")
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return ast.literal_eval(node.value)
    except Exception:
        return None
    return None


def _load_route_manifest(path: str | Path | None = None) -> list[dict[str, Any]]:
    manifest_path = Path(path or "tools/react-migration/route-manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    routes = payload.get("routes") if isinstance(payload, dict) else payload
    if not isinstance(routes, list):
        return []
    return [route for route in routes if isinstance(route, dict)]


def full_react_routes(path: str | Path | None = None) -> set[str]:
    result: set[str] = set()
    for route in _load_route_manifest(path):
        if route.get("status") == "react_operational_full" and route.get("unlockFromGate") is True:
            value = str(route.get("route") or "").strip()
            if value:
                result.add(value)
    return result


def _is_inside(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _path_key_must_be_tenant_scoped(key: str) -> bool:
    return key not in {"SUPPORT_DB"}


def audit_data_flow_contract(
    *,
    paths: dict[str, str] | None = None,
    tenant_root: str | Path | None = None,
    route_manifest_path: str | Path | None = None,
    app_tsx_path: str | Path = "frontend/src/App.tsx",
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    sqlite_missing = sorted(required_sqlite_tables() - sqlite_schema_tables())
    if sqlite_missing:
        errors.append("SQLite senza tabelle richieste: " + ", ".join(sqlite_missing))

    postgres_missing = sorted(required_postgres_tables() - postgres_schema_tables())
    if postgres_missing:
        errors.append("PostgreSQL senza tabelle richieste: " + ", ".join(postgres_missing))

    postgres_contract_missing = sorted(required_postgres_tables() - postgres_contract_tables())
    if postgres_contract_missing:
        errors.append(
            "CORE_TABLE_COLUMNS non dichiara tabelle richieste: "
            + ", ".join(postgres_contract_missing)
        )

    route_missing = sorted(required_react_routes() - full_react_routes(route_manifest_path))
    if route_missing:
        errors.append("Route richieste non full React: " + ", ".join(route_missing))

    sidebar_items = _extract_sidebar_items(app_tsx_path)
    menu_missing: list[str] = []
    for label, hrefs in sorted(required_menu_items().items()):
        actual = sidebar_items.get(label, set())
        missing_hrefs = sorted({_normalise_href(href) for href in hrefs} - actual)
        if missing_hrefs:
            menu_missing.append(f"{label} -> {', '.join(missing_hrefs)}")
    if menu_missing:
        errors.append("Sottomenu/alias mancanti nella sidebar React: " + "; ".join(menu_missing))

    menu_data_missing = [
        key
        for key, area in APPLICATION_DATA_FLOW_AREAS.items()
        if area.menu_items
        and not (
            area.tenant_path_keys
            and (
                area.sqlite_tables
                or area.postgres_tables
                or area.json_modules
                or area.external_repositories
            )
        )
    ]
    if menu_data_missing:
        errors.append(
            "Aree con sottomenu senza contratto dati: " + ", ".join(sorted(menu_data_missing))
        )

    path_missing: list[str] = []
    path_outside_tenant: list[str] = []
    if paths is not None:
        for key in sorted(required_tenant_path_keys()):
            value = str(paths.get(key) or "").strip()
            if not value:
                path_missing.append(key)
                continue
            if tenant_root and _path_key_must_be_tenant_scoped(key):
                candidate = Path(value)
                if not _is_inside(Path(tenant_root), candidate):
                    path_outside_tenant.append(f"{key}={value}")
        if path_missing:
            errors.append("Path tenant mancanti: " + ", ".join(path_missing))
        if path_outside_tenant:
            errors.append(
                "Path fuori tenant rilevati: " + "; ".join(path_outside_tenant)
            )

    area_report = {
        key: {
            "label": area.label,
            "react_routes": list(area.react_routes),
            "menu_items": [{"label": label, "href": href} for label, href in area.menu_items],
            "api_routes": list(area.api_routes),
            "tenant_path_keys": list(area.tenant_path_keys),
            "json_modules": list(area.json_modules),
            "sqlite_tables": list(area.sqlite_tables),
            "postgres_tables": list(area.postgres_tables),
            "external_repositories": list(area.external_repositories),
            "topbar_hooks": list(area.topbar_hooks),
        }
        for key, area in APPLICATION_DATA_FLOW_AREAS.items()
    }

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "areas": area_report,
        "required": {
            "sqlite_tables": sorted(required_sqlite_tables()),
            "postgres_tables": sorted(required_postgres_tables()),
            "tenant_path_keys": sorted(required_tenant_path_keys()),
            "json_modules": sorted(required_json_modules()),
            "react_routes": sorted(required_react_routes()),
            "menu_items": {
                label: sorted(hrefs)
                for label, hrefs in sorted(required_menu_items().items())
            },
        },
    }
