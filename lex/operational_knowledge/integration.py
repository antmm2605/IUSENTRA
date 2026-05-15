"""HTTP bridge integration for Lex operational knowledge."""

from __future__ import annotations

from typing import Any

from lex.formatting.ui_payloads import direct_answer_payload

from .models import OperationalAnswer
from .serializers import clean_spaces
from .service import OperationalKnowledgeService
from .settings import OperationalKnowledgeSettings


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

    metadata = dict(data or {})
    metadata.update(
        {
            "focus_topic": clean_spaces(studio_context.get("focus_topic")),
            "focus_label": clean_spaces(studio_context.get("focus_label")),
            "request_profile": dict(studio_context.get("request_profile") or {}),
        }
    )
    answer = OperationalKnowledgeService(settings=settings).answer(
        question=resolved_effective_question,
        user=user,
        studio=studio,
        tenant_id=_tenant_id(studio, metadata),
        metadata=metadata,
    )
    if answer is None or not answer.handled:
        return None
    return operational_answer_to_http_payload(
        answer,
        current_user_message=current_user_message,
        resolved_effective_question=resolved_effective_question,
        studio_context=studio_context,
    )


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
