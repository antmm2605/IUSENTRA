from __future__ import annotations

from functools import lru_cache
from typing import Any

from .contracts import Citation, LexRequest, LexResponse
from .formatting.ui_payloads import direct_answer_payload


_BOUNDED_FOCUS_TOPICS = {
    "agenda",
    "archivio_sentenze",
    "economico",
    "fatture",
    "fascicoli",
    "pec_firma",
    "preventivi",
    "ricerca_legale",
    "scadenze",
    "sentenze_civili",
    "sentenze_web",
    "telematico",
}
_REQUEST_PROFILE_INTENTS = {
    "checklist_operativa",
    "fatturazione_economica",
    "giurisprudenza",
    "normativa",
    "pratica_procedura",
    "preventivo_guidato",
    "sintesi_fascicolo",
    "tariffario_economico",
}
_STRICT_OFFICIAL_INTENTS = {"giurisprudenza", "normativa", "pratica_procedura"}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _user_id(user: Any) -> str:
    for key in ("username", "id", "email", "nome_utente"):
        value = _clean_spaces(getattr(user, key, ""))
        if value:
            return value
    return "utente"


def _tenant_id(studio: Any, metadata: dict[str, Any]) -> str:
    for key in ("slug", "id", "tenant_slug", "studio_id"):
        value = _clean_spaces(getattr(studio, key, "") or metadata.get(key))
        if value:
            return value
    return "tenant"


def _has_internal_context(studio_context: dict[str, Any]) -> bool:
    if list(studio_context.get("sources") or []):
        return True
    structured = dict(studio_context.get("structured_context") or {})
    for value in structured.values():
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, list) and value:
            return True
        if isinstance(value, str) and _clean_spaces(value):
            return True
    return False


def _resolve_workflow_hint(studio_context: dict[str, Any], request_profile: dict[str, Any]) -> str:
    focus_topic = _clean_spaces(studio_context.get("focus_topic"))
    profile_intent = _clean_spaces(request_profile.get("intent"))
    if focus_topic in {"economico", "preventivi", "fatture"}:
        return "economico"
    if focus_topic == "telematico":
        return "telematico_status"
    if focus_topic == "fascicoli":
        return "fascicolo"
    if profile_intent == "normativa":
        return "normativa"
    if profile_intent == "giurisprudenza":
        return "giurisprudenza"
    if focus_topic in {"ricerca_legale", "archivio_sentenze", "sentenze_civili", "sentenze_web"}:
        return "giurisprudenza"
    return ""


def _resolve_intent(question: str, studio_context: dict[str, Any], request_profile: dict[str, Any]) -> str:
    haystack = _clean_spaces(question).lower()
    focus_topic = _clean_spaces(studio_context.get("focus_topic"))
    profile_intent = _clean_spaces(request_profile.get("intent"))
    if profile_intent == "preventivo_guidato" or "preventiv" in haystack:
        return "evaluate_preventivo"
    if profile_intent == "tariffario_economico" or "tariffario" in haystack:
        return "evaluate_tariffario"
    if profile_intent == "fatturazione_economica" or any(token in haystack for token in ("fattura", "fatture", "parcella", "parcelle")):
        return "evaluate_fatturazione"
    if profile_intent == "sintesi_fascicolo" or focus_topic == "fascicoli":
        return "summarize_fascicolo"
    if profile_intent == "normativa":
        return "research_normativa"
    if profile_intent == "giurisprudenza":
        return "research_giurisprudenza"
    if profile_intent == "checklist_operativa":
        return "suggest_next_action"
    if focus_topic == "telematico":
        return "explain_telematico_error"
    return "ask_lex"


def _should_use_bounded_workflow(
    *,
    attachments: list[dict[str, Any]] | None,
    studio_context: dict[str, Any],
) -> bool:
    if list(attachments or []):
        return False
    request_profile = dict(studio_context.get("request_profile") or {})
    if bool(request_profile.get("drafting_mode")):
        return False
    profile_intent = _clean_spaces(request_profile.get("intent"))
    focus_topic = _clean_spaces(studio_context.get("focus_topic"))
    source_mode = _clean_spaces(studio_context.get("source_mode"))
    return (
        source_mode == "strict"
        or profile_intent in _REQUEST_PROFILE_INTENTS
        or focus_topic in _BOUNDED_FOCUS_TOPICS
    )


@lru_cache(maxsize=1)
def _application_lex_service():
    from .registry import build_lex_service

    return build_lex_service()


