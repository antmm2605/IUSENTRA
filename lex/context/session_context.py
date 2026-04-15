"""Contesto sessione per il bounded context Lex."""

from __future__ import annotations


def build_session_context(request) -> dict[str, str]:
    return {"session_id": request.session_id}
