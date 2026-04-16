"""Adapter agenda per Lex."""

from __future__ import annotations

from .base import BaseLexAdapter, as_list, compact_mapping, make_event, make_fact, preview_items


class AgendaAdapter(BaseLexAdapter):
    module = "agenda"
    sections = ("agenda",)

    def should_include(self, request, workflow: str, context: dict, evidence: dict) -> bool:
        return bool(context.get("agenda") or workflow == "udienza")

    def build_context(self, request, workflow: str, context: dict, evidence: dict) -> dict:
        agenda = as_list(context.get("agenda"))
        return compact_mapping({"eventi_count": len(agenda), "preview": preview_items(agenda)})

    def collect_facts(self, request, workflow: str, context: dict, evidence: dict):
        agenda = as_list(context.get("agenda"))
        if not agenda:
            return []
        return [make_fact(self.module, "eventi_count", len(agenda), entity_id=str(getattr(request, "fascicolo_id", "") or ""), source="agenda_context")]

    def collect_events(self, request, workflow: str, context: dict, evidence: dict):
        agenda = as_list(context.get("agenda"))
        if not agenda:
            return []
        return [make_event(self.module, "agenda_context_loaded", entity_id=str(getattr(request, "fascicolo_id", "") or ""), source="agenda_context", payload={"preview": preview_items(agenda)})]

    def collect_warnings(self, request, workflow: str, context: dict, evidence: dict):
        if workflow == "udienza" and not as_list(context.get("agenda")):
            return ["Nessun evento agenda disponibile per la preparazione dell'udienza."]
        return []