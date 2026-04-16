"""Adapter preventivi per Lex."""

from __future__ import annotations

from .base import BaseLexAdapter, compact_mapping, make_event, make_fact, metadata_for_module


class PreventiviAdapter(BaseLexAdapter):
    module = "preventivi"

    def should_include(self, request, workflow: str, context: dict, evidence: dict) -> bool:
        return bool(metadata_for_module(request, self.module))

    def build_context(self, request, workflow: str, context: dict, evidence: dict) -> dict:
        return compact_mapping(metadata_for_module(request, self.module))

    def collect_facts(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        facts = []
        for key in ("preventivi_aperti", "preventivi_accettati", "scostamento_previsto"):
            value = payload.get(key)
            if value not in (None, ""):
                facts.append(make_fact(self.module, key, value, entity_id=str(payload.get("practice_id") or getattr(request, "fascicolo_id", "") or ""), source="request_metadata"))
        return facts

    def collect_events(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        if not payload:
            return []
        return [make_event(self.module, str(payload.get("event_type") or "preventivi_snapshot_loaded"), entity_id=str(payload.get("practice_id") or ""), source="request_metadata", payload=payload)]