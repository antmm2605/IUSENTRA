"""Memoria di pratica per Lex."""

from __future__ import annotations

from typing import Any


def build_practice_memory(pratica_id: str, context_sections: dict[str, Any]) -> dict[str, Any]:
    return {
        "pratica_id": str(pratica_id or "").strip(),
        "sections": dict(context_sections or {}),
    }
