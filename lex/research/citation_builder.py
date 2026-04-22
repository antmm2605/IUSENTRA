"""Ricostruzione citazioni dal pacchetto di ricerca."""

from __future__ import annotations

from lex.contracts import Citation


class ResearchCitationBuilder:
    def build(self, rows, citations):
        if citations:
            return list(citations)
        rebuilt = []
        for row in list(rows or []):
            metadata = dict(row.get("metadata") or {})
            rebuilt.append(
                Citation(
                    source_type=str(row.get("source_type") or ""),
                    source_id=str(row.get("source_id") or ""),
                    title=str(row.get("title") or "Fonte"),
                    excerpt=str(row.get("content") or "")[:240],
                    confidence=float(row.get("score") or 0.0),
                    authority=str(row.get("authority") or metadata.get("authority") or ""),
                    url=row.get("official_url") or row.get("url") or metadata.get("official_url") or metadata.get("url"),
                    trust_class=str(row.get("trust_class") or metadata.get("trust_class") or ""),
                    source_level=int(row.get("source_level") or metadata.get("source_level") or 0),
                    verified_reference=bool(row.get("verified_reference") or metadata.get("verified_reference")),
                    published_at=row.get("published_at") or metadata.get("published_at"),
                    freshness_score=float(row.get("freshness_score") or metadata.get("freshness_score") or 0.0),
                )
            )
        return rebuilt
