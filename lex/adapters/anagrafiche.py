"""Adapter anagrafiche per Lex."""

from __future__ import annotations

from .base import BaseLexAdapter, as_list, as_mapping, compact_mapping, make_event, make_fact, metadata_for_module


class AnagraficheAdapter(BaseLexAdapter):
    module = "anagrafiche"
    sections = ("anagrafica",)

    def should_include(self, request, workflow: str, context: dict, evidence: dict) -> bool:
        return bool(context.get("anagrafica") or metadata_for_module(request, self.module))

    def build_context(self, request, workflow: str, context: dict, evidence: dict) -> dict:
        anagrafica = as_mapping(context.get("anagrafica"))
        payload = metadata_for_module(request, self.module)
        payload.setdefault("clienti_count", len(as_list(anagrafica.get("clienti"))))
        payload.setdefault("soggetti_count", len(as_list(anagrafica.get("soggetti"))))
        return compact_mapping(payload)

    def collect_facts(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        facts = []
        for key in ("clienti_count", "soggetti_count"):
            value = payload.get(key)
            if value not in (None, ""):
                facts.append(make_fact(self.module, key, value, entity_id=str(getattr(request, "fascicolo_id", "") or ""), source="anagrafica_context"))
        return facts

    def collect_events(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        if not payload:
            return []
        return [make_event(self.module, "anagrafica_context_loaded", entity_id=str(getattr(request, "fascicolo_id", "") or ""), source="anagrafica_context", payload=payload)]