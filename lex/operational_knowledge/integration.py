"""HTTP bridge integration for Lex operational knowledge."""

from __future__ import annotations

from typing import Any

from lex.formatting.ui_payloads import direct_answer_payload
from lex.research.query_helpers import is_exact_legal_reference_query

from .models import OperationalAnswer
from .serializers import clean_spaces
from .service import OperationalKnowledgeService
from .settings import OperationalKnowledgeSettings

_PUBLIC_LEGAL_FOCUS = {
    "ricerca_legale",
    "archivio_sentenze",
    "sentenze_civili",
    "sentenze_web",
    "giurisprudenza",
    "normativa",
}
_PUBLIC_LEGAL_INTENTS = {
    "giurisprudenza",
    "giurisprudenza_specifica",
    "normativa",
    "prassi",
    "research",
    "fonti",
    "pratica_procedura",
}
_PUBLIC_LEGAL_TERMS = (
    "sentenza",
    "ordinanza",
    "cassazione",
    "giurisprudenza",
    "normativa",
    "normattiva",
    "gazzetta ufficiale",
    "corte costituzionale",
    "consiglio di stato",
    "massima",
)
_DRAFTING_INTENTS = {
    "bozza_atto",
    "bozza_lettera",
    "pec_comunicazioni",
}
_DRAFTING_TERMS = (
    "bozza",
    "diffida",
    "lettera",
    "messa in mora",
    "redigi",
    "scrivi",
)
_COMMUNICATION_LOOKUP_TERMS = (
    "ultima pec",
    "ultime pec",
    "ultimo messaggio pec",
    "messaggi pec",
    "pec ricevut",
    "pec inviat",
    "ultima email",
    "ultime email",
    "email ricevut",
    "email inviat",
    "ultima posta",
    "posta ordinaria",
    "casella",
    "allegati pec",
)
_STUDIO_DATA_TERMS = (
    "agenda",
    "cartella cliente",
    "cliente",
    "clienti",
    "conferimento",
    "email",
    "fascicolo",
    "fascicoli",
    "fattur",
    "messagg",
    "parcell",
    "pec",
    "preventiv",
    "scadenz",
    "soggett",
)
_STUDIO_DATA_INTENTS = {
    "cliente_anagrafica",
    "domanda_generica",
}
_STUDIO_DATA_FOCUS = {
    "agenda",
    "clienti",
    "documenti",
    "economico",
    "fascicoli",
    "fatture",
    "pec_firma",
    "preventivi",
    "scadenze",
    "soggetti",
    "udienze",
}
_SOURCE_OVERVIEW_TERMS = ("quali fonti", "fonti hai usato", "mostra fonti")


def build_operational_http_payload(
    *,
    user: Any,
    studio: Any,
    data: dict[str, Any],
    current_user_message: str,
    resolved_effective_question: str,
    studio_context: dict[str, Any],
) -> dict[str, Any] | None:
    settings = OperationalKnowledgeSettings.from_env()
    if not settings.enabled:
        return None
    if not _has_operational_permission_context(user):
        return None

    metadata = dict(data or {})
    metadata.update(
        {
            "focus_topic": clean_spaces(studio_context.get("focus_topic")),
            "focus_label": clean_spaces(studio_context.get("focus_label")),
            "request_profile": dict(studio_context.get("request_profile") or {}),
        }
    )
    if _should_defer_to_public_legal_research(
        resolved_effective_question,
        metadata=metadata,
        studio_context=studio_context,
    ):
        return None
    answer = OperationalKnowledgeService(settings=settings).answer(
        question=resolved_effective_question,
        user=user,
        studio=studio,
        tenant_id=_tenant_id(studio, metadata),
        metadata=metadata,
    )
    if answer is None or not answer.handled:
        return None
    if _should_fall_back_after_operational_answer(answer):
        return None
    return operational_answer_to_http_payload(
        answer,
        current_user_message=current_user_message,
        resolved_effective_question=resolved_effective_question,
        studio_context=studio_context,
    )


def _should_defer_to_public_legal_research(
    question: str,
    *,
    metadata: dict[str, Any],
    studio_context: dict[str, Any],
) -> bool:
    """Keep public legal research out of the operational studio-data layer."""

    text = clean_spaces(question).lower()
    if not text:
        return False
    if any(token in text for token in _SOURCE_OVERVIEW_TERMS):
        return False
    if is_exact_legal_reference_query(text):
        return True

    request_profile = dict(metadata.get("request_profile") or studio_context.get("request_profile") or {})
    intent = clean_spaces(request_profile.get("intent")).lower()
    focus_topic = clean_spaces(metadata.get("focus_topic") or studio_context.get("focus_topic")).lower()
    source_mode = clean_spaces(metadata.get("source_mode") or request_profile.get("source_mode")).lower()
    has_studio_term = any(token in text for token in _STUDIO_DATA_TERMS)
    if intent == "pec_comunicazioni" and has_studio_term and any(token in text for token in _COMMUNICATION_LOOKUP_TERMS):
        return False
    if intent in _DRAFTING_INTENTS or any(token in text for token in _DRAFTING_TERMS):
        return True
    if intent in _STUDIO_DATA_INTENTS and (focus_topic in _STUDIO_DATA_FOCUS or has_studio_term):
        return False
    if focus_topic in _STUDIO_DATA_FOCUS and has_studio_term:
        return False
    if intent in _PUBLIC_LEGAL_INTENTS or focus_topic in _PUBLIC_LEGAL_FOCUS:
        return True
    if bool(metadata.get("web_execution_requested") or metadata.get("web_fallback_used")):
        return True
    if clean_spaces(metadata.get("external_sources_reason")):
        return True
    if source_mode in {"strict", "public", "official", "free", "free_web", "web_libero", "ricerca_libera", "libera"}:
        return True
    has_public_term = any(token in text for token in _PUBLIC_LEGAL_TERMS)
    return has_public_term and not has_studio_term


