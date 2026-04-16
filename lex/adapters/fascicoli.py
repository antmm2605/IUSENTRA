"""Adapter fascicoli per il contesto Lex."""

from __future__ import annotations

from .base import BaseLexAdapter, as_list, as_mapping, compact_mapping, make_event, make_fact


class FascicoliAdapter(BaseLexAdapter):
    module = "fascicoli"
    sections = ("fascicolo",)

    def should_include(self, request, workflow: str, context: dict, evidence: dict) -> bool:
        return bool(getattr(request, "fascicolo_id", "") or context.get("fascicolo"))

    def build_context(self, request, workflow: str, context: dict, evidence: dict) -> dict:
        fascicolo = as_mapping(context.get("fascicolo"))
        return compact_mapping(
            {
                "fascicolo_id": fascicolo.get("id") or getattr(request, "fascicolo_id", ""),
                "numero_rg": fascicolo.get("numero_rg") or fascicolo.get("rg"),
                "stato": fascicolo.get("stato"),
                "fase": fascicolo.get("fase"),
                "ufficio": fascicolo.get("ufficio") or fascicolo.get("tribunale"),
                "parti": len(as_list(fascicolo.get("parti"))),
            }
        )

    def collect_facts(self, request, workflow: str, context: dict, evidence: dict):
        fascicolo = as_mapping(context.get("fascicolo"))
        fascicolo_id = str(fascicolo.get("id") or getattr(request, "fascicolo_id", "") or "")
        facts = []
        if fascicolo_id:
            facts.append(make_fact(self.module, "fascicolo_id", fascicolo_id, entity_id=fascicolo_id, source="fascicolo_context"))
        for key in ("stato", "fase", "ufficio", "tribunale", "numero_rg", "rg"):
            value = fascicolo.get(key)
            if value not in (None, ""):
                facts.append(make_fact(self.module, key, value, entity_id=fascicolo_id, source="fascicolo_context"))
        parti = as_list(fascicolo.get("parti"))
        if parti:
            facts.append(make_fact(self.module, "parti_count", len(parti), entity_id=fascicolo_id, source="fascicolo_context"))
        return facts

    def collect_events(self, request, workflow: str, context: dict, evidence: dict):
        fascicolo_id = str(getattr(request, "fascicolo_id", "") or as_mapping(context.get("fascicolo")).get("id") or "")
        if not fascicolo_id:
            return []
        return [make_event(self.module, "fascicolo_context_loaded", entity_id=fascicolo_id, source="fascicolo_context")]

    def collect_warnings(self, request, workflow: str, context: dict, evidence: dict):
        if getattr(request, "fascicolo_id", None) and not as_mapping(context.get("fascicolo")):
            return ["Il fascicolo richiesto non e' stato trovato nel contesto disponibile."]
        return []