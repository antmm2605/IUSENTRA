"""Tenant-aware storage runtime helpers."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass, replace
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
        return DbMode.JSON, False, "tenant-postgresql-not-activated"
    if selected_mode == DbMode.MYSQL:
        return DbMode.JSON, False, "tenant-mysql-not-supported"
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
    if _json_anchor_has_legacy_data(anchor) and _sqlite_runtime_is_unseeded(studio_db_path, anchor):
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
    if cached is not None and str(getattr(cached, "db_path", "")) == profile.studio_db_path:
        return cached

    try:
        studio_db = ensure_core_storage_backend_contract(StudioDB.get(profile.studio_db_path))
    except (OSError, sqlite3.Error, TypeError) as exc:
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
