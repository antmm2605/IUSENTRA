"""Ricostruzione citazioni dal pacchetto di ricerca."""

from __future__ import annotations

from lex.contracts import Citation


class ResearchCitationBuilder:
    def build(self, rows, citations):
        if citations:
            return list(citations)
        rebuilt = []
        for row in list(rows or []):
            rebuilt.append(
                Citation(
                    source_type=str(row.get("source_type") or ""),
                    source_id=str(row.get("source_id") or ""),
                    title=str(row.get("title") or "Fonte"),
                    excerpt=str(row.get("content") or "")[:240],
                    confidence=float(row.get("score") or 0.0),
                    authority=str(row.get("authority") or ""),
                    url=row.get("url"),
                )
            )
        return rebuilt