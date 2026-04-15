"""Tenant-aware storage runtime helpers."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context

from pct.storage import StudioDB
from pct.tenant import DbMode, normalize_db_mode


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


def _derive_studio_db_path(anchor_path: str) -> str:
    anchor = Path(anchor_path)
    root = anchor.parent.parent if anchor.suffix.lower() == ".json" else anchor.parent
    return str((root / "studio.db").resolve())


def resolve_storage_runtime(*, anchor_path: str, tenant: Any = None) -> StorageRuntimeProfile:
    selected_mode = DbMode.SQLITE
    source = "app"
    tenant_slug = ""

    if tenant is not None:
        tenant_slug = str(getattr(tenant, "slug", "") or "")
        source = "tenant"
        try:
            selected_mode = normalize_db_mode(getattr(tenant, "database").mode)
        except Exception:
            selected_mode = DbMode.SQLITE
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

    cached = getattr(g, "_runtime_studio_db", None) if has_request_context() else None
    if cached is not None and str(cached.db_path) == profile.studio_db_path:
        return cached

    studio_db = StudioDB.get(profile.studio_db_path)
    if has_request_context():
        g._runtime_studio_db = studio_db
    return studio_db
