"""Dati operativi per la pagina amministrativa database."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    raw = str(value if value is not None else fallback).strip()
    return raw or fallback


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _date_label(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return "n.d."
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.hour or parsed.minute:
            return parsed.strftime("%d/%m/%Y %H:%M")
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return raw


def _module_kind(module: dict[str, Any]) -> dict[str, str]:
    name = _text(module.get("nome"))
    if name == "search_index":
        return {"label": "SQLite", "tone": "info"}
    if bool(module.get("migrabile_sqlite")):
        return {"label": "JSON core", "tone": "primary"}
    return {"label": "JSON", "tone": "neutral"}


def _status_payload(status: Any, error: Any = "") -> dict[str, str]:
    raw = _text(status, "OK").upper()
    labels = {
        "OK": ("OK", "success"),
        "VUOTO": ("Vuoto", "neutral"),
        "NON_TROVATO": ("Non trovato", "warning"),
        "NON_CONFIGURATO": ("Non configurato", "warning"),
        "ERRORE": ("Errore", "danger"),
    }
    label, tone = labels.get(raw, (raw.title(), "danger"))
    return {"code": raw, "label": label, "tone": tone, "message": _text(error)}


def _module_payload(module: Any, index: int) -> dict[str, Any]:
    row = dict(module or {}) if isinstance(module, dict) else {}
    name = _text(row.get("nome"), f"modulo_{index}")
    return {
        "id": name,
        "name": name,
        "label": name.replace("_", " ").title(),
        "path": _text(row.get("percorso")),
        "exists": bool(row.get("esiste")),
        "records": _number(row.get("record_totali")),
        "sizeBytes": _number(row.get("dimensione_bytes")),
        "sizeLabel": _text(row.get("dimensione_leggibile"), "0 B"),
        "lastModified": _text(row.get("ultima_modifica")),
        "lastModifiedLabel": _date_label(row.get("ultima_modifica")),
        "migratableSqlite": bool(row.get("migrabile_sqlite")),
        "kind": _module_kind(row),
        "status": _status_payload(row.get("stato"), row.get("errore")),
    }


def _usage_items(values: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not isinstance(values, list):
        return items
    for index, row in enumerate(values):
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            label, count = row[0], row[1]
        elif isinstance(row, dict):
            label, count = row.get("label") or row.get("azione") or row.get("utente"), row.get("count") or row.get("totale")
        else:
            continue
        items.append({"id": f"uso-{index}", "label": _text(label, "n.d."), "count": _number(count)})
    return items


def _usage_payload(usage: Any) -> dict[str, Any]:
    data = dict(usage or {}) if isinstance(usage, dict) else {}
    return {
        "available": bool(data.get("disponibile")),
        "error": _text(data.get("errore")),
        "totalEvents": _number(data.get("totale_eventi")),
        "topActions": _usage_items(data.get("azioni_frequenti")),
        "topUsers": _usage_items(data.get("utenti_attivi")),
        "peakHour": None if data.get("ora_punta") is None else _number(data.get("ora_punta")),
        "errorRate": _float(data.get("tasso_errori")),
        "recentErrors": list(data.get("errori_recenti") or []) if isinstance(data.get("errori_recenti"), list) else [],
    }


def _sqlite_payload(sqlite_info: Any) -> dict[str, Any]:
    data = dict(sqlite_info or {}) if isinstance(sqlite_info, dict) else {}
    tables = data.get("tabelle") if isinstance(data.get("tabelle"), dict) else {}
    return {
        "exists": bool(data.get("esiste")),
        "error": _text(data.get("errore")),
        "sizeLabel": _text(data.get("dimensione"), "n.d."),
        "sizeBytes": _number(data.get("dimensione_bytes")),
        "totalPages": _number(data.get("pagine_totali")),
        "freePages": _number(data.get("pagine_libere")),
        "fragmentationPct": _float(data.get("frammentazione_pct")),
        "pageSize": _number(data.get("page_size")),
        "tables": [
            {"name": _text(name), "records": _number(count)}
            for name, count in sorted(tables.items())
        ],
    }


def _actions_payload() -> dict[str, str]:
    return {
        "refresh": "/api/v1/ui/admin/database",
        "verify": "/admin/database/verifica",
        "repair": "/admin/database/verifica-ripara",
        "optimize": "/admin/database/ottimizza",
        "migrate": "/admin/database/migra",
        "precheckSqlite": "/admin/database/preverifica-sqlite",
        "reconcileSqlite": "/admin/database/riconcilia-sqlite",
        "activateSqlite": "/admin/database/attiva-sqlite",
        "exportZip": "/admin/database/export",
        "backup": "/backup",
        "audit": "/audit",
    }


def build_react_admin_database_payload(
    get_database: Callable[[], Any],
    latest_sqlite_snapshot_path: Callable[[str], str],
    *,
    backup_dir: str,
    path: str = "/admin/database",
) -> dict[str, Any]:
    """Costruisce il contratto dati reale per ``/admin/database`` React."""

    database = get_database()
    stats = database.statistiche()
    usage = database.analisi_uso()
    sqlite_info = database.statistiche_sqlite(latest_sqlite_snapshot_path(backup_dir))
    modules = [_module_payload(module, index) for index, module in enumerate(stats.get("moduli") or [])]
    status_counts: dict[str, int] = {}
    for module in modules:
        code = _text(module.get("status", {}).get("code"), "OK")
        status_counts[code] = status_counts.get(code, 0) + 1

    return {
        "source": "repository_reali",
        "generatedAt": _iso_now(),
        "page": {
            "title": "Gestione Database",
            "subtitle": "Statistiche, integrità, ottimizzazione, migrazione SQLite ed export dei moduli dati.",
            "path": path,
        },
        "summary": {
            "modulesMonitored": _number(stats.get("moduli_monitorati") or len(modules)),
            "modulesMigratableSqlite": _number(stats.get("moduli_migrabili_sqlite")),
            "totalRecords": _number(stats.get("totale_record")),
            "totalSizeBytes": _number(stats.get("totale_dimensione_bytes")),
            "totalSizeLabel": _text(stats.get("totale_dimensione"), "0 B"),
            "sqliteFragmentationPct": _float(_sqlite_payload(sqlite_info).get("fragmentationPct")),
            "statusCounts": status_counts,
            "generatedLabel": _date_label(stats.get("generato_il")),
        },
        "modules": modules,
        "sqlite": _sqlite_payload(sqlite_info),
        "usage": _usage_payload(usage),
        "actions": _actions_payload(),
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
            "legacy_fallback": "Percorso di recupero",
        },
    }


def build_react_admin_database_error_payload(message: str) -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generatedAt": _iso_now(),
        "page": {
            "title": "Gestione Database",
            "subtitle": "La pagina Database non e' raggiungibile in questo momento.",
            "path": "/admin/database",
        },
        "summary": {
            "modulesMonitored": 0,
            "modulesMigratableSqlite": 0,
            "totalRecords": 0,
            "totalSizeBytes": 0,
            "totalSizeLabel": "0 B",
            "sqliteFragmentationPct": 0,
            "statusCounts": {},
            "generatedLabel": "n.d.",
        },
        "modules": [],
        "sqlite": _sqlite_payload({}),
        "usage": _usage_payload({}),
        "actions": _actions_payload(),
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
            "legacy_fallback": "Percorso di recupero",
        },
        "warning": message,
    }
