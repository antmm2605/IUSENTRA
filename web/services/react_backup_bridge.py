"""Bridge read-only per la pagina React dei backup."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _safe_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _size_mb(bytes_value: Any) -> float:
    return round(_safe_number(bytes_value) / 1024 / 1024, 2)


def _record(row: Any) -> dict[str, Any]:
    record_id = _text(getattr(row, "id", ""))
    file_name = Path(_text(getattr(row, "percorso_file", ""))).name
    stato = _enum(getattr(row, "stato", ""))
    return {
        "id": record_id,
        "timestamp": _text(getattr(row, "timestamp", "")),
        "type": _enum(getattr(row, "tipo", "")),
        "status": stato,
        "statusTone": "success" if stato == "OK" else "danger" if stato == "FALLITO" else "warning",
        "fileName": file_name,
        "sizeMb": _size_mb(getattr(row, "dimensione_bytes", 0)),
        "filesCount": _safe_number(getattr(row, "num_file", 0)),
        "components": list(getattr(row, "componenti", []) or []),
        "encrypted": bool(getattr(row, "cifrato", False)),
        "note": _text(getattr(row, "nota", "")),
        "error": _text(getattr(row, "errore", "")),
        "downloadHref": f"/backup/{record_id}/scarica?_legacy=1" if record_id and stato == "OK" else "",
        "verifyAction": f"/backup/{record_id}/verifica" if record_id and stato == "OK" else "",
        "restoreHref": f"/backup/{record_id}/ripristina?_legacy=1" if record_id and stato == "OK" else "",
        "deleteAction": f"/backup/{record_id}/elimina" if record_id else "",
    }


def _safe_config(config: Any) -> dict[str, Any]:
    return {
        "frequency": _enum(getattr(config, "frequenza", "")),
        "scheduledTime": _text(getattr(config, "ora_esecuzione", "")),
        "enabled": bool(getattr(config, "backup_abilitato", False)),
        "maxBackups": _safe_number(getattr(config, "max_backup", 0)),
        "includes": [
            {"id": "agenda", "label": "Agenda", "enabled": bool(getattr(config, "includi_agenda", False))},
            {"id": "clienti", "label": "Clienti", "enabled": bool(getattr(config, "includi_clienti", False))},
            {"id": "fascicoli", "label": "Fascicoli", "enabled": bool(getattr(config, "includi_fascicoli", False))},
            {"id": "messaggi", "label": "Messaggi", "enabled": bool(getattr(config, "includi_messaggi", False))},
            {"id": "documenti", "label": "Documenti", "enabled": bool(getattr(config, "includi_documenti", False))},
        ],
    }


def build_react_backup_payload(
    *,
    get_backup: Callable[[], Any],
    current_user: Any,
) -> dict[str, Any]:
    manager = get_backup()
    records = [_record(row) for row in manager.tutti()]
    stats = manager.statistiche() if hasattr(manager, "statistiche") else {}
    can_execute = _can(current_user, "backup.esegui")

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/backup.json",
        },
        "metrics": [
            {"id": "totale", "label": "Backup totali", "value": int(stats.get("totale", len(records)) or 0), "note": "Record nel registro backup", "tone": "primary"},
            {"id": "ok", "label": "Completati", "value": int(stats.get("ok", 0) or 0), "note": "Copie integre dichiarate", "tone": "success"},
            {"id": "falliti", "label": "Falliti", "value": int(stats.get("falliti", 0) or 0), "note": "Errori registrati", "tone": "danger" if int(stats.get("falliti", 0) or 0) else "neutral"},
            {"id": "spazio", "label": "Spazio totale", "value": f"{stats.get('dimensione_totale_mb', 0)} MB", "note": "Somma backup OK", "tone": "info"},
        ],
        "sections": [
            {
                "id": "config",
                "title": "Configurazione backup",
                "kind": "configuration",
                "items": [
                    {"id": "frequency", "label": "Frequenza", "value": _safe_config(manager.config).get("frequency"), "note": "Configurazione reale", "tone": "neutral"},
                    {"id": "time", "label": "Ora", "value": _safe_config(manager.config).get("scheduledTime"), "note": "Orario pianificato", "tone": "neutral"},
                    {"id": "enabled", "label": "Automatico", "value": "abilitato" if _safe_config(manager.config).get("enabled") else "disabilitato", "note": "Scheduler backup", "tone": "success" if _safe_config(manager.config).get("enabled") else "warning"},
                ],
                "emptyMessage": "Configurazione backup non disponibile.",
            },
            {
                "id": "components",
                "title": "Componenti inclusi",
                "kind": "components",
                "items": [
                    {"id": item["id"], "label": item["label"], "value": "incluso" if item["enabled"] else "escluso", "note": "", "tone": "success" if item["enabled"] else "neutral"}
                    for item in _safe_config(manager.config).get("includes", [])
                ],
                "emptyMessage": "Nessun componente configurato.",
            },
        ],
        "records": records,
        "actions": [
            {"id": "legacy", "label": "Apri backup legacy", "href": "/backup?_legacy=1", "method": "GET", "tone": "primary"},
            {"id": "refresh", "label": "Aggiorna stato", "href": "/backup?_legacy=1", "method": "GET", "tone": "neutral"},
        ],
        "forms": [
            {
                "id": "esegui_backup",
                "title": "Avvia backup legacy",
                "description": "Form standard verso POST /backup/esegui. Le operazioni tecniche restano sulle route Flask auditabili.",
                "action": "/backup/esegui",
                "method": "POST",
                "submitLabel": "Avvia backup legacy",
                "enabled": can_execute,
                "fields": [
                    {
                        "name": "tipo",
                        "label": "Tipo",
                        "type": "select",
                        "required": True,
                        "options": [
                            {"value": "COMPLETO", "label": "Completo"},
                            {"value": "INCREMENTALE", "label": "Incrementale"},
                        ],
                    },
                    {"name": "nota", "label": "Nota", "type": "text", "required": False},
                    {"name": "componenti", "label": "Componenti", "type": "checkbox", "required": False, "options": _safe_config(manager.config).get("includes", [])},
                ],
            }
        ],
        "warnings": [
            {
                "code": "backup_operazioni_legacy",
                "message": "Creazione, verifica, download e ripristino usano ancora le route legacy esistenti.",
            }
        ],
    }


def build_react_backup_error_payload(message: str = "Backup non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/backup.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [{"id": "legacy", "label": "Apri backup legacy", "href": "/backup?_legacy=1", "method": "GET", "tone": "neutral"}],
        "forms": [],
        "warnings": [
            {"code": "backup_errore_controllato", "message": message},
            {"code": "backup_operazioni_legacy", "message": "Le operazioni tecniche restano sulle route Flask esistenti."},
        ],
    }
