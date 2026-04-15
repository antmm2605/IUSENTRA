"""Bridge di contesto studio posseduti dal package Lex."""

from __future__ import annotations

from typing import Any

from web.services.assistente_studio_context import (
    build_lex_studio_context as _build_lex_studio_context,
    warm_lex_studio_context as _warm_lex_studio_context,
)


def build_lex_studio_context(*args, **kwargs) -> dict[str, Any]:
    """Espone il builder storico sotto ownership lessicale di ``lex/``."""

    return dict(_build_lex_studio_context(*args, **kwargs) or {})


def warm_lex_studio_context(*args, **kwargs) -> dict[str, Any]:
    """Pre-riscalda il contesto studio per i flussi Lex."""

    return dict(_warm_lex_studio_context(*args, **kwargs) or {})


def build_studio_context(request) -> dict[str, Any]:
    return {
        "tenant_id": request.tenant_id,
        "workflow_hint": request.workflow_hint or "",
    }
