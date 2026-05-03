from __future__ import annotations

from statistics import mean
from typing import Any

from lex.contracts import EvidencePack
from .official_sources import OfficialSourcesCatalog

_STRICT_SOURCE_WORKFLOWS = {"normativa", "giurisprudenza", "prassi", "research", "fonti"}


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
        "source_registry_key": metadata.get("source_registry_key") or "",
        "source_access_status": metadata.get("source_access_status") or "",
        "source_access_label": metadata.get("source_access_label") or "",
        "source_category": metadata.get("source_category") or "",
        "source_priority": metadata.get("source_priority") or "",
        "source_requires_credentials": bool(metadata.get("source_requires_credentials")),
        "source_restricted": bool(metadata.get("source_restricted")),
        "source_supports_web_search": bool(metadata.get("source_supports_web_search", False)),
        "document_id": metadata.get("document_id") or "",
        "parser": metadata.get("parser") or "",
        "parser_version": metadata.get("parser_version") or "",
        "source_hash": metadata.get("source_hash") or "",
        "page_no": metadata.get("page_no"),
        "section_path": metadata.get("section_path") or "",
        "chunk_index": metadata.get("chunk_index"),
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
                "source_registry_key": str(row.get("source_registry_key") or ""),
                "source_access_status": str(row.get("source_access_status") or ""),
                "source_access_label": str(row.get("source_access_label") or ""),
                "source_category": str(row.get("source_category") or ""),
                "source_priority": str(row.get("source_priority") or ""),
                "source_requires_credentials": bool(row.get("source_requires_credentials")),
                "source_restricted": bool(row.get("source_restricted")),
                "source_supports_web_search": bool(row.get("source_supports_web_search")),
                "document_id": str(row.get("document_id") or ""),
                "parser": str(row.get("parser") or ""),
                "parser_version": str(row.get("parser_version") or ""),
                "source_hash": str(row.get("source_hash") or ""),
                "page_no": row.get("page_no"),
                "section_path": str(row.get("section_path") or ""),
                "chunk_index": row.get("chunk_index"),
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

        pack_metadata = dict(metadata or {})
        workflow = str(pack_metadata.get("workflow") or "").strip()
        strict_sources_required = workflow in _STRICT_SOURCE_WORKFLOWS

        coverage_gaps: list[str] = []
        if not rows:
            coverage_gaps.append("Nessuna evidenza disponibile.")
        if strict_sources_required and not official:
            coverage_gaps.append("Mancano fonti ufficiali tra le evidenze selezionate.")
        if strict_sources_required and len(compared_sources) < 2:
            coverage_gaps.append("Confronto fonti limitato: meno di due fonti rilevanti.")
        if strict_sources_required and not any(row["trust_class"] == "A" for row in compared_sources):
            coverage_gaps.append("Nessuna fonte primaria di trust class A rilevata.")

        registry_metadata = dict(pack_metadata.get("source_registry") or {})
        restricted_sources = list(registry_metadata.get("restricted_sources") or [])
        partner_sources = list(registry_metadata.get("partner_sources") or [])
        credentialed_sources = list(registry_metadata.get("credentialed_sources") or [])
        requested_sources = list(registry_metadata.get("requested_sources") or [])
        present_registry_keys = {
            str(row.get("source_registry_key") or "").strip()
            for row in compared_sources
            if str(row.get("source_registry_key") or "").strip()
        }
        missing_restricted = [
            row for row in restricted_sources if str(row.get("key") or "").strip() not in present_registry_keys
        ]
        missing_partner = [
            row for row in partner_sources if str(row.get("key") or "").strip() not in present_registry_keys
        ]
        missing_credentialed = [
            row for row in credentialed_sources if str(row.get("key") or "").strip() not in present_registry_keys
        ]
        if missing_restricted:
            labels = ", ".join(str(row.get("label") or row.get("key") or "").strip() for row in missing_restricted[:4])
            coverage_gaps.append(
                f"Restano fonti riservate non interrogabili via web pubblico: {labels}."
            )
        if missing_partner:
            labels = ", ".join(str(row.get("label") or row.get("key") or "").strip() for row in missing_partner[:4])
            coverage_gaps.append(
                f"Restano fonti partner che richiedono integrazione dedicata o credenziali: {labels}."
            )
        if missing_credentialed and not missing_partner:
            labels = ", ".join(str(row.get("label") or row.get("key") or "").strip() for row in missing_credentialed[:4])
            coverage_gaps.append(
                f"Per alcune fonti servono credenziali o abilitazioni aggiuntive: {labels}."
            )

        if strict_sources_required:
            sufficient = bool(rows) and not (
                "Mancano fonti ufficiali tra le evidenze selezionate." in coverage_gaps and len(rows) < 3
            )
        else:
            sufficient = bool(rows)
        needs_human_review = bool(conflicting_items) or not sufficient

        pack_metadata.update(
            {
                "source_count": len(rows),
                "official_count": len(official),
                "trusted_count": len(trusted),
                "strict_sources_required": strict_sources_required,
                "source_registry_requested": requested_sources,
                "source_registry_restricted": restricted_sources,
                "source_registry_partner": partner_sources,
                "source_registry_credentialed": credentialed_sources,
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
