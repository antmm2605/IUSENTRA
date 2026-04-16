"""Adapter scadenziario per Lex."""

from __future__ import annotations

from .base import BaseLexAdapter, as_list, compact_mapping, make_event, make_fact, preview_items


class ScadenziarioAdapter(BaseLexAdapter):
    module = "scadenziario"
    sections = ("scadenziario",)

    def should_include(self, request, workflow: str, context: dict, evidence: dict) -> bool:
        return bool(context.get("scadenziario") or workflow in {"udienza", "next_action"})

    def build_context(self, request, workflow: str, context: dict, evidence: dict) -> dict:
        items = as_list(context.get("scadenziario"))
        return compact_mapping({"scadenze_count": len(items), "preview": preview_items(items)})

    def collect_facts(self, request, workflow: str, context: dict, evidence: dict):
        items = as_list(context.get("scadenziario"))
        if not items:
            return []
        return [make_fact(self.module, "scadenze_count", len(items), entity_id=str(getattr(request, "fascicolo_id", "") or ""), source="scadenziario_context")]

    def collect_events(self, request, workflow: str, context: dict, evidence: dict):
        items = as_list(context.get("scadenziario"))
        if not items:
            return []
        return [make_event(self.module, "scadenziario_context_loaded", entity_id=str(getattr(request, "fascicolo_id", "") or ""), source="scadenziario_context", payload={"preview": preview_items(items)})]

    def collect_warnings(self, request, workflow: str, context: dict, evidence: dict):
        if workflow in {"udienza", "next_action"} and not as_list(context.get("scadenziario")):
            return ["Nessuna scadenza contestuale disponibile nel contesto corrente."]
        return []