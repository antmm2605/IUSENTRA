"""Adapter Centro Servizi Telematici per Lex."""

from __future__ import annotations

from .base import BaseLexAdapter, as_list, compact_mapping, make_event, make_fact, metadata_for_module


class TelematicoAdapter(BaseLexAdapter):
    module = "telematico"
    sections = ("telematico",)

    def should_include(self, request, workflow: str, context: dict, evidence: dict) -> bool:
        return bool(context.get("telematico") or metadata_for_module(request, self.module) or workflow == "telematico")

    def build_context(self, request, workflow: str, context: dict, evidence: dict) -> dict:
        telematico = context.get("telematico")
        payload = metadata_for_module(request, self.module)
        if isinstance(telematico, dict):
            payload = {**dict(telematico), **payload}
        elif isinstance(telematico, list):
            payload.setdefault("items_count", len(telematico))
        return compact_mapping(payload)

    def collect_facts(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        facts = []
        entity_id = str(getattr(request, "fascicolo_id", "") or payload.get("practice_id") or "")
        for key in ("source", "items_count", "documents_found", "documents_imported", "documents_missing", "status", "error_count"):
            value = payload.get(key)
            if value not in (None, ""):
                facts.append(make_fact(self.module, key, value, entity_id=entity_id, source="telematico_context"))
        if payload:
            facts.append(make_fact(self.module, "payload_present", True, entity_id=entity_id, source="telematico_context"))
        return facts

    def collect_events(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        if not payload:
            return []
        error_types = as_list(payload.get("error_types"))
        return [
            make_event(
                self.module,
                str(payload.get("event_type") or "telematico_snapshot_loaded"),
                entity_id=str(getattr(request, "fascicolo_id", "") or payload.get("practice_id") or ""),
                source=str(payload.get("source") or "telematico_context"),
                payload=payload,
                has_errors=bool(payload.get("has_errors") or error_types or payload.get("documents_missing")),
            )
        ]

    def collect_warnings(self, request, workflow: str, context: dict, evidence: dict):
        payload = self.build_context(request, workflow, context, evidence)
        warnings = []
        if workflow == "telematico" and not payload:
            warnings.append("Nessun segnale telematico disponibile per questa richiesta.")
        if payload.get("documents_missing"):
            warnings.append("Import telematico non completo: risultano documenti mancanti rispetto alla fonte ufficiale.")
        if payload.get("has_errors") or payload.get("error_count"):
            warnings.append("Sono presenti anomalie o errori nel canale telematico da verificare.")
        return warnings