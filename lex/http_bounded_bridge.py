from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from .contracts import Citation, LexRequest, LexResponse
from .formatting.ui_payloads import direct_answer_payload
from .retrieval.attachment_evidence import (
    attachment_evidence_source_rows,
    build_attachment_evidence,
)

_BOUNDED_FOCUS_TOPICS = {
    "economico",
    "fatture",
    "pec_firma",
    "preventivi",
    "telematico",
}
_REQUEST_PROFILE_INTENTS = {
    "fatturazione_economica",
    "preventivo_guidato",
    "tariffario_economico",
    "bozza_lettera",
    "bozza_atto",
}
_UNBOUNDED_PROFILE_INTENTS = {
    "checklist_operativa",
    "pratica_procedura",
    "sintesi_fascicolo",
}
_STRICT_OFFICIAL_INTENTS = {"giurisprudenza", "giurisprudenza_specifica", "normativa", "pratica_procedura"}
_STRICT_SOURCE_WORKFLOWS = {"normativa", "giurisprudenza", "giurisprudenza_specifica", "prassi", "research", "fonti"}
_LEGAL_BOUNDED_PROFILE_INTENTS = {"giurisprudenza", "giurisprudenza_specifica", "normativa"}
_LEGAL_BOUNDED_FOCUS_TOPICS = {"ricerca_legale", "archivio_sentenze", "sentenze_civili", "sentenze_web"}
_FASCICOLO_FIRST_TOPICS = {"fascicoli"}
_EXTERNAL_LEGAL_TOKENS = (
    "norma",
    "normativa",
    "legge",
    "decreto",
    "art.",
    "articolo",
    "codice civile",
    "codice penale",
    "cassazione",
    "sentenza",
    "giurisprudenza",
    "fonte ufficiale",
    "fonti ufficiali",
    "verifica normativa",
    "web",
    "cerca",
    "controlla",
    "aggiornata",
    "vigente",
)
_NORMATIVE_EXTERNAL_TOKENS = (
    "norma",
    "normativa",
    "legge",
    "decreto",
    "art.",
    "articolo",
    "codice civile",
    "codice penale",
    "cassazione",
    "sentenza",
    "giurisprudenza",
    "fonte ufficiale",
    "fonti ufficiali",
)
_FALSE_VALUES = {"0", "false", "falso", "no", "off", "disabled", "disabilitato"}
_TRUE_VALUES = {"1", "true", "vero", "yes", "si", "on", "enabled", "abilitato"}
_FREE_WEB_MODES = {"free", "free_web", "web_libero", "ricerca_libera", "libera"}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = _clean_spaces(raw).lower()
    if value in _FALSE_VALUES:
        return False
    if value in _TRUE_VALUES:
        return True
    return default


def _payload_flag(value: Any) -> bool:
    if value is True:
        return True
    return _clean_spaces(value).lower() in _TRUE_VALUES


def _manual_free_web_enabled(data: dict[str, Any], studio_context: dict[str, Any] | None = None) -> bool:
    studio_context = dict(studio_context or {})
    request_profile = dict(studio_context.get("request_profile") or {})
    source_mode = _clean_spaces(
        data.get("source_mode")
        or studio_context.get("source_mode")
        or request_profile.get("source_mode")
    ).lower()
    if source_mode in _FREE_WEB_MODES:
        return True
    return any(
        _payload_flag((data or {}).get(key)) or _payload_flag(studio_context.get(key))
        for key in ("free_web_enabled", "free_web", "force_free_web_search", "manual_free_web_enabled")
    )


def apply_manual_free_web_context(data: dict[str, Any], studio_context: dict[str, Any]) -> dict[str, Any]:
    if not _manual_free_web_enabled(data, studio_context):
        return studio_context
    updated = dict(studio_context or {})
    request_profile = dict(updated.get("request_profile") or {})
    request_profile["source_mode"] = "free_web"
    request_profile["needs_external_validation"] = True
    updated["request_profile"] = request_profile
    updated["source_mode"] = "free_web"
    updated["web_execution_requested"] = True
    updated["free_web_enabled"] = True
    updated["manual_free_web_enabled"] = True
    updated["answer_guardrail_message"] = ""
    return updated


