"""Factory governabile per il backend core tenant-aware.

Questo modulo centralizza la scelta del backend usato dai repository core
(``utenti``, ``clienti``, ``fascicoli``, ``agenda``, ``scadenziario``)
evitando branch duplicati tra runtime Flask, admin e migrazioni.
"""

from __future__ import annotations

from typing import Any

from pct.storage import StudioDB
from pct.storage_postgres import PostgresStudioDB, build_postgres_dsn


def _mode_value(config: Any) -> str:
    normalized = getattr(config, "normalized_mode", None)
    if normalized:
        return str(normalized or "").strip().upper()
    return str(getattr(config, "mode", "") or "").strip().upper()


def is_postgres_core_active(config: Any) -> bool:
    return (
        _mode_value(config) == "POSTGRESQL"
        and bool(getattr(config, "connessione_ok", False))
        and bool(getattr(config, "core_runtime_enabled", False))
    )


def build_postgres_backend(config: Any) -> PostgresStudioDB | None:
    if _mode_value(config) != "POSTGRESQL":
        return None

    host = str(getattr(config, "host", "") or "").strip()
    db_name = str(getattr(config, "db_name", "") or "").strip()
    user = str(getattr(config, "utente", "") or "").strip()
    password = str(getattr(config, "password", "") or "")
    port = int(getattr(config, "porta_effettiva", 0) or 0)
    ssl = bool(getattr(config, "ssl", False))
    if not all((host, db_name, user)):
        return None

    dsn = build_postgres_dsn(
        host=host,
        port=port or 5432,
        db_name=db_name,
        user=user,
        password=password,
        ssl=ssl,
    )
    return PostgresStudioDB.get(dsn)


def build_core_storage_backend(config: Any, *, studio_db_path: str):
    mode = _mode_value(config)
    if mode == "SQLITE":
        return StudioDB.get(studio_db_path)
    if is_postgres_core_active(config):
        return build_postgres_backend(config)
    return None
