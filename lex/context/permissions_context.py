"""Permessi applicativi minimi per il bounded context Lex."""

from __future__ import annotations


def build_permissions_context(request) -> dict[str, bool]:
    return {"can_use_lex": bool(request.tenant_id and request.user_id)}