def _governed_only_enabled() -> bool:
    """Ritorna True quando Lex deve usare solo workflow governati."""

    return _env_flag("LEX_GOVERNED_ONLY", default=True)


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
    if profile_intent == "bozza_lettera":
        return "drafting_legal_letter"
    if profile_intent == "bozza_atto":
        return "atto"
    if profile_intent == "giurisprudenza_specifica":
        return "giurisprudenza_specifica"
    if profile_intent == "cliente_anagrafica" or focus_topic == "clienti":
        return "studio_data_lookup"
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


def _is_fascicolo_first_request(data: dict[str, Any], studio_context: dict[str, Any], workflow_hint: str) -> bool:
    return bool(
        _clean_spaces(data.get("fascicolo_id"))
        or workflow_hint == "fascicolo"
        or _clean_spaces(studio_context.get("focus_topic")) in _FASCICOLO_FIRST_TOPICS
    )


_DRAFTING_INTENTS = {"bozza_lettera", "bozza_atto", "risposta_in_italiano"}
_DRAFTING_WEB_ONLY_TOKENS = (
    "norma",
    "normativa",
    "legge",
    "decreto",
    "art.",
    "articolo",
    "codice civile",
    "codice penale",
)


def _external_sources_reason(
    question: str,
    studio_context: dict[str, Any],
    request_profile: dict[str, Any],
    *,
    fascicolo_first: bool,
) -> str | None:
    source_mode = _clean_spaces(studio_context.get("source_mode") or request_profile.get("source_mode")).lower()
    profile_intent = _clean_spaces(request_profile.get("intent")).lower()
    focus_topic = _clean_spaces(studio_context.get("focus_topic")).lower()
    text = _clean_spaces(question).lower()
    explicit_web = bool(studio_context.get("web_execution_requested") or studio_context.get("web_fallback_used"))

    if source_mode in _FREE_WEB_MODES or _payload_flag(studio_context.get("free_web_enabled")):
        return "Ricerca web libera attivata manualmente dall'utente."

    # Per i workflow di redazione, "web"/"cerca" nella query dell'utente NON deve
    # attivare la ricerca esterna di giurisprudenza o fonti irrilevanti.
    # Solo token normativi specifici giustificano la ricerca per bozza/drafting.
    if profile_intent in _DRAFTING_INTENTS:
        has_normative_token = any(token in text for token in _DRAFTING_WEB_ONLY_TOKENS)
        if has_normative_token:
            return "La bozza richiede un riferimento normativo da verificare."
        return None

    explicit_research = (
        source_mode == "strict"
        or profile_intent in _LEGAL_BOUNDED_PROFILE_INTENTS
        or focus_topic in _LEGAL_BOUNDED_FOCUS_TOPICS
        or bool(request_profile.get("needs_external_validation"))
        or explicit_web
    )
    has_legal_token = any(token in text for token in _EXTERNAL_LEGAL_TOKENS)
    has_normative_token = any(token in text for token in _NORMATIVE_EXTERNAL_TOKENS)

    if not fascicolo_first:
        if explicit_research or has_legal_token:
            return "La domanda richiede una verifica su fonti ufficiali o normative."
        return None

    if has_normative_token:
        return "La domanda richiede una verifica normativa o una fonte ufficiale pertinente."
    if explicit_research and has_legal_token:
        return "La domanda sul fascicolo richiede anche una verifica normativa o una fonte ufficiale pertinente."
    if explicit_web and has_legal_token:
        return "L'utente ha chiesto una verifica esterna pertinente alla domanda sul fascicolo."
    return None


