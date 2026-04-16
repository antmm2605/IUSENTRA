"""Tenant-aware storage runtime helpers."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context

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


def _sqlite_runtime_is_unseeded(studio_db_path: Path) -> bool:
    if not studio_db_path.exists():
        return True
    try:
        conn = sqlite3.connect(str(studio_db_path))
        try:
            tables = ("clienti", "fascicoli", "appuntamenti", "scadenze", "utenti")
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


def resolve_storage_runtime(*, anchor_path: str, tenant: Any = None) -> StorageRuntimeProfile:
    selected_mode = resolve_default_storage_mode()
    source = "app"
    tenant_slug = ""

    if tenant is not None:
        tenant_slug = str(getattr(tenant, "slug", "") or "")
        source = "tenant"
        try:
            selected_mode = normalize_db_mode(getattr(tenant, "database").mode)
        except Exception:
            selected_mode = DbMode.SQLITE
    elif has_app_context() and current_app.config.get("STORAGE_MODE_DEFAULT"):
        source = "app-default"
    elif has_app_context() and current_app.config.get("SQLITE_MODE"):
        selected_mode = DbMode.SQLITE
        source = "legacy-global"
    else:
        source = "default-operational"

    studio_db_path = _derive_studio_db_path(anchor_path)
    uses_sqlite = selected_mode == DbMode.SQLITE
    external_sql_configured = selected_mode in (DbMode.POSTGRESQL, DbMode.MYSQL)
    effective_mode = DbMode.SQLITE if uses_sqlite else DbMode.JSON

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

    cached = getattr(g, "_storage_runtime_profile", None)
    if cached and cached.data_anchor_path == str(Path(anchor_path).resolve()):
        return cached

    tenant = getattr(g, "tenant", None)
    profile = resolve_storage_runtime(anchor_path=anchor_path, tenant=tenant)
    g._storage_runtime_profile = profile
    return profile


def get_request_studio_db(anchor_path: str):
    profile = get_request_storage_runtime(anchor_path)
    if not profile.uses_sqlite:
        return None

    anchor = Path(profile.data_anchor_path)
    studio_db_path = Path(profile.studio_db_path)
    if _json_anchor_has_legacy_data(anchor) and _sqlite_runtime_is_unseeded(studio_db_path):
        fallback_profile = replace(
            profile,
            effective_mode=DbMode.JSON,
            uses_sqlite=False,
            source=f"{profile.source}-json-legacy",
        )
        if has_request_context():
            g._storage_runtime_profile = fallback_profile
        if has_app_context():
            current_app.logger.info(
                "SQLite operativo non ancora popolato per %s: mantengo i dati legacy JSON come sorgente attiva.",
                profile.data_anchor_path,
            )
        return None

    cached = getattr(g, "_runtime_studio_db", None) if has_request_context() else None
    if cached is not None and str(cached.db_path) == profile.studio_db_path:
        return cached

    try:
        studio_db = StudioDB.get(profile.studio_db_path)
    except (OSError, sqlite3.Error) as exc:
        fallback_profile = replace(
            profile,
            effective_mode=DbMode.JSON,
            uses_sqlite=False,
            source=f"{profile.source}-sqlite-unavailable",
        )
        if has_request_context():
            g._storage_runtime_profile = fallback_profile
        if has_app_context():
            current_app.logger.warning(
                "SQLite non disponibile per %s: fallback JSON attivato (%s)",
                profile.studio_db_path,
                exc,
            )
        return None

    if has_request_context():
        g._runtime_studio_db = studio_db
    return studio_db
