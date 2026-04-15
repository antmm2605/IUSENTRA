"""Index key memoria del bounded context Lex."""

from __future__ import annotations


def memory_index_key(tenant_id: str, scope: str, obj_id: str) -> str:
    return f"{tenant_id}:{scope}:{obj_id}"
