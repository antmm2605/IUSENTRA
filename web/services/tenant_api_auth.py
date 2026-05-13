"""Tenant-aware API key authentication helpers."""

from __future__ import annotations

from dataclasses import dataclass
import secrets
from typing import Any

from flask import current_app, g, has_app_context, has_request_context, request

from pct.tenant import GestioneTenant, StatoTenant, StudioLegale


ACTIVE_TENANT_STATES = {StatoTenant.ATTIVO, StatoTenant.TRIAL}


@dataclass(frozen=True)
class TenantApiAuthContext:
    valid: bool
    tenant_slug: str = ""
    studio: StudioLegale | None = None
    reason: str = ""
    status_code: int = 401


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _multi_tenant_enabled() -> bool:
    if not has_app_context():
        return False
    return bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False))


def _request_api_key() -> str:
    if not has_request_context():
        return ""
    return _text(request.headers.get("X-API-Key"))


def _global_api_key() -> str:
    if not has_app_context():
        return ""
    return _text(current_app.config.get("API_KEY"))


def _safe_equals(left: str, right: str) -> bool:
    if not left or not right:
        return False
    try:
        return secrets.compare_digest(left, right)
    except TypeError:
        return False


def resolve_api_tenant_slug_from_headers() -> str:
    """Return the explicit tenant slug requested by API headers, if coherent."""

    if not has_request_context():
        return ""
    tenant_slug = _text(request.headers.get("X-Tenant-Slug")).lower()
    studio_slug = _text(request.headers.get("X-Studio-Slug")).lower()
    if tenant_slug and studio_slug and tenant_slug != studio_slug:
        return ""
    return tenant_slug or studio_slug


def _load_tenant_manager() -> GestioneTenant | None:
    registry = _text(current_app.config.get("TENANTS_REGISTRY")) if has_app_context() else ""
    if not registry:
        return None
    try:
        return GestioneTenant(registry_path=registry)
    except Exception as exc:  # pragma: no cover - defensive logging path
        current_app.logger.warning("Validazione API tenant non disponibile: registry non leggibile (%s)", exc)
        return None


def resolve_api_tenant_context_from_headers() -> TenantApiAuthContext:
    """Validate the request API key and tenant headers without exposing secrets."""

    if not has_request_context() or not has_app_context():
        return TenantApiAuthContext(False, reason="request_context_missing")

    cached = getattr(g, "_tenant_api_auth_context", None)
    if isinstance(cached, TenantApiAuthContext):
        return cached

    api_key = _request_api_key()
    if not api_key:
        context = TenantApiAuthContext(False, reason="api_key_missing")
        g._tenant_api_auth_context = context
        return context

    if not _multi_tenant_enabled():
        context = TenantApiAuthContext(
            _safe_equals(api_key, _global_api_key()),
            reason="" if _safe_equals(api_key, _global_api_key()) else "api_key_invalid",
        )
        g._tenant_api_auth_context = context
        return context

    tenant_slug = resolve_api_tenant_slug_from_headers()
    global_key = _global_api_key()
    if global_key and _safe_equals(api_key, global_key):
        reason = "global_api_key_not_allowed" if tenant_slug else "tenant_context_required"
        status_code = 403 if tenant_slug else 409
        context = TenantApiAuthContext(False, tenant_slug=tenant_slug, reason=reason, status_code=status_code)
        g._tenant_api_auth_context = context
        return context

    if not tenant_slug:
        context = TenantApiAuthContext(False, reason="tenant_slug_missing_or_mismatch", status_code=409)
        g._tenant_api_auth_context = context
        return context

    manager = _load_tenant_manager()
    if manager is None:
        context = TenantApiAuthContext(False, tenant_slug=tenant_slug, reason="tenant_registry_unavailable", status_code=409)
        g._tenant_api_auth_context = context
        return context

    studio = manager.get(tenant_slug)
    if studio is None:
        context = TenantApiAuthContext(False, tenant_slug=tenant_slug, reason="tenant_not_found", status_code=403)
        g._tenant_api_auth_context = context
        return context

    stato = _text(getattr(studio, "stato", "")).upper()
    if stato not in ACTIVE_TENANT_STATES:
        context = TenantApiAuthContext(False, tenant_slug=tenant_slug, reason="tenant_not_active", status_code=403)
        g._tenant_api_auth_context = context
        return context

    if not _safe_equals(api_key, _text(getattr(studio, "api_key", ""))):
        context = TenantApiAuthContext(False, tenant_slug=tenant_slug, reason="tenant_api_key_invalid", status_code=403)
        g._tenant_api_auth_context = context
        return context

    context = TenantApiAuthContext(True, tenant_slug=tenant_slug, studio=studio)
    g._tenant_api_auth_context = context
    return context


def attach_api_tenant_context_from_headers() -> TenantApiAuthContext:
    """Attach g.tenant and g.data_paths for a validated tenant API request."""

    context = resolve_api_tenant_context_from_headers()
    if not context.valid or not _multi_tenant_enabled():
        return context

    manager = _load_tenant_manager()
    if manager is None:
        return TenantApiAuthContext(False, tenant_slug=context.tenant_slug, reason="tenant_registry_unavailable", status_code=409)

    paths = manager.percorsi_dati(context.tenant_slug, reconcile_aliases=False)
    g.tenant = context.studio or manager.get(context.tenant_slug)
    g.data_paths = paths
    g.tenant_context_required = True
    g.tenant_context_missing = False
    g.tenant_context_slug = context.tenant_slug
    g.api_tenant_authenticated = True
    g.api_tenant_slug = context.tenant_slug
    try:
        from web.services.storage_runtime import get_request_storage_runtime

        g.storage_runtime = get_request_storage_runtime(paths["CLIENTI_DB"]).to_dict()
    except Exception:
        g.storage_runtime = None
    return context


def api_key_valid_for_request() -> bool:
    """Return True when the request is authorized by a valid API key."""

    context = attach_api_tenant_context_from_headers()
    return bool(context.valid)


__all__ = [
    "TenantApiAuthContext",
    "api_key_valid_for_request",
    "attach_api_tenant_context_from_headers",
    "resolve_api_tenant_context_from_headers",
    "resolve_api_tenant_slug_from_headers",
]