def _resolve_intent(question: str, studio_context: dict[str, Any], request_profile: dict[str, Any]) -> str:
    haystack = _clean_spaces(question).lower()
    focus_topic = _clean_spaces(studio_context.get("focus_topic"))
    profile_intent = _clean_spaces(request_profile.get("intent"))
    if profile_intent == "bozza_lettera":
        return "bozza_lettera"
    if profile_intent == "bozza_atto":
        return "bozza_atto"
    if profile_intent == "giurisprudenza_specifica":
        return "giurisprudenza_specifica"
    if profile_intent == "cliente_anagrafica" or focus_topic == "clienti":
        return "cliente_anagrafica"
    if profile_intent == "normativa":
        return "research_normativa"
    if profile_intent == "giurisprudenza":
        return "research_giurisprudenza"
    if profile_intent == "pratica_procedura":
        return "suggest_next_action"
    if profile_intent == "sintesi_fascicolo":
        return "summarize_fascicolo"
    if profile_intent == "checklist_operativa":
        return "suggest_next_action"
    if profile_intent == "preventivo_guidato" or "preventiv" in haystack:
        return "evaluate_preventivo"
    if profile_intent == "tariffario_economico" or "tariffario" in haystack:
        return "evaluate_tariffario"
    if profile_intent == "fatturazione_economica" or any(token in haystack for token in ("fattura", "fatture", "parcella", "parcelle")):
        return "evaluate_fatturazione"
    if focus_topic == "fascicoli":
        return "summarize_fascicolo"
    if focus_topic == "telematico":
        return "explain_telematico_error"
    return "ask_lex"


