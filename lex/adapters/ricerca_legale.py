"""Adapter ricerca legale per Lex."""

from __future__ import annotations

from .base import BaseLexAdapter, as_list, as_mapping, compact_mapping, make_event, make_fact


class RicercaLegaleAdapter(BaseLexAdapter):
    module = "ricerca_legale"
    sections = ("studio",)

    def build_context(self, request, workflow: str, context: dict, evidence: dict) -> dict:
        studio = as_mapping(context.get("studio"))
        evidence_pack = as_mapping((evidence or {}).get("evidence_pack"))
        return compact_mapping(
            {
                "queries": as_list(evidence_pack.get("queries")) or as_list((evidence or {}).get("queries")),
                "official_sources": as_list(evidence_pack.get("official_sources")),
                "trusted_sources": as_list(evidence_pack.get("trusted_sources")),
                "verified_legal_references": as_list(studio.get("verified_legal_references")),
                "legal_route_scope": studio.get("legal_route_scope"),
                "research_strategy": studio.get("research_strategy"),
            }
        )

    def collect_facts(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        facts = []
        for key in ("queries", "official_sources", "trusted_sources", "verified_legal_references"):
            value = payload.get(key)
            if isinstance(value, list):
                facts.append(make_fact(self.module, f"{key}_count", len(value), entity_id=str(getattr(request, "session_id", "") or ""), source="research"))
        if payload.get("legal_route_scope"):
            facts.append(make_fact(self.module, "legal_route_scope", payload["legal_route_scope"], entity_id=str(getattr(request, "session_id", "") or ""), source="studio_context"))
        return facts

    def collect_events(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        if not payload:
            return []
        return [make_event(self.module, "evidence_pack_built", entity_id=str(getattr(request, "session_id", "") or ""), source="research", payload=payload)]

    def collect_warnings(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        if payload.get("official_sources") or payload.get("verified_legal_references"):
            return []
        return ["Nessuna fonte ufficiale verificata nel pacchetto di ricerca corrente."]