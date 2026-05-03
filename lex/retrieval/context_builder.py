"""Builder del contesto di retrieval per l'evidence pack Lex."""

from __future__ import annotations

from .document_parser_docling import is_docling_enabled


class RetrievalContextBuilder:
    def build(self, request, context, workflow: str, queries, sources):
        studio = dict(context.get("studio") or {})
        request_metadata = dict(getattr(request, "metadata", {}) or {})
        source_registry = dict(request_metadata.get("source_registry") or {})
        source_names = []
        for source in list(sources or []):
            name = str(getattr(source, "source_name", "") or source.__class__.__name__).strip()
            if name and name not in source_names:
                source_names.append(name)
        return {
            "workflow": workflow,
            "query": str(getattr(request, "query", "") or ""),
            "effective_question": str(studio.get("effective_question") or getattr(request, "query", "") or ""),
            "source_names": source_names,
            "official_web_requested": "official_web" in source_names,
            "source_registry_requested": list(source_registry.get("requested_sources") or []),
            "source_registry_restricted": list(source_registry.get("restricted_sources") or []),
            "source_registry_partner": list(source_registry.get("partner_sources") or []),
            "source_registry_credentialed": list(source_registry.get("credentialed_sources") or []),
            "docling_enabled": is_docling_enabled(),
            "legal_dashboard_headline": dict(studio.get("legal_dashboard_headline") or {}),
            "focus_label": str(studio.get("focus_label") or ""),
            "queries": list(queries or []),
        }
