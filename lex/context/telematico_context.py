"""Contesto telematico minimo per i workflow Lex."""

from __future__ import annotations


def build_telematico_context(request) -> dict[str, str]:
    return {
        "workflow_hint": request.workflow_hint or "",
        "document_id": request.document_id or "",
    }
