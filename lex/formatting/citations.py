"""Gestione citazioni per le risposte di Lex."""

from __future__ import annotations

from typing import Any


def build_citations(sources: list[dict[str, Any]] | None) -> list[str]:
    citations: list[str] = []
    for source in list(sources or []):
        citation = " ".join(str(source.get("citation") or "").split()).strip()
        if citation:
            citations.append(citation)
    return citations
