"""Mirror SQL/PostgreSQL governato per la sezione Impostazioni."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pct.config_studio import (
    CONFIG_STUDIO_SECRET_FIELDS,
    ConfigStudio,
    config_studio_to_storage_dict,
)


SETTINGS_CONFIG_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings_config (
    section TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'config_studio',
    secret_fields_json TEXT NOT NULL DEFAULT '[]',
    dati_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_settings_config_updated ON settings_config(updated_at);
"""

SETTINGS_CONFIG_POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings_config (
    section TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'config_studio',
    secret_fields_json TEXT NOT NULL DEFAULT '[]',
    dati_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_settings_config_updated ON settings_config(updated_at);
"""

CONFIG_STUDIO_SECTIONS: tuple[str, ...] = (
    "studio",
    "pec",
    "firma",
    "smtp",
    "whatsapp",
    "scheduler",
    "ai",
    "sdi",
    "fatturazione",
    "support_remote",
)

VISIBLE_SETTINGS_SECTIONS: tuple[str, ...] = (
    "studio",
    "pec",
    "firma",
    "smtp",
    "whatsapp",
    "scheduler",
    "ai",
    "sdi",
    "fatturazione",
    "pagamenti",
    "notifiche",
    "backup",
    "calendari",
)

SPECIALIZED_SECTION_STORAGE: dict[str, str] = {
    "pagamenti": "payment_config, payment_links",
    "notifiche": "config_studio.whatsapp, config_studio.scheduler, notifiche_log",
    "backup": "backup_config, backup_records",
    "calendari": "calendar_sync repository",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _secret_fields_by_section() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for section, field_name in CONFIG_STUDIO_SECRET_FIELDS:
        grouped.setdefault(section, []).append(field_name)
    return grouped


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(item) for item in value]
        return str(value)


def settings_config_rows_from_config(
    cfg: ConfigStudio,
    *,
    extra_sections: dict[str, Any] | None = None,
    updated_at: str | None = None,
) -> list[dict[str, Any]]:
    """Costruisce le righe da salvare nella tabella `settings_config`."""
    stored = config_studio_to_storage_dict(cfg)
    secrets = _secret_fields_by_section()
    timestamp = updated_at or _iso_now()
    rows: list[dict[str, Any]] = []

    for section in CONFIG_STUDIO_SECTIONS:
        rows.append(
            {
                "section": section,
                "updated_at": timestamp,
                "source": "config_studio",
                "secret_fields": secrets.get(section, []),
                "dati": stored.get(section, {}),
            }
        )

    for section, payload in (extra_sections or {}).items():
        normalized = str(section or "").strip().lower()
        if not normalized or normalized in CONFIG_STUDIO_SECTIONS:
            continue
        rows.append(
            {
                "section": normalized,
                "updated_at": timestamp,
                "source": SPECIALIZED_SECTION_STORAGE.get(normalized, "react_impostazioni"),
                "secret_fields": [],
                "dati": _json_safe(payload),
            }
        )

    present = {row["section"] for row in rows}
    manifest = {
        "visible_sections": list(VISIBLE_SETTINGS_SECTIONS),
        "config_studio_sections": list(CONFIG_STUDIO_SECTIONS),
        "specialized_storage": SPECIALIZED_SECTION_STORAGE,
        "missing_visible_sections": [
            section for section in VISIBLE_SETTINGS_SECTIONS if section not in present
        ],
    }
    rows.append(
        {
            "section": "_manifest",
            "updated_at": timestamp,
            "source": "settings_config_repository",
            "secret_fields": [],
            "dati": manifest,
        }
    )
    return rows


def ensure_settings_config_schema(studio_db: Any) -> None:
    """Applica lo schema al backend corrente, se espone una connessione SQL."""
    conn = getattr(studio_db, "conn", None)
    if conn is None:
        return
    script = (
        SETTINGS_CONFIG_POSTGRES_SCHEMA
        if str(getattr(studio_db, "backend_kind", "")).lower() == "postgresql"
        else SETTINGS_CONFIG_SQLITE_SCHEMA
    )
    if hasattr(conn, "executescript"):
        conn.executescript(script)
    else:
        for statement in script.split(";"):
            sql = statement.strip()
            if sql:
                conn.execute(sql)
    try:
        conn.commit()
    except Exception:
        pass


def load_settings_config_section(studio_db: Any, section: str) -> dict[str, Any]:
    """Legge una sezione dal backend SQL tenant, fonte operativa delle impostazioni."""

    if studio_db is None:
        return {}
    normalized = str(section or "").strip().lower()
    if not normalized:
        return {}
    ensure_settings_config_schema(studio_db)
    conn = getattr(studio_db, "conn", None)
    if conn is None:
        return {}
    try:
        row = conn.execute(
            "SELECT dati_json FROM settings_config WHERE section = ?",
            (normalized,),
        ).fetchone()
    except Exception:
        return {}
    if not row:
        return {}
    try:
        raw = row["dati_json"]
    except (KeyError, TypeError):
        raw = row[0]
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def save_settings_config_snapshot(
    studio_db: Any,
    cfg: ConfigStudio,
    *,
    extra_sections: dict[str, Any] | None = None,
    updated_at: str | None = None,
) -> int:
    """
    Salva lo snapshot Impostazioni nel backend strutturato corrente.

    Ritorna il numero di righe scritte. Il chiamante decide se loggare eventuali
    errori: il salvataggio JSON canonico resta separato e non viene perso.
    """
    if studio_db is None:
        return 0

    rows = settings_config_rows_from_config(
        cfg,
        extra_sections=extra_sections,
        updated_at=updated_at,
    )
    ensure_settings_config_schema(studio_db)

    def _insert(conn: Any, row: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO settings_config
            (section, updated_at, source, secret_fields_json, dati_json)
            VALUES (?,?,?,?,?)
            """,
            (
                row["section"],
                row["updated_at"],
                row["source"],
                _json(row.get("secret_fields") or []),
                _json(row.get("dati") or {}),
            ),
        )

    studio_db.salva_tabella("settings_config", rows, _insert)
    return len(rows)