def _should_use_bounded_workflow(
    *,
    attachments: list[dict[str, Any]] | None,
    studio_context: dict[str, Any],
) -> bool:
    request_profile = dict(studio_context.get("request_profile") or {})
    profile_intent = _clean_spaces(request_profile.get("intent"))
    focus_topic = _clean_spaces(studio_context.get("focus_topic"))
    source_mode = _clean_spaces(studio_context.get("source_mode") or request_profile.get("source_mode"))

    if list(attachments or []):
        return True

    if _manual_free_web_enabled({}, studio_context):
        return True

    if _governed_only_enabled():
        return True

    # Modalita' legacy: disponibile solo quando LEX_GOVERNED_ONLY=0.
    if list(attachments or []):
        return False
    if bool(request_profile.get("drafting_mode")):
        return False
    legal_request = profile_intent in _LEGAL_BOUNDED_PROFILE_INTENTS or focus_topic in _LEGAL_BOUNDED_FOCUS_TOPICS
    legal_bounded_request = (
        legal_request
        and (
            source_mode == "strict"
            or bool(studio_context.get("web_execution_requested"))
        )
    )
    if legal_bounded_request:
        return True
    if profile_intent in _UNBOUNDED_PROFILE_INTENTS or bool(studio_context.get("web_execution_requested")):
        return False
    return (
        profile_intent in _REQUEST_PROFILE_INTENTS
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
    workflow = _clean_spaces(response.metadata.get("workflow"))
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
    if workflow not in _STRICT_SOURCE_WORKFLOWS:
        return rows[:8]
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
    workflow = _clean_spaces(response.metadata.get("workflow"))
    restricted_sources = list(response.metadata.get("restricted_sources") or [])
    partner_sources = list(response.metadata.get("partner_sources") or [])
    evidence_count = int(summary.get("evidence_count") or 0)
    if workflow in {"economico", "cabina", "next_action", "telematico_status", "compliance"}:
        if response.answer_mode != "grounded":
            return "Risposta prudenziale: il percorso operativo e' disponibile, ma serve ancora una verifica sui dati dello studio prima di chiudere."
        if evidence_count:
            return "Base operativa di studio: riferimenti interni e percorso applicativo disponibili, senza bisogno di trasformare la risposta in ricerca legale."
        return "Base operativa minima: Lex ha individuato il flusso corretto, ma conviene ancora agganciare i dati interni della pratica."
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


def _attachment_needs_indexing_payload(
    *,
    current_user_message: str,
    resolved_effective_question: str,
    studio_context: dict[str, Any],
    attachments: list[dict[str, Any]],
) -> dict[str, Any]:
    reply = (
        "Non posso usare gli allegati come semplice testo libero nel prompt. "
        "Serve prima una lettura governata o un'indicizzazione riuscita del documento, "
        "cosi' Lex possa trasformarlo in evidenze verificabili."
    )
    payload = direct_answer_payload(
        current_user_message,
        reply,
        query_type="workflow_answer",
        sources=[],
        citations=[],
        legal_reference_guard_active=True,
    )
    payload.update(
        {
            "question": current_user_message,
            "effective_question": resolved_effective_question,
            "answer": reply,
            "warnings": [
                "Allegati presenti ma non trasformati in evidenze governate.",
                "Lex non riversa documenti nel prompt libero del modello.",
            ],
            "next_actions": [
                "Ricarica il documento con testo estraibile oppure abilita il parser/OCR governato.",
                "Se il documento appartiene a un fascicolo, indicizzalo nel fascicolo prima di chiedere una sintesi.",
            ],
            "risk_level": "medium",
            "confidence": 0.18,
            "confidence_label": "bassa",
            "confidence_reason": "Gli allegati non sono ancora evidenze citabili.",
            "answer_mode": "needs_review",
            "reference_label": _clean_spaces(studio_context.get("focus_label")),
            "focus_label": _clean_spaces(studio_context.get("focus_label")),
            "focus_topic": _clean_spaces(studio_context.get("focus_topic")),
            "disable_exports": True,
            "request_profile": dict(studio_context.get("request_profile") or {}),
            "source_policy_summary": dict(studio_context.get("source_policy_summary") or {}),
            "source_mode": _clean_spaces(studio_context.get("source_mode")),
            "workflow": "attachment_evidence",
            "provider": "guardrail",
            "considered_sources": [],
            "compared_sources": [],
            "missing_evidence": [
                "Testo allegato non disponibile come EvidenceItem.",
                f"Allegati ricevuti: {len(list(attachments or []))}.",
            ],
            "evidence_summary": {
                "evidence_count": 0,
                "attachment_count": len(list(attachments or [])),
                "attachment_evidence_count": 0,
                "evidence_sufficient": False,
            },
        }
    )
    return payload


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
    data = dict(data or {})
    studio_context = apply_manual_free_web_context(data, studio_context)
    free_web_enabled = _manual_free_web_enabled(data, studio_context)
    if not _should_use_bounded_workflow(attachments=attachments, studio_context=studio_context):
        return None

    request_profile = dict(studio_context.get("request_profile") or {})
    if free_web_enabled:
        request_profile["source_mode"] = "free_web"
        request_profile["needs_external_validation"] = True
    metadata = dict(data or {})
    workflow_hint = _resolve_workflow_hint(studio_context, request_profile)
    fascicolo_first = _is_fascicolo_first_request(data, studio_context, workflow_hint)
    external_reason = _external_sources_reason(
        resolved_effective_question,
        studio_context,
        request_profile,
        fascicolo_first=fascicolo_first,
    )
    if free_web_enabled:
        external_reason = "Ricerca web libera attivata manualmente dall'utente."
    allow_external_research = True if free_web_enabled else bool(external_reason) if fascicolo_first else bool(
        studio_context.get("web_execution_requested")
        or studio_context.get("web_fallback_used")
        or request_profile.get("needs_external_validation")
        or external_reason
        or not _has_internal_context(studio_context)
    )
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
            "free_web_enabled": free_web_enabled,
            "manual_free_web_enabled": free_web_enabled,
            "force_free_web_search": free_web_enabled,
            "public_web_forced": bool(free_web_enabled or metadata.get("public_web_forced")),
            "fascicolo_first": fascicolo_first,
            "external_sources_reason": external_reason,
            "studio_context_seed": {
                "sources": list(studio_context.get("sources") or []),
                "structured_context": dict(studio_context.get("structured_context") or {}),
                "focus_label": _clean_spaces(studio_context.get("focus_label")),
                "focus_topic": _clean_spaces(studio_context.get("focus_topic")),
                "request_profile": request_profile,
                "execution_policy": dict(studio_context.get("execution_policy") or {}),
                "source_policy_summary": dict(studio_context.get("source_policy_summary") or {}),
                "source_mode": _clean_spaces(studio_context.get("source_mode")),
                "web_fallback_used": bool(studio_context.get("web_fallback_used")),
                "web_execution_requested": bool(studio_context.get("web_execution_requested")),
                "free_web_enabled": free_web_enabled,
                "fascicolo_first": fascicolo_first,
                "external_sources_reason": external_reason,
            },
        }
    )
    if not list(attachments or []) and not free_web_enabled:
        try:
            from lex.operational_knowledge.integration import build_operational_http_payload

            operational_payload = build_operational_http_payload(
                user=user,
                studio=studio,
                data=metadata,
                current_user_message=current_user_message,
                resolved_effective_question=resolved_effective_question,
                studio_context=studio_context,
            )
            if operational_payload:
                return operational_payload
        except Exception:
            # The operational layer is optional and feature-flagged. Fail closed
            # into the existing governed Lex workflow if its own guard rejects.
            pass
    request = LexRequest(
        tenant_id=_tenant_id(studio, metadata),
        user_id=_user_id(user),
        session_id=_clean_spaces(data.get("session_id")) or "lex-http",
        query=resolved_effective_question,
        intent=_resolve_intent(resolved_effective_question, studio_context, request_profile),  # type: ignore[arg-type]
        fascicolo_id=_clean_spaces(data.get("fascicolo_id")) or None,
        document_id=_clean_spaces(data.get("document_id")) or None,
        workflow_hint=workflow_hint or None,
        metadata=metadata,
        allow_external_research=allow_external_research,
        require_citations=bool(
            request_profile.get("source_mode") == "strict"
            or _clean_spaces(studio_context.get("focus_topic")) in {"ricerca_legale", "archivio_sentenze", "sentenze_civili", "sentenze_web"}
        ),
        require_official_sources=False if free_web_enabled else bool(
            bool(external_reason)
            or _clean_spaces(request_profile.get("intent")) in _STRICT_OFFICIAL_INTENTS
            or _clean_spaces(studio_context.get("focus_topic")) in {"ricerca_legale", "archivio_sentenze", "sentenze_civili", "sentenze_web", "telematico"}
        ),
    )

    attachment_evidence = build_attachment_evidence(attachments, request=request, context=studio_context)
    attachment_source_rows = attachment_evidence_source_rows(attachment_evidence)
    if list(attachments or []) and not attachment_evidence:
        return _attachment_needs_indexing_payload(
            current_user_message=current_user_message,
            resolved_effective_question=resolved_effective_question,
            studio_context=studio_context,
            attachments=list(attachments or []),
        )
    if attachment_evidence:
        seed = dict(metadata.get("studio_context_seed") or {})
        seed_sources = list(seed.get("sources") or [])
        seed_sources.extend(attachment_source_rows)
        seed["sources"] = seed_sources
        seed.setdefault("attachment_evidence", attachment_source_rows)
        metadata["studio_context_seed"] = seed
        metadata["attachment_evidence_count"] = len(attachment_evidence)
        metadata["attachment_count"] = len(list(attachments or []))
        request.metadata = metadata

    response = _application_lex_service().ask(request)
    if not isinstance(response, LexResponse):
        return None

    citations: list[str] = []
    for item in list(attachment_evidence or []):
        label = _clean_spaces(getattr(item, "title", ""))
        if label and label not in citations:
            citations.append(label)
    for item in list(response.citations or []):
        label = _citation_label(item)
        if label and label not in citations:
            citations.append(label)
    sources = [*attachment_source_rows, *_source_rows(response)]
    external_sources_used = bool(
        response.metadata.get("external_sources_used")
        or response.metadata.get("fallback_triggered")
        or any(str(row.get("authority") or "").lower() in {"official_web", "fonte ufficiale"} for row in sources)
    )
    external_reason_payload = response.metadata.get("external_sources_reason") or external_reason
    if external_sources_used and not external_reason_payload:
        external_reason_payload = "La risposta ha usato una fonte esterna governata per integrare il contesto interno."
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
            "fascicolo_first": fascicolo_first,
            "external_sources_used": external_sources_used,
            "external_sources_reason": external_reason_payload,
            "disable_exports": bool(
                response.answer_mode != "grounded" or str(response.risk_level or "low") in {"high", "critical"}
            ),
            "execution_policy": dict(studio_context.get("execution_policy") or {}),
            "request_profile": request_profile,
            "source_policy_summary": dict(studio_context.get("source_policy_summary") or {}),
            "source_mode": _clean_spaces(studio_context.get("source_mode")),
            "free_web_enabled": free_web_enabled,
            "competence_labels": list(studio_context.get("competence_labels") or []),
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
