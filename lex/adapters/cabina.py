"""Adapter della Cabina Intelligente per il contesto Lex."""

from __future__ import annotations

from .base import BaseLexAdapter, as_list, as_mapping, compact_mapping, make_event, make_fact


class CabinaAdapter(BaseLexAdapter):
    module = "cabina"
    sections = ("studio", "runtime", "utente", "permessi", "sessione")

    def build_context(self, request, workflow: str, context: dict, evidence: dict) -> dict:
        studio = as_mapping(context.get("studio"))
        return compact_mapping(
            {
                "tenant_id": getattr(request, "tenant_id", ""),
                "workflow": workflow,
                "legal_dashboard_headline": as_mapping(studio.get("legal_dashboard_headline")),
                "engine_ids": as_list(studio.get("engine_ids")),
                "source_ids": as_list(studio.get("source_ids")),
                "focus_label": studio.get("focus_label"),
                "legal_route_scope": studio.get("legal_route_scope"),
                "execution_policy": as_mapping(studio.get("execution_policy")),
            }
        )

    def collect_facts(self, request, workflow: str, context: dict, evidence: dict):
        studio = as_mapping(context.get("studio"))
        headline = as_mapping(studio.get("legal_dashboard_headline"))
        facts = [
            make_fact(self.module, "tenant_id", str(getattr(request, "tenant_id", "") or ""), entity_id=str(getattr(request, "tenant_id", "") or ""), source="request"),
            make_fact(self.module, "workflow", workflow, entity_id=str(getattr(request, "session_id", "") or ""), source="request"),
        ]
        for key, value in headline.items():
            if value not in (None, ""):
                facts.append(make_fact(self.module, f"headline.{key}", value, entity_id=str(getattr(request, "tenant_id", "") or ""), source="legal_dashboard"))
        engine_ids = as_list(studio.get("engine_ids"))
        if engine_ids:
            facts.append(make_fact(self.module, "motori_attivi", len(engine_ids), entity_id=str(getattr(request, "tenant_id", "") or ""), source="legal_route"))
        verified = as_list(studio.get("verified_legal_references"))
        if verified:
            facts.append(make_fact(self.module, "riferimenti_verificati", len(verified), entity_id=str(getattr(request, "tenant_id", "") or ""), source="studio_context"))
        return facts

    def collect_events(self, request, workflow: str, context: dict, evidence: dict):
        studio = as_mapping(context.get("studio"))
        headline = as_mapping(studio.get("legal_dashboard_headline"))
        if not headline and not as_list(studio.get("engine_ids")):
            return []
        return [
            make_event(
                self.module,
                "cockpit_snapshot_loaded",
                entity_id=str(getattr(request, "tenant_id", "") or ""),
                source="studio_context",
                payload={
                    "headline_keys": list(headline.keys()),
                    "engine_count": len(as_list(studio.get("engine_ids"))),
                    "source_count": len(as_list(studio.get("source_ids"))),
                },
            )
        ]

    def collect_warnings(self, request, workflow: str, context: dict, evidence: dict):
        studio = as_mapping(context.get("studio"))
        if studio:
            return []
        return ["Cockpit studio non disponibile nel contesto applicativo corrente."]