"""Adapter documenti e atti per Lex."""

from __future__ import annotations

from collections import Counter

from .base import BaseLexAdapter, as_list, compact_mapping, make_event, make_fact, preview_items


class DocumentiAdapter(BaseLexAdapter):
    module = "documenti"
    sections = ("documenti", "documento")

    def should_include(self, request, workflow: str, context: dict, evidence: dict) -> bool:
        return bool(getattr(request, "document_id", "") or context.get("documenti"))

    def build_context(self, request, workflow: str, context: dict, evidence: dict) -> dict:
        documenti = as_list(context.get("documenti"))
        documento = dict(context.get("documento") or {})
        return compact_mapping(
            {
                "document_id": getattr(request, "document_id", "") or documento.get("document_id"),
                "documenti_count": len(documenti),
                "preview": preview_items(documenti),
            }
        )

    def collect_facts(self, request, workflow: str, context: dict, evidence: dict):
        documenti = as_list(context.get("documenti"))
        entity_id = str(getattr(request, "fascicolo_id", "") or "")
        facts = []
        if documenti:
            facts.append(make_fact(self.module, "documenti_count", len(documenti), entity_id=entity_id, source="document_context"))
            tipi = Counter(
                str((item or {}).get("tipo") or (item or {}).get("categoria") or "documento")
                for item in documenti
                if isinstance(item, dict)
            )
            for tipo, count in tipi.items():
                facts.append(make_fact(self.module, f"tipo.{tipo}", count, entity_id=entity_id, source="document_context"))
        document_id = str(getattr(request, "document_id", "") or "")
        if document_id:
            facts.append(make_fact(self.module, "document_id", document_id, entity_id=document_id, source="request"))
        return facts

    def collect_events(self, request, workflow: str, context: dict, evidence: dict):
        documenti = as_list(context.get("documenti"))
        if not documenti:
            return []
        return [
            make_event(
                self.module,
                "document_context_loaded",
                entity_id=str(getattr(request, "fascicolo_id", "") or ""),
                source="document_context",
                payload={"documenti_count": len(documenti), "preview": preview_items(documenti)},
            )
        ]

    def collect_warnings(self, request, workflow: str, context: dict, evidence: dict):
        if getattr(request, "document_id", None) and not as_list(context.get("documenti")):
            return ["Documento richiesto senza archivio documentale disponibile nel contesto corrente."]
        return []