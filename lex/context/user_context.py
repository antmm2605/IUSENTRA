"""Contesto utente per i workflow applicativi Lex."""

from __future__ import annotations


def build_user_context(request) -> dict[str, str]:
    return {"user_id": request.user_id}
