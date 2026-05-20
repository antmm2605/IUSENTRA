"""Adapter template atti per il retrieval applicativo Lex."""

from __future__ import annotations

from typing import Any

from lex.contracts import EvidenceItem


class TemplateAttiSource:
    source_name = "template_atti"

    def __init__(self, *, limit: int = 10) -> None:
        self.limit = max(1, min(int(limit or 10), 30))

    def search(self, queries, request, context):
        try:
            from pct.template_atti_lex_service import search_template_models
        except Exception:
            return []

        query_values = [str(item or "").strip() for item in list(queries or []) if str(item or "").strip()]
        if not query_values:
            query_values = [str(getattr(request, "query", "") or "").strip()]

        seen: set[str] = set()
        results: list[EvidenceItem] = []
        metadata_request = dict(getattr(request, "metadata", {}) or {})
        active_context = metadata_request.get("active_context") if isinstance(metadata_request.get("active_context"), dict) else {}
        requested_code = str(
            active_context.get("model_code")
            or active_context.get("modelCode")
            or metadata_request.get("model_code")
            or ""
        ).strip()
        for query in query_values:
            for match in search_template_models(query, limit=self.limit, model_code=requested_code):
                if not match.found or match.model_code in seen:
                    continue
                seen.add(match.model_code)
                results.append(_to_evidence(match))
                if len(results) >= self.limit:
                    return results
        return results


def _to_evidence(match: Any) -> EvidenceItem:
    metadata = dict(getattr(match, "metadata", {}) or {})
    code = str(metadata.get("model_code") or getattr(match, "model_code", "") or "").strip()
    name = str(metadata.get("name") or getattr(match, "name", "") or code).strip()
    area = str(metadata.get("area") or getattr(match, "area", "") or "").strip()
    fields = metadata.get("required_fields") or []
    attachments = metadata.get("suggested_attachments") or []
    content = " ".join(
        part
        for part in [
            f"Modello catalogo atti: {name}.",
            f"Area: {area}." if area else "",
            f"Campi richiesti: {', '.join(fields[:8])}." if isinstance(fields, list) and fields else "",
            f"Allegati suggeriti: {', '.join(attachments[:5])}." if isinstance(attachments, list) and attachments else "",
        ]
        if part
    )
    return EvidenceItem(
        source_type="template_atto",
        source_id=code,
        title=name,
        content=content or name,
        score=float(getattr(match, "score", 0.0) or 0.0),
        metadata=metadata,
        trust_class="B",
        source_level=3,
        trust_score=0.86,
        freshness_score=0.8,
        context_fit_score=float(getattr(match, "score", 0.0) or 0.0),
        consensus_score=0.8,
        verified_reference=True,
        authority="iusentra_template_atti",
        official_url=str(metadata.get("source_url") or metadata.get("compile_url") or "") or None,
    )
