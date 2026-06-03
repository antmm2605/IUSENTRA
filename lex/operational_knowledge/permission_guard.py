"""Tenant, RBAC and privacy guard for Lex operational knowledge."""

from __future__ import annotations

from typing import Any

from .models import OperationalQueryContext, OperationalSourceDefinition, PermissionDecision


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _user_id(user: Any) -> str:
    for key in ("id", "username", "email", "nome_utente"):
        value = _clean(getattr(user, key, ""))
        if value:
            return value
    if isinstance(user, dict):
        for key in ("id", "username", "email"):
            value = _clean(user.get(key))
            if value:
                return value
    return ""


def _username(user: Any) -> str:
    for key in ("username", "email", "nome_completo", "id"):
        value = _clean(getattr(user, key, ""))
        if value:
            return value
    if isinstance(user, dict):
        for key in ("username", "email", "nome_completo", "id"):
            value = _clean(user.get(key))
            if value:
                return value
    return ""


def resolve_query_context(
    *,
    user: Any = None,
    studio: Any = None,
    tenant_id: str = "",
    permissions: set[str] | None = None,
) -> OperationalQueryContext:
    """Resolve the current operational context.

    In Flask requests, tenant and user are read from ``g``. In tests or
    background code, callers can pass them explicitly.
    """

    flask_source = False
    multi_tenant = False
    tenant_context_available = True
    try:
        from flask import current_app, g, has_app_context, has_request_context

        if has_app_context():
            multi_tenant = bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False))
        if has_request_context():
            flask_source = True
            user = user or g.get("utente_corrente")
            tenant = getattr(g, "tenant", None)
            tenant_id = (
                _clean(tenant_id)
                or _clean(getattr(tenant, "slug", ""))
                or _clean(getattr(tenant, "id", ""))
                or _clean(getattr(g, "tenant_context_slug", ""))
            )
            tenant_context_available = not bool(getattr(g, "tenant_context_missing", False))
    except Exception:
        pass

    tenant_id = (
        _clean(tenant_id)
        or _clean(getattr(studio, "slug", ""))
        or _clean(getattr(studio, "id", ""))
        or _clean(getattr(studio, "tenant_slug", ""))
    )

    user_permissions = set(permissions or set())
    effective = getattr(user, "permessi_effettivi", None)
    if effective:
        try:
            user_permissions.update(str(item) for item in list(effective or []))
        except Exception:
            pass

    return OperationalQueryContext(
        tenant_id=tenant_id,
        user_id=_user_id(user),
        username=_username(user),
        user=user,
        permissions=user_permissions,
        multi_tenant=multi_tenant,
        tenant_context_available=tenant_context_available,
        source="flask" if flask_source else "explicit",
    )


class OperationalPermissionGuard:
    """Centralized fail-closed guard before every operational retrieval."""

    def check_source(self, context: OperationalQueryContext, source: OperationalSourceDefinition) -> PermissionDecision:
        if not context.user_id or context.user is None:
            return PermissionDecision(False, source.source_id, reason="authentication_required")

        if context.multi_tenant and (not context.tenant_id or not context.tenant_context_available):
            return PermissionDecision(False, source.source_id, reason="tenant_context_required")

        user_tenant = _clean(getattr(context.user, "tenant_slug", "")).lower()
        if context.multi_tenant and user_tenant and context.tenant_id and user_tenant != context.tenant_id.lower():
            return PermissionDecision(False, source.source_id, reason="tenant_mismatch")

        missing = []
        if not context.has_permission("ai.usa"):
            missing.append("ai.usa")
        for permission in source.required_permissions:
            if permission and not context.has_permission(permission):
                missing.append(permission)
        if missing:
            return PermissionDecision(
                False,
                source.source_id,
                reason="missing_permission",
                missing_permissions=sorted(set(missing)),
            )

        warnings = []
        if source.sensitive:
            warnings.append("Accesso limitato ai dati del tenant corrente e ai permessi dell'utente.")
        return PermissionDecision(True, source.source_id, warnings=warnings)

    def record_belongs_to_tenant(self, context: OperationalQueryContext, record: Any) -> bool:
        """Return False only when a record explicitly declares another tenant."""

        if not context.tenant_id:
            return True
        if isinstance(record, dict):
            raw_tenant = record.get("tenant_id") or record.get("tenant_slug")
        else:
            raw_tenant = (
                getattr(record, "tenant_id", "")
                or getattr(record, "tenant_slug", "")
            )
        value = _clean(raw_tenant)
        if not value:
            return True
        return value.lower() == context.tenant_id.lower()
