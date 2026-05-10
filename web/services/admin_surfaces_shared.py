"""Helper condivisi per le superfici amministrative prodotto."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import current_app, g

from pct.agenda import Agenda
from pct.auth import GestioneUtenti
from pct.backup import GestioneBackup
from pct.calendar_sync import GestioneCalendarSync
from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli
from pct.giurisprudenza import GestioneGiurisprudenza
from pct.scadenziario import GestioneScadenziario
from pct.template_atti import GestioneTemplateAtti
from web.services.storage_runtime import get_request_studio_db


def _cfg(key: str) -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if key in paths:
        return str(paths[key] or "")
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    return str(current_app.config.get(key, "") or "")


def _studio_db():
    clienti_db = _cfg("CLIENTI_DB")
    return get_request_studio_db(clienti_db) if clienti_db else None


def load_studio_config() -> dict[str, Any]:
    path_value = _cfg("CONFIG_STUDIO_DB") or _cfg("STUDIO_CONFIG")
    path = Path(path_value)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_auth_manager() -> GestioneUtenti:
    return GestioneUtenti(
        db_path=_cfg("AUTH_DB"),
        audit_path=_cfg("AUDIT_DB"),
        secret_key=current_app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=_studio_db(),
    )


def get_clienti_manager() -> GestioneClienti:
    return GestioneClienti(
        db_path=_cfg("CLIENTI_DB"),
        studio_db=_studio_db(),
    )


def get_fascicoli_manager() -> GestioneFascicoli:
    return GestioneFascicoli(
        db_path=_cfg("FASCICOLI_DB"),
        documents_dir=_cfg("FASCICOLI_DOCS"),
        archive_dir=_cfg("FASCICOLI_ARCH"),
        studio_db=_studio_db(),
    )


def get_agenda_manager() -> Agenda:
    return Agenda(
        db_path=_cfg("AGENDA_DB"),
        studio_db=_studio_db(),
    )


def get_scadenziario_manager() -> GestioneScadenziario:
    return GestioneScadenziario(db_path=_cfg("SCADENZIARIO_DB"))


def get_calendar_sync_manager() -> GestioneCalendarSync:
    return GestioneCalendarSync(db_path=_cfg("CALENDAR_SYNC_DB"))


def get_template_manager() -> GestioneTemplateAtti:
    return GestioneTemplateAtti(db_path=_cfg("TEMPLATE_ATTI_DB"))


def get_giurisprudenza_manager() -> GestioneGiurisprudenza:
    return GestioneGiurisprudenza(_cfg("GIURISPRUDENZA_DB"))


def get_backup_manager() -> GestioneBackup:
    return GestioneBackup(directory_backup=_cfg("BACKUP_DIR"))


def count_documents(fascicoli_manager: GestioneFascicoli) -> int:
    return sum(int(getattr(fascicolo, "documenti_count", 0) or 0) for fascicolo in fascicoli_manager.tutti())


def path_size_bytes(path_value: str) -> int:
    path = Path(str(path_value or ""))
    if not path.exists():
        return 0
    if path.is_file():
        return int(path.stat().st_size)
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += int(child.stat().st_size)
    return total


def storage_mode_label() -> str:
    if bool(current_app.config.get("SQLITE_MODE")):
        return "SQLite"
    return "JSON"
