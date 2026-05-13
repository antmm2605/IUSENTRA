"""Guardrail condivisi per percorsi dati tenant-aware."""

from __future__ import annotations

from typing import Any

from flask import current_app, g, has_app_context


CROSS_STUDIO_DATA_MESSAGE = (
    "Contesto studio non disponibile per la richiesta corrente. "
    "Accesso ai dati bloccato per evitare letture cross-studio."
)


class TenantDataPathError(RuntimeError):
    """Raised when a sensitive repository would fall back outside a tenant."""


def _multi_tenant_enabled() -> bool:
    if not has_app_context():
        return False
    return bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False))


def tenant_data_path(key: str, default: str = "", *aliases: str, require_tenant: bool = False) -> str:
    """Return a runtime path without falling back to global storage for sensitive tenant data."""

    candidates = (key, *aliases)
    paths: dict[str, Any] = {}
    if has_app_context():
        paths = getattr(g, "data_paths", {}) or {}

    for candidate in candidates:
        value = paths.get(candidate)
        if value:
            if _multi_tenant_enabled():
                from web.services.tenant_isolation_runtime import assert_tenant_data_path

                return assert_tenant_data_path(str(value), key=candidate)
            return str(value)

    if has_app_context():
        if getattr(g, "tenant_context_missing", False) or (require_tenant and _multi_tenant_enabled()):
            raise TenantDataPathError(CROSS_STUDIO_DATA_MESSAGE)
        for candidate in candidates:
            value = current_app.config.get(candidate)
            if value:
                return str(value)

    return str(default or "")