def _citation_label(citation: Citation) -> str:
    title = _clean_spaces(getattr(citation, "title", ""))
    excerpt = _clean_spaces(getattr(citation, "excerpt", ""))
    if title and excerpt:
        return f"{title} — {excerpt}"
    return title or excerpt


def _source_rows(response: LexResponse) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    compared_index: dict[str, dict[str, Any]] = {}
    for item in list(response.compared_sources or []):
        title = _clean_spaces(item.get("title"))
        source_id = _clean_spaces(item.get("source_registry_key") or item.get("source_id"))
        if title:
            compared_index[f"title:{title.lower()}"] = dict(item)
        if source_id:
            compared_index[f"id:{source_id.lower()}"] = dict(item)
    for citation in list(response.citations or []):
        key = f"{_clean_spaces(getattr(citation, 'source_id', ''))}:{_clean_spaces(getattr(citation, 'title', ''))}"
        if key in seen:
            continue
        source_id = _clean_spaces(getattr(citation, "source_id", ""))
        title = _clean_spaces(getattr(citation, "title", ""))
        compared = compared_index.get(f"id:{source_id.lower()}") or compared_index.get(f"title:{title.lower()}") or {}
        rows.append(
            {
                "id": source_id,
                "title": title or "Fonte",
                "excerpt": _clean_spaces(getattr(citation, "excerpt", "")),
                "url": getattr(citation, "url", None),
                "authority": _clean_spaces(getattr(citation, "authority", "")),
                "confidence": float(getattr(citation, "confidence", 0.0) or 0.0),
                "verified_reference": bool(getattr(citation, "verified_reference", False)),
                "trust_class": _clean_spaces(getattr(citation, "trust_class", "")),
                "source_registry_key": _clean_spaces(compared.get("source_registry_key")),
                "source_access_status": _clean_spaces(compared.get("source_access_status")),
                "source_access_label": _clean_spaces(compared.get("source_access_label")),
                "source_requires_credentials": bool(compared.get("source_requires_credentials")),
                "source_restricted": bool(compared.get("source_restricted")),
                "source_supports_web_search": bool(compared.get("source_supports_web_search", True)),
            }
        )
        seen.add(key)
    for title in list(response.legal_basis or []):
        clean_title = _clean_spaces(title)
        if not clean_title or clean_title in seen:
            continue
        rows.append({"id": clean_title, "title": clean_title, "excerpt": "", "authority": "Fonte considerata"})
        seen.add(clean_title)
    return rows[:8]


def _confidence_label(value: float) -> str:
    if value >= 0.8:
        return "alta"
    if value >= 0.55:
        return "media"
    return "bassa"


def _confidence_reason(response: LexResponse) -> str:
    summary = dict(response.evidence_summary or {})
    restricted_sources = list(response.metadata.get("restricted_sources") or [])
    partner_sources = list(response.metadata.get("partner_sources") or [])
    if response.answer_mode != "grounded":
        return "Risposta prudenziale: le evidenze disponibili non bastano ancora per chiudere il punto senza revisione."
    official = int(summary.get("official_count") or 0)
    trusted = int(summary.get("trusted_count") or 0)
    if restricted_sources:
        return (
            f"Base forte ma incompleta: restano {len(restricted_sources)} fonti riservate che richiedono portale o credenziali dedicate."
        )
    if partner_sources:
        return (
            f"Base buona ma governata: restano {len(partner_sources)} fonti partner che richiedono abilitazioni aggiuntive."
        )
    if official:
        return f"Base forte: fonti ufficiali {official}, fonti attendibili {trusted}, nessun blocco attivo."
    if trusted:
        return f"Base interna/studio: fonti attendibili {trusted}, risposta costruita sul contesto operativo disponibile."
    return "Risposta costruita sul contesto disponibile; conviene comunque verificare i dati operativi prima dell'azione finale."


