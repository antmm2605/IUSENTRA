"""Adapter template atti per il retrieval applicativo Lex."""

from __future__ import annotations

from typing import Any

from lex.contracts import EvidenceItem


class _FallbackTemplateMatch:
    def __init__(self, *, model_code: str, name: str, area: str, score: float, metadata: dict[str, Any]) -> None:
        self.model_code = model_code
        self.name = name
        self.area = area
        self.score = score
        self.found = bool(model_code)
        self.metadata = metadata


class TemplateAttiSource:
    source_name = "template_atti"

    def __init__(self, *, limit: int = 10) -> None:
        self.limit = max(1, min(int(limit or 10), 30))

    def search(self, queries, request, context):
        try:
            from pct.template_atti_lex_service import search_template_models
        except Exception:
            search_template_models = _fallback_search_template_models

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


def _fallback_search_template_models(query: str, *, limit: int = 10, model_code: str = "") -> list[Any]:
    matches: list[Any] = []
    try:
        from pct.compilatore_atti import elenco_modelli
    except Exception:
        return matches
    query_norm = _normalize_text(query)
    query_tokens = [
        token
        for token in query_norm.split()
        if len(token) >= 4 and token not in {"atto", "atti", "crea", "creare", "bozza", "modello", "template"}
    ]
    requested_code = _clean(model_code).upper()
    for model in elenco_modelli():
        code = _clean(model.get("code") or model.get("codice")).upper()
        name = _clean(model.get("name") or model.get("nome") or code)
        area = _clean(model.get("area") or model.get("categoria"))
        haystack = _normalize_text(" ".join([code, name, area, _clean(model.get("description") or model.get("descrizione"))]))
        matched_tokens = [token for token in query_tokens if token in haystack]
        if requested_code and code == requested_code or matched_tokens:
            metadata = _fallback_metadata_for_model(model, code=code, name=name, area=area)
            matches.append(
                _FallbackTemplateMatch(
                    model_code=code,
                    name=metadata.get("name") or name,
                    area=metadata.get("area") or area,
                    score=0.72 if requested_code == code else min(0.68, 0.42 + (len(matched_tokens) / max(1, len(query_tokens))) * 0.24),
                    metadata=metadata,
                )
            )
    return sorted(matches, key=lambda item: item.score, reverse=True)[:limit]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: Any) -> str:
    text = _clean(value).casefold()
    return "".join(char if char.isalnum() else " " for char in text)


def _fallback_metadata_for_model(model: dict[str, Any], *, code: str, name: str, area: str) -> dict[str, Any]:
    required_fields = model.get("required_fields") or model.get("campi_obbligatori") or []
    suggested_attachments = model.get("suggested_attachments") or model.get("allegati_suggeriti") or []
    return {
        "model_code": code,
        "name": name,
        "area": area,
        "required_fields": required_fields if isinstance(required_fields, list) else [],
        "suggested_attachments": suggested_attachments if isinstance(suggested_attachments, list) else [],
        "compile_url": f"/template-atti/compila/{code}" if code else "",
        "source": "catalogo_template_atti",
    }


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
