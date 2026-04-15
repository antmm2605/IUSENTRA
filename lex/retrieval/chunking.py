"""Chunking testuale minimo per il retrieval Lex."""

from __future__ import annotations


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    safe = str(text or "")
    return [safe[index : index + max_chars] for index in range(0, len(safe), max_chars)] or [""]
