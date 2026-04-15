"""Snapshot identifier per retrieval Lex."""

from __future__ import annotations


def build_snapshot_id(request, workflow: str) -> str:
    return f"{request.tenant_id}:{request.session_id}:{workflow}"