def build_bounded_http_payload(
    *,
    user: Any,
    studio: Any,
    data: dict[str, Any],
    current_user_message: str,
    resolved_effective_question: str,
    studio_context: dict[str, Any],
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not _should_use_bounded_workflow(attachments=attachments, studio_context=studio_context):
        return None

    request_profile = dict(studio_context.get("request_profile") or {})
    metadata = dict(data or {})
    metadata.update(
        {
            "mode": _clean_spaces(data.get("mode")) or "general",
            "messages": list(data.get("messages") or []),
            "focus_label": _clean_spaces(studio_context.get("focus_label")),
            "focus_topic": _clean_spaces(studio_context.get("focus_topic")),
            "module": _clean_spaces(studio_context.get("focus_topic")),
            "topic": _clean_spaces(studio_context.get("focus_topic")),
            "request_profile": request_profile,
            "execution_policy": dict(studio_context.get("execution_policy") or {}),
            "source_policy_summary": dict(studio_context.get("source_policy_summary") or {}),
            "source_mode": _clean_spaces(studio_context.get("source_mode")),
            "web_fallback_used": bool(studio_context.get("web_fallback_used")),
            "web_execution_requested": bool(studio_context.get("web_execution_requested")),
        }
    )
    request = LexRequest(
        tenant_id=_tenant_id(studio, metadata),
        user_id=_user_id(user),
        session_id=_clean_spaces(data.get("session_id")) or "lex-http",
        query=resolved_effective_question,
        intent=_resolve_intent(resolved_effective_question, studio_context, request_profile),  # type: ignore[arg-type]
        fascicolo_id=_clean_spaces(data.get("fascicolo_id")) or None,
        document_id=_clean_spaces(data.get("document_id")) or None,
        workflow_hint=_resolve_workflow_hint(studio_context, request_profile) or None,
        metadata=metadata,
        allow_external_research=bool(
            studio_context.get("web_execution_requested")
            or studio_context.get("web_fallback_used")
            or request_profile.get("needs_external_validation")
            or not _has_internal_context(studio_context)
        ),
        require_citations=bool(
            request_profile.get("source_mode") == "strict"
            or _clean_spaces(studio_context.get("focus_topic")) in {"ricerca_legale", "archivio_sentenze", "sentenze_civili", "sentenze_web"}
        ),
        require_official_sources=bool(
            _clean_spaces(request_profile.get("intent")) in _STRICT_OFFICIAL_INTENTS
            or _clean_spaces(studio_context.get("focus_topic")) in {"ricerca_legale", "archivio_sentenze", "sentenze_civili", "sentenze_web", "telematico"}
        ),
    )

    response = _application_lex_service().ask(request)
    if not isinstance(response, LexResponse):
        return None

    citations = [_citation_label(item) for item in list(response.citations or []) if _citation_label(item)]
    sources = _source_rows(response)
    payload = direct_answer_payload(
        current_user_message,
        response.answer,
        query_type="workflow_answer",
        sources=sources,
        citations=citations,
        legal_reference_guard_active=bool(request.require_official_sources),
    )
    payload.update(
        {
            "question": current_user_message,
            "effective_question": resolved_effective_question,
            "answer": response.answer,
            "warnings": list(response.warnings or []),
            "next_actions": list(response.next_actions or []),
            "risk_level": str(response.risk_level or "low"),
            "confidence": float(response.confidence or 0.0),
            "confidence_label": _confidence_label(float(response.confidence or 0.0)),
            "confidence_reason": _confidence_reason(response),
            "answer_mode": str(response.answer_mode or "grounded"),
            "reference_label": _clean_spaces(studio_context.get("focus_label")),
            "focus_label": _clean_spaces(studio_context.get("focus_label")),
            "focus_topic": _clean_spaces(studio_context.get("focus_topic")),
            "web_fallback_used": bool(
                response.metadata.get("fallback_triggered") or studio_context.get("web_fallback_used")
            ),
            "web_execution_requested": bool(studio_context.get("web_execution_requested")),
            "disable_exports": bool(
                response.answer_mode != "grounded" or str(response.risk_level or "low") in {"high", "critical"}
            ),
            "execution_policy": dict(studio_context.get("execution_policy") or {}),
            "request_profile": request_profile,
            "source_policy_summary": dict(studio_context.get("source_policy_summary") or {}),
            "source_mode": _clean_spaces(studio_context.get("source_mode")),
            "routing": dict(payload.get("routing") or {}),
            "followup_resolution": dict(payload.get("followup_resolution") or {}),
            "provider": _clean_spaces(response.metadata.get("provider")),
            "workflow": _clean_spaces(response.metadata.get("workflow")),
            "legal_basis": list(response.legal_basis or []),
            "considered_sources": list(response.considered_sources or []),
            "compared_sources": list(response.compared_sources or []),
            "missing_evidence": list(response.missing_evidence or []),
            "evidence_summary": dict(response.evidence_summary or {}),
        }
    )
    return payload