def _has_operational_permission_context(user: Any) -> bool:
    if user is None:
        return False
    if callable(getattr(user, "ha_permesso", None)):
        return True
    effective = getattr(user, "permessi_effettivi", None)
    if effective is not None:
        try:
            return bool(list(effective or []))
        except Exception:
            return bool(effective)
    if isinstance(user, dict):
        permissions = user.get("permessi_effettivi") or user.get("permissions") or user.get("permessi")
        return bool(permissions)
    return False


def _should_fall_back_after_operational_answer(answer: OperationalAnswer) -> bool:
    if answer.blocked_reason:
        return False
    if answer.sources or answer.objects:
        return False
    gaps = [clean_spaces(gap).lower() for gap in list(answer.coverage_gaps or []) if clean_spaces(gap)]
    if not gaps:
        return False
    unavailable_tokens = ("non disponibile", "non interrogabile", "repository ")
    return all(any(token in gap for token in unavailable_tokens) for gap in gaps)


def operational_answer_to_http_payload(
    answer: OperationalAnswer,
    *,
    current_user_message: str,
    resolved_effective_question: str,
    studio_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    studio_context = dict(studio_context or {})
    sources = [_source_row(source) for source in answer.sources]
    citations = [source.label() for source in answer.sources if clean_spaces(source.label())]
    payload = direct_answer_payload(
        current_user_message,
        answer.answer,
        query_type="workflow_answer",
        sources=sources,
        citations=citations,
        legal_reference_guard_active=False,
    )
    confidence = float(answer.confidence or 0.0)
    payload.update(
        {
            "question": current_user_message,
            "effective_question": resolved_effective_question,
            "answer": answer.answer,
            "warnings": list(answer.warnings or []),
            "next_actions": list(answer.next_actions or []),
            "risk_level": "medium" if answer.blocked_reason else "low",
            "confidence": confidence,
            "confidence_label": _confidence_label(confidence),
            "confidence_reason": _confidence_reason(answer),
            "answer_mode": "blocked" if answer.blocked_reason else "lookup",
            "reference_label": clean_spaces(studio_context.get("focus_label")),
            "focus_label": clean_spaces(studio_context.get("focus_label")),
            "focus_topic": clean_spaces(studio_context.get("focus_topic")),
            "web_fallback_used": False,
            "web_execution_requested": False,
            "external_sources_used": False,
            "disable_exports": bool(answer.blocked_reason or answer.confidence < 0.55),
            "workflow": "operational_knowledge",
            "provider": "deterministic",
            "legal_basis": [],
            "considered_sources": [source.label() for source in answer.sources],
            "compared_sources": [],
            "missing_evidence": list(answer.coverage_gaps or []),
            "coverage_gaps": list(answer.coverage_gaps or []),
            "operational_objects": [obj.to_dict() for obj in answer.objects],
            "permissions_applied": list(answer.permissions_applied or []),
            "fallback_triggered": False,
            "audit_event_id": answer.audit_event_id,
            "evidence_summary": {
                "evidence_count": len(answer.sources),
                "object_count": len(answer.objects),
                "coverage_gap_count": len(answer.coverage_gaps),
                "evidence_sufficient": confidence >= 0.55 and not answer.blocked_reason,
                "operational_knowledge": True,
            },
            "metadata": answer.metadata,
        }
    )
    return payload


def _source_row(source) -> dict[str, Any]:
    return {
        "id": source.object_id or source.source_id,
        "title": source.title or source.source_name,
        "excerpt": source.label(),
        "authority": source.source_name,
        "confidence": source.confidence,
        "source_type": source.source_type,
        "source_id": source.source_id,
        "object_type": source.object_type,
        "object_id": source.object_id,
        "internal": source.internal,
        "retrieved_at": source.retrieved_at,
        "permission_applied": source.permission_applied,
    }


def _tenant_id(studio: Any, metadata: dict[str, Any]) -> str:
    for key in ("slug", "id", "tenant_slug", "studio_id"):
        value = clean_spaces(getattr(studio, key, "") or metadata.get(key))
        if value:
            return value
    return ""


def _confidence_label(value: float) -> str:
    if value >= 0.8:
        return "alta"
    if value >= 0.55:
        return "media"
    return "bassa"


def _confidence_reason(answer: OperationalAnswer) -> str:
    if answer.blocked_reason:
        return "Richiesta bloccata dalla policy operativa Lex."
    if answer.coverage_gaps:
        return "Risposta costruita solo sulle sorgenti interne autorizzate; restano dati mancanti o non accessibili."
    return "Risposta deterministica basata su dati interni del tenant corrente e permessi applicati."
