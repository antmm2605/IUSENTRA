from __future__ import annotations

from statistics import mean
from typing import Any

from lex.contracts import EvidencePack
from .official_sources import OfficialSourcesCatalog


def _to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    metadata = dict(getattr(item, "metadata", {}) or {})
    return {
        "title": getattr(item, "title", ""),
        "source_type": getattr(item, "source_type", ""),
        "source_id": getattr(item, "source_id", ""),
        "score": getattr(item, "score", 0.0),
        "trust_class": getattr(item, "trust_class", "") or metadata.get("trust_class") or "",
        "source_level": getattr(item, "source_level", 0) or metadata.get("source_level") or 0,
        "trust_score": getattr(item, "trust_score", 0.0),
        "freshness_score": getattr(item, "freshness_score", 0.0),
        "context_fit_score": getattr(item, "context_fit_score", 0.0),
        "consensus_score": getattr(item, "consensus_score", 0.0),
        "authority": getattr(item, "authority", "") or metadata.get("authority") or "",
        "official_url": getattr(item, "official_url", None) or metadata.get("official_url") or metadata.get("url"),
        "published_at": getattr(item, "published_at", None) or metadata.get("published_at"),
        "verified_reference": getattr(item, "verified_reference", False) or metadata.get("verified_reference") or False,
        "metadata": metadata,
    }


class EvidencePackBuilder:
    def __init__(self, *, official_catalog: OfficialSourcesCatalog | None = None) -> None:
        self.official_catalog = official_catalog or OfficialSourcesCatalog()

    def build(self, *, queries, items, citations, official_sources, trusted_sources, freshness, metadata=None):
        rows = [self.official_catalog.enrich(_to_dict(item)) for item in list(items or [])]
        compared_sources = [
            {
                "title": str(row.get("title") or row.get("source_id") or "Fonte"),
                "authority": str(row.get("authority") or ""),
                "trust_class": str(row.get("trust_class") or ""),
                "source_level": int(row.get("source_level") or 0),
                "score": float(row.get("score") or 0.0),
                "trust_score": float(row.get("trust_score") or 0.0),
                "freshness_score": float(row.get("freshness_score") or 0.0),
                "context_fit_score": float(row.get("context_fit_score") or 0.0),
                "consensus_score": float(row.get("consensus_score") or 0.0),
                "published_at": row.get("published_at"),
                "official_url": row.get("official_url") or row.get("url"),
            }
            for row in rows
        ]
        official = list(official_sources or []) or self.official_catalog.extract(rows, citations)
        trusted = list(trusted_sources or [])
        if not trusted:
            trusted = [row["title"] for row in compared_sources if row["trust_class"] in {"A", "B"}][:12]

        trust_values = [float(row.get("trust_score") or 0.0) for row in compared_sources]
        fresh_values = [float(row.get("freshness_score") or 0.0) for row in compared_sources]
        context_values = [float(row.get("context_fit_score") or 0.0) for row in compared_sources]
        consensus_values = [float(row.get("consensus_score") or 0.0) for row in compared_sources]

        conflicting_items: list[str] = []
        grouped: dict[str, set[str]] = {}
        for row in compared_sources:
            key = str(row.get("authority") or row.get("title") or "fonte")
            grouped.setdefault(key, set()).add(str(row.get("published_at") or ""))
        for key, values in grouped.items():
            non_empty = {value for value in values if value}
            if len(non_empty) > 1:
                conflicting_items.append(key)

        coverage_gaps: list[str] = []
        if not rows:
            coverage_gaps.append("Nessuna evidenza disponibile.")
        if not official:
            coverage_gaps.append("Mancano fonti ufficiali tra le evidenze selezionate.")
        if len(compared_sources) < 2:
            coverage_gaps.append("Confronto fonti limitato: meno di due fonti rilevanti.")
        if not any(row["trust_class"] == "A" for row in compared_sources):
            coverage_gaps.append("Nessuna fonte primaria di trust class A rilevata.")

        sufficient = bool(rows) and not ("Mancano fonti ufficiali tra le evidenze selezionate." in coverage_gaps and len(rows) < 3)
        needs_human_review = bool(conflicting_items) or not sufficient

        pack_metadata = dict(metadata or {})
        pack_metadata.update(
            {
                "source_count": len(rows),
                "official_count": len(official),
                "trusted_count": len(trusted),
            }
        )

        return EvidencePack(
            queries=list(queries or []),
            items=list(items or []),
            citations=list(citations or []),
            official_sources=official,
            trusted_sources=trusted,
            freshness=dict(freshness or {}),
            metadata=pack_metadata,
            aggregate_trust_score=round(mean(trust_values), 4) if trust_values else 0.0,
            aggregate_freshness_score=round(mean(fresh_values), 4) if fresh_values else 0.0,
            aggregate_context_fit_score=round(mean(context_values), 4) if context_values else 0.0,
            aggregate_consensus_score=round(mean(consensus_values), 4) if consensus_values else 0.0,
            compared_sources=compared_sources,
            conflicting_items=conflicting_items,
            coverage_gaps=coverage_gaps,
            needs_human_review=needs_human_review,
            sufficient=sufficient,
        )
