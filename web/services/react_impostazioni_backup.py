"""Payload Backup per la pagina React Impostazioni."""

from __future__ import annotations

from typing import Any

from flask import g

from web.services.react_backup_bridge import build_react_backup_payload


def build_backup_settings_payload(get_backup: Any) -> dict[str, Any]:
    """Restituisce dati backup pronti per il tab Impostazioni."""

    user = g.get("utente_corrente")
    try:
        payload = build_react_backup_payload(get_backup=get_backup, current_user=user)
    except Exception:
        return {
            "ok": False,
            "status": {},
            "backups": [],
            "integrity": {"available": False, "state": "error", "label": "Backup non disponibile"},
            "actions": {"canCreate": False, "canVerify": False, "canDownload": False},
            "warnings": [{"message": "Backup non disponibile in questo momento."}],
        }
    return {
        "ok": bool(payload.get("ok")),
        "status": payload.get("status") or {},
        "backups": payload.get("backups") or [],
        "integrity": payload.get("integrity") or {},
        "actions": payload.get("actions") or {},
        "warnings": [],
    }
