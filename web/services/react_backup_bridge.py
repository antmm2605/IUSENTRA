"""Bridge operativo per la pagina React dei backup."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pct.backup import StatoBackup, TipoBackup


_COMPONENT_LABELS = {
    "agenda": "Agenda",
    "clienti": "Clienti",
    "fascicoli": "Fascicoli",
    "messaggi": "Messaggi",
    "documenti": "Documenti",
}
_CREATE_KEYS = {"type", "components", "note", "confirm"}
_VERIFY_KEYS = {"backupId", "confirm"}


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


def _tone_for_state(state: str) -> str:
    if state == StatoBackup.OK.value:
        return "success"
    if state == StatoBackup.FALLITO.value:
        return "danger"
    if state == StatoBackup.CORROTTO.value:
        return "warning"
    return "neutral"


def _state_label(state: str) -> str:
    return {
        StatoBackup.OK.value: "Completato",
        StatoBackup.FALLITO.value: "Fallito",
        StatoBackup.CORROTTO.value: "Da verificare",
    }.get(state, state or "Stato non indicato")


def _record(row: Any) -> dict[str, Any]:
    record_id = _text(getattr(row, "id", ""))
    file_name = Path(_text(getattr(row, "percorso_file", ""))).name
    state = _enum(getattr(row, "stato", ""))
    can_download = bool(record_id and state == StatoBackup.OK.value)
    return {
        "id": record_id,
        "createdAt": _text(getattr(row, "timestamp", "")),
        "type": _enum(getattr(row, "tipo", "")),
        "state": state,
        "stateLabel": _state_label(state),
        "stateTone": _tone_for_state(state),
        "fileName": file_name,
        "sizeMb": _size_mb(getattr(row, "dimensione_bytes", 0)),
        "filesCount": _safe_number(getattr(row, "num_file", 0)),
        "components": [_text(item) for item in list(getattr(row, "componenti", []) or []) if _text(item)],
        "encrypted": bool(getattr(row, "cifrato", False)),
        "note": _text(getattr(row, "nota", "")),
        "error": _text(getattr(row, "errore", "")),
        "downloadHref": f"/backup/{record_id}/scarica" if can_download else "",
        "restoreHref": f"/backup/{record_id}/ripristina?_legacy=1" if can_download else "",
    }


def _available_components(manager: Any) -> list[str]:
    configured = getattr(manager, "_percorsi", {}) or {}
    if isinstance(configured, dict) and configured:
        return [str(key) for key in configured.keys() if _text(key)]
    return list(_COMPONENT_LABELS.keys())


def _component_options(manager: Any) -> list[dict[str, Any]]:
    configured = set(_available_components(manager))
    config = getattr(manager, "config", None)
    options: list[dict[str, Any]] = []
    for key in _COMPONENT_LABELS:
        enabled = bool(getattr(config, f"includi_{key}", True))
        options.append(
            {
                "id": key,
                "label": _COMPONENT_LABELS[key],
                "available": key in configured,
                "enabled": enabled and key in configured,
            }
        )
    for key in configured - set(_COMPONENT_LABELS):
        options.append({"id": key, "label": key.replace("_", " ").title(), "available": True, "enabled": True})
    return options


def _status(manager: Any, records: list[dict[str, Any]]) -> dict[str, Any]:
    stats = manager.statistiche() if hasattr(manager, "statistiche") else {}
    config = getattr(manager, "config", None)
    return {
        "total": int(stats.get("totale", len(records)) or 0),
        "completed": int(stats.get("ok", 0) or 0),
        "failed": int(stats.get("falliti", 0) or 0),
        "corrupted": int(stats.get("corrotti", 0) or 0),
        "totalSizeMb": float(stats.get("dimensione_totale_mb", 0) or 0),
        "lastBackupAt": _text(stats.get("ultimo", "")),
        "automaticEnabled": bool(getattr(config, "backup_abilitato", False)),
        "frequency": _enum(getattr(config, "frequenza", "")),
        "scheduledTime": _text(getattr(config, "ora_esecuzione", "")),
        "maxBackups": _safe_number(getattr(config, "max_backup", 0)),
        "configuredComponents": _component_options(manager),
    }


def _integrity(records: list[dict[str, Any]]) -> dict[str, Any]:
    corrupted = [record for record in records if record["state"] == StatoBackup.CORROTTO.value]
    latest = records[0] if records else {}
    return {
        "available": bool(records),
        "state": "attention" if corrupted else "ok" if records else "empty",
        "label": "Verifiche con anomalie" if corrupted else "Nessuna anomalia registrata" if records else "Nessun backup verificabile",
        "lastCheckedAt": "",
        "checkedBackupId": _text(latest.get("id", "")),
        "corruptedCount": len(corrupted),
    }


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "restore_migrated": False,
    }


def _actions(current_user: Any) -> dict[str, Any]:
    can_execute = _can(current_user, "backup.esegui")
    can_read = _can(current_user, "backup.leggi")
    return {
        "canCreate": can_execute,
        "canVerify": can_execute,
        "canDownload": can_read,
        "canRestore": False,
        "createEndpoint": "/api/v1/ui/backup/crea",
        "verifyEndpoint": "/api/v1/ui/backup/verifica",
        "legacyHref": "/backup?_legacy=1",
    }


def build_react_backup_payload(
    *,
    get_backup: Callable[[], Any],
    current_user: Any,
) -> dict[str, Any]:
    manager = get_backup()
    records = [_record(row) for row in manager.tutti()]
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "status": _status(manager, records),
        "backups": records,
        "integrity": _integrity(records),
        "actions": _actions(current_user),
        "warnings": [
            {
                "code": "restore_non_migrato",
                "message": "Il ripristino richiede una procedura protetta di assistenza.",
            },
            {
                "code": "delete_non_migrato",
                "message": "La cancellazione delle copie non e' disponibile da questa scheda.",
            },
        ],
    }


def build_react_backup_error_payload(message: str = "Backup non disponibile.") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "status": {},
        "backups": [],
        "integrity": {"available": False, "state": "error", "label": "Verifica non disponibile"},
        "actions": {
            "canCreate": False,
            "canVerify": False,
            "canDownload": False,
            "canRestore": False,
            "createEndpoint": "/api/v1/ui/backup/crea",
            "verifyEndpoint": "/api/v1/ui/backup/verifica",
            "legacyHref": "/backup?_legacy=1",
        },
        "warnings": [{"code": "backup_errore_controllato", "message": message}],
    }


def _result(
    *,
    ok: bool,
    message: str,
    errors: dict[str, str] | None = None,
    backup: dict[str, Any] | None = None,
    integrity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "message": message,
        "errors": errors or {},
        "backup": backup,
        "integrity": integrity,
    }


def _forbidden_fields(payload: dict[str, Any], allowed: set[str]) -> dict[str, str]:
    unknown = sorted(set(payload) - allowed)
    return {key: "Campo non accettato in questa richiesta." for key in unknown}


def _audit(
    *,
    get_utenti: Callable[[], Any],
    current_user: Any,
    action: str,
    resource_id: str,
    details: str,
    ip: str,
) -> None:
    try:
        get_utenti().registra_evento(
            action,
            id_utente=_text(getattr(current_user, "id", "")),
            username=_text(getattr(current_user, "username", "")),
            risorsa_tipo="backup",
            risorsa_id=resource_id,
            dettagli=details,
            ip=ip,
        )
    except Exception:
        return


def create_react_backup(
    *,
    get_backup: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    payload: dict[str, Any],
    ip: str = "",
) -> dict[str, Any]:
    errors = _forbidden_fields(payload, _CREATE_KEYS)
    if payload.get("confirm") is not True:
        errors["confirm"] = "Conferma esplicitamente la creazione della copia."

    type_raw = _text(payload.get("type") or TipoBackup.COMPLETO.value).upper()
    try:
        backup_type = TipoBackup(type_raw)
    except ValueError:
        backup_type = TipoBackup.COMPLETO
        errors["type"] = "Seleziona un tipo backup valido."

    note = _text(payload.get("note", ""))
    if len(note) > 240:
        errors["note"] = "La nota puo' contenere al massimo 240 caratteri."
    if "<" in note or ">" in note:
        errors["note"] = "La nota non accetta markup."

    manager = get_backup()
    allowed_components = set(_available_components(manager))
    raw_components = payload.get("components", [])
    if raw_components in (None, ""):
        components: list[str] | None = None
    elif isinstance(raw_components, list):
        components = [_text(item) for item in raw_components if _text(item)]
        unknown = sorted(set(components) - allowed_components)
        if unknown:
            errors["components"] = "Alcune parti non sono disponibili per la copia."
    else:
        components = None
        errors["components"] = "Invia una lista di componenti valida."

    if errors:
        return _result(ok=False, message="Controlla i campi evidenziati.", errors=errors)

    record = manager.esegui_backup(tipo=backup_type, componenti=components, nota=note)
    backup_payload = _record(record)
    _audit(
        get_utenti=get_utenti,
        current_user=current_user,
        action="backup.crea",
        resource_id=backup_payload["id"],
        details=f"tipo={backup_payload['type']}; stato={backup_payload['state']}",
        ip=ip,
    )
    if backup_payload["state"] == StatoBackup.OK.value:
        return _result(
            ok=True,
            message="Backup creato correttamente.",
            backup=backup_payload,
            integrity=_integrity([backup_payload]),
        )
    return _result(
        ok=False,
        message="Backup avviato ma concluso con errore.",
        errors={"_form": backup_payload["error"] or "Il backup non e' stato completato."},
        backup=backup_payload,
        integrity=_integrity([backup_payload]),
    )


def verify_react_backup_integrity(
    *,
    get_backup: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    payload: dict[str, Any],
    ip: str = "",
) -> dict[str, Any]:
    errors = _forbidden_fields(payload, _VERIFY_KEYS)
    backup_id = _text(payload.get("backupId", ""))
    if not backup_id:
        errors["backupId"] = "Seleziona una copia backup da verificare."
    if payload.get("confirm") is not True:
        errors["confirm"] = "Conferma esplicitamente la verifica integrita'."
    if errors:
        return _result(ok=False, message="Controlla i campi evidenziati.", errors=errors)

    manager = get_backup()
    record = manager.get(backup_id)
    if record is None:
        return _result(
            ok=False,
            message="Backup non trovato.",
            errors={"backupId": "La copia indicata non esiste nel registro backup."},
        )

    try:
        check = manager.verifica_integrita(backup_id)
    except ValueError:
        return _result(
            ok=False,
            message="Backup non verificabile.",
            errors={"backupId": "La copia indicata non puo' essere verificata."},
        )

    updated = manager.get(backup_id) or record
    backup_payload = _record(updated)
    ok = bool(check.get("ok"))
    integrity = {
        "available": True,
        "state": "ok" if ok else "attention",
        "label": "Backup integro" if ok else "Anomalia rilevata nella verifica",
        "lastCheckedAt": _iso_now(),
        "checkedBackupId": backup_id,
        "corruptedCount": 0 if ok else 1,
    }
    _audit(
        get_utenti=get_utenti,
        current_user=current_user,
        action="backup.verifica",
        resource_id=backup_id,
        details=f"esito={'ok' if ok else 'anomalia'}",
        ip=ip,
    )
    return _result(
        ok=ok,
        message="Verifica completata: backup integro." if ok else "Verifica completata con anomalia.",
        errors={} if ok else {"integrity": "La copia non coincide con il registro di integrita'."},
        backup=backup_payload,
        integrity=integrity,
    )
