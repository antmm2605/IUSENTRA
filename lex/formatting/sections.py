"""Blocchi di sezione per la UI di Lex."""

from __future__ import annotations

from typing import Any


def build_sections(answer: str, warnings: list[str] | None, actions: list[dict[str, Any]] | None) -> dict[str, Any]:
    return {
        "answer": str(answer or "").strip(),
        "warnings": list(warnings or []),
        "actions": list(actions or []),
    }
