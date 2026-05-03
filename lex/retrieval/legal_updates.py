"""Retrieval SQL degli aggiornamenti legali per Lex."""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - il modulo resta importabile anche fuori Flask
    from flask import g, has_app_context, has_request_context
except Exception:  # pragma: no cover
    g = None  # type: ignore[assignment]

    def has_app_context() -> bool:
        return False

    def has_request_context() -> bool:
        return False


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _tenant_slug_from_request(request: Any = None) -> str:
    metadata = dict(getattr(request, "metadata", {}) or {})
    for key in ("tenant_slug", "studio_slug", "tenant"):
        value = _clean_spaces(metadata.get(key)).lower()
        if value:
            return value
    if has_request_context() and g is not None:
        tenant = getattr(g, "tenant", None)
        value = _clean_spaces(getattr(tenant, "slug", "")).lower()
        if value:
            return value
    return ""


def search_legal_update_sources(message: str, *, request: Any = None, limit: int = 10) -> list[dict[str, Any]]:
    if not has_app_context():
        return []
    try:
        from web.services.legal_update_surface import build_legal_update_pipeline_runtime

        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_tenant_slug_from_request(request))
        return pipeline.repository.search_lex_sources(message, limit=limit)
    except Exception:
        return []
