"""HTTP bridge integration for Lex operational knowledge."""

from __future__ import annotations

import re
from typing import Any

from lex.formatting.ui_payloads import direct_answer_payload
from lex.research.query_helpers import is_exact_legal_reference_query

from .models import OperationalAnswer
from .query_router import OFFICIAL_SOURCE_LOOKUP_TOKENS
from .serializers import clean_spaces
from .service import OperationalKnowledgeService
from .settings import OperationalKnowledgeSettings
from .unified_chat import LexContextProvider, build_lex_unified_chat

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
    "pec di deposito",
    "deposito pec",
    "pec deposito",
    "controllo pec",
    "controllare pec",
    "pec da controllare",
    "verifica pec",
    "verificare pec",
    "audit pec",
    "mime pec",
)
_STUDIO_DATA_TERMS = (
    "agenda",
    "cartella cliente",
    "cliente",
    "clienti",
    "conferimento",
    "contesto studio",
    "database studio",
    "db studio",
    "deposit",
    "document",
    "email",
    "fascicolo",
    "fascicoli",
    "fattur",
    "messagg",
    "parcell",
    "pec",
    "pratica",
    "pratiche",
    "preventiv",
    "ricerca studio",
    "scadenz",
    "soggett",
    "udienz",
)
_STUDIO_DATA_INTENTS = {
    "cliente_anagrafica",
    "comunicazioni_lookup",
    "domanda_generica",
    "studio_context_lookup",
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

    metadata = LexContextProvider.enrich_metadata(dict(data or {}), studio_context)
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
    answer.metadata = dict(answer.metadata or {})
    answer.metadata["active_context"] = dict(metadata.get("active_context") or {})
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
    if _is_official_source_lookup_question(text):
        return False
    if is_exact_legal_reference_query(text):
        return True

    request_profile = dict(metadata.get("request_profile") or studio_context.get("request_profile") or {})
    intent = clean_spaces(request_profile.get("intent")).lower()
    focus_topic = clean_spaces(metadata.get("focus_topic") or studio_context.get("focus_topic")).lower()
    source_mode = clean_spaces(metadata.get("source_mode") or request_profile.get("source_mode")).lower()
    has_studio_term = any(token in text for token in _STUDIO_DATA_TERMS)
    has_communication_lookup = any(token in text for token in _COMMUNICATION_LOOKUP_TERMS)
    has_communication_source = any(token in text for token in ("pec", "email", "posta", "messaggio"))
    has_pec_control_lookup = "pec" in text and any(
        token in text
        for token in (
            "deposit",
            "controll",
            "verific",
            "presidi",
            "audit",
            "mime",
            "firma",
            "firme",
            "notific",
            "cancelleria",
            "giudice di pace",
            "d.l. 179",
        )
    )
    has_communication_draft = has_communication_source and any(token in text for token in _DRAFTING_TERMS + ("risposta", "rispondi"))
    if has_pec_control_lookup:
        return False
    if has_communication_draft:
        return False
    if (intent in {"comunicazioni_lookup", "pec_comunicazioni", "bozza_lettera"} or has_studio_term) and has_communication_lookup:
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


def _is_official_source_lookup_question(text: str) -> bool:
    if any(token in text for token in OFFICIAL_SOURCE_LOOKUP_TOKENS):
        return True
    return bool(re.search(r"\br\.?\s*g\.?\s*(?:n\.?\s*)?\d{1,7}/\d{4}\b", text))


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
    studio_reasoner = dict((answer.metadata or {}).get("studio_reasoner") or {})
    entity_map = dict(studio_reasoner.get("entity_map") or {})
    fascicolo_timeline = list(studio_reasoner.get("fascicolo_timeline") or [])
    operational_links = _operational_links(answer, sources)
    lex_unified_chat = build_lex_unified_chat(
        answer=answer,
        current_user_message=current_user_message,
        resolved_effective_question=resolved_effective_question,
        studio_context=studio_context,
        sources=sources,
        operational_links=operational_links,
    )
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
            "operational_links": operational_links,
            "lex_unified_chat": lex_unified_chat,
            "active_context": lex_unified_chat.get("active_context") or {},
            "detected_intent": lex_unified_chat.get("detected_intent"),
            "lex_structured_context": lex_unified_chat.get("structured_context") or {},
            "structured_context": lex_unified_chat.get("structured_context") or {},
            "message_blocks": lex_unified_chat.get("renderer_blocks") or [],
            "lex_actions": lex_unified_chat.get("actions") or [],
            "renderer": "LexMessageRenderer",
            "chat_component": "LexUnifiedChat",
            "studio_reasoner": studio_reasoner,
            "reasoner_mode": clean_spaces((answer.metadata or {}).get("reasoner_mode")),
            "rag_governato": bool((answer.metadata or {}).get("rag_governato")),
            "entity_map": entity_map,
            "fascicolo_timeline": fascicolo_timeline,
            "permissions_applied": list(answer.permissions_applied or []),
            "fallback_triggered": False,
            "audit_event_id": answer.audit_event_id,
            "evidence_summary": {
                "evidence_count": len(answer.sources),
                "object_count": len(answer.objects),
                "operational_link_count": len(operational_links),
                "entity_count": len(list(entity_map.get("nodes") or [])),
                "timeline_event_count": len(fascicolo_timeline),
                "coverage_gap_count": len(answer.coverage_gaps),
                "evidence_sufficient": confidence >= 0.55 and not answer.blocked_reason,
                "operational_knowledge": True,
                "studio_reasoner": bool(studio_reasoner),
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
        "action_url": clean_spaces((source.metadata or {}).get("action_url")),
        "record": dict((source.metadata or {}).get("record") or {}),
        "internal": source.internal,
        "retrieved_at": source.retrieved_at,
        "permission_applied": source.permission_applied,
    }


def _operational_links(answer: OperationalAnswer, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_link(*, label: str, url: str, object_type: str = "", object_id: str = "", source_id: str = "") -> None:
        clean_url = clean_spaces(url)
        if not clean_url or clean_url in seen:
            return
        seen.add(clean_url)
        links.append(
            {
                "label": clean_spaces(label) or clean_url,
                "url": clean_url,
                "object_type": clean_spaces(object_type),
                "object_id": clean_spaces(object_id),
                "source_id": clean_spaces(source_id),
            }
        )

    for obj in list(answer.objects or []):
        add_link(
            label=obj.label,
            url=obj.action_url,
            object_type=obj.object_type,
            object_id=obj.object_id,
            source_id=obj.source_id,
        )
    for source in sources:
        add_link(
            label=source.get("title") or source.get("excerpt") or source.get("id"),
            url=source.get("action_url"),
            object_type=source.get("object_type"),
            object_id=source.get("object_id"),
            source_id=source.get("source_id"),
        )
    return links[:60]


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
