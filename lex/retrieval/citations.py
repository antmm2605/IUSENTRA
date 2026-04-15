"""Conversione evidenze -> citazioni Lex."""

from __future__ import annotations

from lex.contracts import Citation


def build_citations(items):
    citations: list[Citation] = []
    for item in list(items or []):
        citations.append(
            Citation(
                source_type=item.source_type,
                source_id=item.source_id,
                title=item.title,
                excerpt=item.content[:240],
                confidence=float(item.score),
                authority=str(item.metadata.get("authority") or ""),
                url=item.metadata.get("url"),
            )
        )
    return citations
