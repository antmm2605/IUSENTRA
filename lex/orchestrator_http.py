"""Compatibilita' HTTP legacy dell'orchestratore Lex."""

from __future__ import annotations

import json
import os
from io import BytesIO
from time import monotonic
from typing import Any

from flask import Response, current_app, send_file, stream_with_context

from .formatting.ui_payloads import (
    direct_answer_payload,
    followup_resolution_payload,
    routing_payload,
    social_context_payload,
)
from .http_bounded_bridge import apply_manual_free_web_context, build_bounded_http_payload
from .telemetry.audit import audit_trace

_TRUE_VALUES = {"1", "true", "vero", "yes", "si", "on", "enabled", "abilitato"}
_STUDIO_DATA_GUARD_BYPASS_INTENTS = {"cliente_anagrafica"}
_STUDIO_DATA_GUARD_BYPASS_TOPICS = {
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


def clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _should_bypass_documentary_source_guard(studio_context: dict[str, Any]) -> bool:
    """Le ricerche sui dati dello studio non sono ricerche da fonte pubblica."""
    if bool(studio_context.get("free_web_enabled")):
        return True
    request_profile = dict(studio_context.get("request_profile") or {})
    intent = clean_spaces(request_profile.get("intent")).lower()
    focus_topic = clean_spaces(studio_context.get("focus_topic")).lower()
    if intent in _STUDIO_DATA_GUARD_BYPASS_INTENTS:
        return True
    return focus_topic in _STUDIO_DATA_GUARD_BYPASS_TOPICS


def _raw_chat_enabled() -> bool:
    return clean_spaces(os.getenv("LEX_RAW_CHAT_ENABLED")).lower() in _TRUE_VALUES


def _allow_unbounded_generation(data: dict[str, Any]) -> bool:
    raw = data.get("allow_unbounded_generation")
    if raw is True:
        return True
    return clean_spaces(raw).lower() in _TRUE_VALUES


def _raw_chat_allowed(data: dict[str, Any]) -> bool:
    return _raw_chat_enabled() and _allow_unbounded_generation(data)


def _raw_chat_blocked_message() -> str:
    return (
        "Non posso rispondere in modalita' chat libera senza evidenze governate. "
        "Serve agganciare contesto, fonti o workflow prima di produrre una risposta affidabile."
    )


def _raw_chat_blocked_payload(
    *,
    question: str,
    effective_question: str,
    studio_context: dict[str, Any],
    allow_unbounded_generation: bool,
) -> dict[str, Any]:
    reply = _raw_chat_blocked_message()
    payload = direct_answer_payload(
        question,
        reply,
        query_type="governed_chat_blocked",
        sources=[],
        citations=[],
        legal_reference_guard_active=True,
    )
    payload.update(
        {
            "answer": reply,
            "effective_question": effective_question,
            "warnings": ["Chat libera disattivata: Lex richiede evidenze o workflow governato."],
            "next_actions": [
                "Seleziona un fascicolo, un documento, una fonte ufficiale o un flusso operativo prima di chiedere la risposta.",
            ],
            "risk_level": "medium",
            "confidence": 0.12,
            "confidence_label": "bassa",
            "confidence_reason": "La richiesta non ha prodotto un payload bounded e la generazione libera non e' abilitata.",
            "answer_mode": "needs_review",
            "disable_exports": True,
            "request_profile": studio_context.get("request_profile") or {},
            "source_policy_summary": studio_context.get("source_policy_summary") or {},
            "source_mode": clean_spaces(studio_context.get("source_mode")),
            "considered_sources": [],
            "compared_sources": [],
            "missing_evidence": ["Nessun payload bounded disponibile per questa richiesta."],
            "evidence_summary": {
                "evidence_count": 0,
                "evidence_sufficient": False,
                "raw_chat_enabled": _raw_chat_enabled(),
                "allow_unbounded_generation": allow_unbounded_generation,
            },
            "provider": "guardrail",
            "workflow": "governed_chat_blocked",
        }
    )
    return payload


def page_context_prompt_block(data: dict[str, Any]) -> str:
    label = clean_spaces(data.get("context_label"))
    page_context = clean_spaces(data.get("page_context"))
    page_path = clean_spaces(data.get("page_path"))
    if not (label or page_context or page_path):
        return ""
    parts: list[str] = []
    if label:
        parts.append(f"contesto dichiarato={label}")
    if page_context and page_context != label:
        parts.append(f"chiave pagina={page_context}")
    if page_path:
        parts.append(f"percorso={page_path}")
    return (
        "Contesto UI attivo: "
        + "; ".join(parts)
        + ". Usa questo contesto per dare priorita' alla pagina aperta dall'utente, senza inventare dati non presenti nelle fonti."
    )


def build_context_payload(
    orchestrator,
    *,
    effective_question: str,
    history_messages: list[dict[str, object]],
    routing,
    pratica_id: str = "",
    fascicolo_id: str = "",
    mode: str = "general",
) -> dict[str, Any]:
    return orchestrator.context_builder.build(
        question=effective_question,
        mode=mode,
        pratica_id=pratica_id,
        fascicolo_id=fascicolo_id,
        history_messages=history_messages,
        routing=routing,
        build_studio_context=orchestrator.dependencies.build_studio_context,
        build_today_summary=orchestrator.dependencies.build_today_summary,
    )


def followup_prompt_block(followup, *, free_web_enabled: bool = False) -> str:
    lines: list[str] = []
    if bool(getattr(followup, "reused_previous_topic", False)) and clean_spaces(getattr(followup, "previous_user_text", "")):
        lines.append(
            "Follow-up conversazionale: il tema utile e' gia' emerso nel turno precedente e va ereditato senza chiedere di nuovo l'argomento."
        )
    if bool(getattr(followup, "is_web_request", False)):
        if free_web_enabled:
            lines.append(
                "Ricerca web libera attiva: Lex deve cercare direttamente sul web pubblico senza allowlist ufficiale e senza blocchi da fonte autorizzata."
            )
        else:
            lines.append(
                "Richiesta web presa in carico: Lex deve controllare direttamente, usare fonti ufficiali pertinenti e riportare risultati concreti, non un elenco di siti da consultare."
            )
    if bool(getattr(followup, "needs_web_search", False)):
        lines.append(
            "In questa risposta il web va usato solo come supporto operativo mirato, dopo aver sfruttato il contesto interno utile."
        )
    return "\n".join(lines).strip()


def routing_prompt_block(routing, *, opening_line: str = "") -> str:
    lines: list[str] = []
    if bool(getattr(routing, "is_daily_overview", False)):
        lines.append(
            "Overview giornaliera: Lex deve costruire un quadro operativo di oggi ordinato per priorita', partendo da scadenze, udienze, agenda e fascicoli attivi."
        )
    if bool(getattr(routing, "is_followup", False)) and bool(getattr(routing, "reused_previous_topic", False)):
        lines.append("Follow-up breve: il contesto del turno precedente va riusato senza ripartire da zero.")
    clean_opening_line = clean_spaces(opening_line)
    if clean_opening_line:
        lines.append(
            "L'apertura iniziale e' gia' stata resa all'utente: dopo quel testo Lex deve continuare direttamente con il contenuto operativo senza ripetere il saluto."
        )
    return "\n".join(lines).strip()


def status_payload(orchestrator) -> tuple[dict[str, Any], int]:
    runtime = orchestrator.dependencies.resolved_runtime()
    api_base_url = str(runtime.get("api_base_url") or "").rstrip("/")
    base_url = str(runtime.get("base_url") or "").rstrip("/")
    chat_model = str(runtime.get("chat_model") or "mistral").strip() or "mistral"
    try:
        response = orchestrator.dependencies.requests_module.get(f"{api_base_url}/tags", timeout=3)
        models = [model["name"] for model in response.json().get("models", [])]
        return {
            "ok": True,
            "url": base_url,
            "modello_attivo": chat_model,
            "modelli": models,
        }, 200
    except orchestrator.dependencies.requests_module.exceptions.ConnectionError:
        return {
            "ok": False,
            "errore": "Ollama non raggiungibile",
            "suggerimento": "Avvia Ollama con: ollama serve",
            "modelli": [],
        }, 200
    except Exception as exc:
        return {"ok": False, "errore": str(exc), "modelli": []}, 200


def build_context_response(
    orchestrator,
    *,
    user,
    studio,
    data: dict[str, Any],
    resolve_messages,
) -> tuple[dict[str, Any], int]:
    orchestrator.auth_guard.ensure_can_access(
        user=user,
        studio=studio,
        pratica_id=str(data.get("pratica_id") or ""),
    )
    messages = list(data.get("messages", []) or [])[-12:]
    attachments = list(data.get("attachments") or [])
    fascicolo_id = clean_spaces(data.get("fascicolo_id"))
    mode = clean_spaces(data.get("mode")) or "general"
    current_user_message, previous_user_message, history_messages = resolve_messages(
        explicit_question=clean_spaces(data.get("question")),
        messages=messages,
    )
    if not current_user_message:
        return {"ok": False, "errore": "Domanda mancante.", "prompt": "", "sources": [], "citations": []}, 200

    routing = orchestrator.dependencies.resolve_social_and_operational_intent(
        current_user_message,
        previous_user_text=previous_user_message,
    )
    if routing.is_social_only:
        reply = orchestrator.dependencies.build_social_only_reply(routing.social_kind, routing.raw_text) or "Dimmi pure."
        payload = social_context_payload(current_user_message, reply)
        payload["routing"] = routing_payload(routing)
        payload["social_kind"] = routing.social_kind
        payload["social_prefix"] = routing.social_prefix
        return payload, 200

    base_question = str(routing.effective_query or current_user_message).strip() or current_user_message
    followup = orchestrator.dependencies.resolve_followup_query(
        base_question,
        previous_user_text=previous_user_message,
    )
    user_effective_question = str(followup.effective_query or base_question).strip() or base_question
    social_prefix = str(routing.social_prefix or "").strip() if routing.is_social_with_request else ""

    runtime = orchestrator.dependencies.resolved_runtime()
    studio_context = build_context_payload(
        orchestrator,
        effective_question=user_effective_question,
        history_messages=history_messages,
        routing=routing,
        pratica_id=str(data.get("pratica_id") or ""),
        fascicolo_id=fascicolo_id,
        mode=mode,
    )
    studio_context = apply_manual_free_web_context(data, studio_context)
    resolved_effective_question = str(studio_context.get("effective_question") or user_effective_question).strip() or user_effective_question
    direct_guard_reply = ""
    if not _should_bypass_documentary_source_guard(studio_context):
        direct_guard_reply = orchestrator.dependencies.build_unverified_pdf_reply(
            resolved_effective_question,
            studio_context.get("verified_legal_references") or studio_context.get("sources") or [],
        )
        if not direct_guard_reply:
            direct_guard_reply = clean_spaces(studio_context.get("answer_guardrail_message"))
    if direct_guard_reply:
        guard_prompt = orchestrator.dependencies.build_prompt(
            question=resolved_effective_question,
            fascicolo_id=fascicolo_id,
            messages=history_messages,
            studio_context=str(studio_context.get("prompt_block") or "").strip(),
            include_conversation=True,
            social_prefix="",
            social_kind=routing.social_kind,
            opening_line="",
        )
        payload = direct_answer_payload(
            current_user_message,
            direct_guard_reply,
            sources=studio_context.get("sources") or [],
            citations=studio_context.get("citations") or [],
            legal_reference_guard_active=True,
        )
        payload["routing"] = routing_payload(routing)
        payload["followup_resolution"] = followup_resolution_payload(followup)
        payload["effective_question"] = resolved_effective_question
        payload["prompt"] = guard_prompt
        payload["request_profile"] = studio_context.get("request_profile") or {}
        payload["source_policy_summary"] = studio_context.get("source_policy_summary") or {}
        payload["source_mode"] = str(studio_context.get("source_mode") or "").strip()
        payload["confidence_label"] = "bassa"
        payload["confidence_reason"] = clean_spaces(
            (studio_context.get("source_policy_summary") or {}).get("reasoning")
            or "Lex si e' fermato per prudenza: le fonti disponibili non bastano a una risposta forte."
        )
        return payload, 200

    prompt_question = resolved_effective_question
    web_execution_requested = bool(studio_context.get("web_execution_requested")) or bool(followup.is_web_request)
    language_guidance = orchestrator.dependencies.build_language_guidance(
        question=prompt_question,
        social_prefix=social_prefix,
        research_strategy=str(studio_context.get("research_strategy") or "").strip(),
        focus_topic=str(studio_context.get("focus_topic") or "").strip(),
        web_execution_requested=web_execution_requested,
        is_daily_overview=bool(routing.is_daily_overview),
    )
    opening_line = str(language_guidance.opening_line or "").strip()
    prompt_social_prefix = "" if opening_line else social_prefix
    web_fallback_used = bool(studio_context.get("web_fallback_used")) or bool(
        followup.is_web_request and followup.needs_web_search
    )
    studio_prompt_block = str(studio_context.get("prompt_block", "") or "").strip()
    studio_prompt_block = "\n\n".join(
        block
        for block in [
            studio_prompt_block,
            page_context_prompt_block(data),
            routing_prompt_block(routing, opening_line=opening_line),
            followup_prompt_block(followup, free_web_enabled=bool(studio_context.get("free_web_enabled"))),
            str(language_guidance.prompt_block or "").strip(),
        ]
        if block
    )
    prompt = orchestrator.dependencies.build_prompt(
        question=prompt_question,
        fascicolo_id=fascicolo_id,
        messages=history_messages,
        studio_context=studio_prompt_block,
        include_conversation=True,
        social_prefix=prompt_social_prefix,
        social_kind=routing.social_kind,
        opening_line=opening_line,
    )

    bounded_payload = build_bounded_http_payload(
        user=user,
        studio=studio,
        data=data,
        current_user_message=current_user_message,
        resolved_effective_question=resolved_effective_question,
        studio_context=studio_context,
        attachments=attachments,
    )
    if bounded_payload:
        bounded_payload["routing"] = routing_payload(routing)
        bounded_payload["followup_resolution"] = followup_resolution_payload(followup)
        free_web_payload = bool(bounded_payload.get("free_web_enabled") or studio_context.get("free_web_enabled"))
        context_sources = [] if free_web_payload else [
            dict(item) for item in list(studio_context.get("sources") or []) if isinstance(item, dict)
        ]
        if context_sources:
            bounded_payload["sources"] = context_sources
        context_citations = [] if free_web_payload else [
            clean_spaces(item) for item in list(studio_context.get("citations") or []) if clean_spaces(item)
        ]
        if context_citations:
            merged_citations = list(context_citations)
            for citation in list(bounded_payload.get("citations") or []):
                clean_citation = clean_spaces(citation)
                if clean_citation and clean_citation not in merged_citations:
                    merged_citations.append(clean_citation)
            bounded_payload["citations"] = merged_citations
        bounded_payload["prompt"] = clean_spaces(bounded_payload.get("prompt")) or prompt
        bounded_payload["language_mode"] = str(language_guidance.mode or "").strip()
        bounded_payload["opening_line"] = opening_line
        bounded_payload["web_execution_requested"] = web_execution_requested
        bounded_payload["web_fallback_used"] = bool(bounded_payload.get("web_fallback_used")) or web_fallback_used
        bounded_payload["social_kind"] = routing.social_kind
        bounded_payload["social_prefix"] = str(social_prefix or "").strip()
        bounded_payload["daily_overview_lead"] = opening_line
        bounded_payload["focus_label"] = str(studio_context.get("focus_label") or "").strip()
        bounded_payload["focus_topic"] = str(studio_context.get("focus_topic") or "").strip()
        bounded_payload["competence_labels"] = list(studio_context.get("competence_labels") or [])
        bounded_payload["execution_policy"] = studio_context.get("execution_policy") or {}
        bounded_payload["structured_context"] = {} if free_web_payload else (studio_context.get("structured_context") or {})
        bounded_payload["retrieval_sources"] = bounded_payload.get("retrieval_sources") or []
        return bounded_payload, 200

    if not _raw_chat_allowed(data):
        payload = _raw_chat_blocked_payload(
            question=current_user_message,
            effective_question=resolved_effective_question,
            studio_context=studio_context,
            allow_unbounded_generation=_allow_unbounded_generation(data),
        )
        payload["routing"] = routing_payload(routing)
        payload["followup_resolution"] = followup_resolution_payload(followup)
        payload["focus_label"] = str(studio_context.get("focus_label") or "").strip()
        payload["focus_topic"] = str(studio_context.get("focus_topic") or "").strip()
        payload["structured_context"] = studio_context.get("structured_context") or {}
        return payload, 200

    retrieval_sources = orchestrator.search_ranker.collect_and_rank(
        pratica_id=str(data.get("pratica_id") or ""),
        message=prompt_question,
        context=studio_context,
        mode=mode,
    )
    grounding = orchestrator.grounding_guard.evaluate(
        sources=studio_context.get("sources") or retrieval_sources
    )
    built = orchestrator.answer_builder.build_chat_payload(
        answer=orchestrator.output_guard.clean(answer="", grounding=grounding),
        sources=studio_context.get("sources") or retrieval_sources,
        grounding=grounding,
        mode=mode,
    )

    try:
        audit_trace(
            query=current_user_message,
            prompt_question=prompt_question,
            engine_ids=studio_context.get("engine_ids") or [],
            source_ids=studio_context.get("source_ids") or [],
            ai_model=runtime.get("chat_model") or "mistral",
            result_summary="Contesto assistente Lex preparato per il companion locale.",
            warning="La risposta finale viene generata sul dispositivo cliente tramite companion locale.",
        )
    except Exception:
        current_app.logger.exception("Errore audit assistente_context")

    built.update(
        {
            "query_type": "assistente_chat",
            "question": current_user_message,
            "effective_question": resolved_effective_question,
            "prompt": prompt,
            "attachments": attachments,
            "focus_label": str(studio_context.get("focus_label") or "").strip(),
            "focus_topic": str(studio_context.get("focus_topic") or "").strip(),
            "competence_labels": list(studio_context.get("competence_labels") or []),
            "web_fallback_used": web_fallback_used,
            "web_execution_requested": web_execution_requested,
            "social_kind": routing.social_kind,
            "social_prefix": str(social_prefix or "").strip(),
            "opening_line": opening_line,
            "daily_overview_lead": opening_line,
            "language_mode": str(language_guidance.mode or "").strip(),
            "legal_reference_guard_active": bool(studio_context.get("legal_reference_guard_active")),
            "verified_legal_references": studio_context.get("verified_legal_references") or [],
            "disable_exports": False,
            "execution_policy": studio_context.get("execution_policy") or {},
            "routing": routing_payload(routing),
            "followup_resolution": followup_resolution_payload(followup),
            "structured_context": studio_context.get("structured_context") or {},
            "retrieval_sources": retrieval_sources,
            "request_profile": studio_context.get("request_profile") or {},
            "source_policy_summary": studio_context.get("source_policy_summary") or {},
            "source_mode": str(studio_context.get("source_mode") or "").strip(),
            "confidence_label": grounding.confidence_label,
            "confidence_reason": grounding.reasoning,
        }
    )
    return built, 200


def warmup_response(orchestrator, *, question: str, context_label: str) -> tuple[dict[str, Any], int]:
    warmed = orchestrator.dependencies.warm_studio_context(question=question, context_label=context_label)
    runtime = orchestrator.dependencies.warm_runtime()
    return {
        "ok": True,
        "prewarmed": True,
        "sources_ready": len(warmed.get("sources") or []),
        "runtime": runtime,
    }, 200


def attachments_response(orchestrator, *, files: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
    attachments, errors = orchestrator.dependencies.parse_attachment_payloads(files or [])
    return {
        "ok": True,
        "attachments": attachments,
        "errors": errors,
        "prompt_block": "",
        "evidence_mode": "attachment_evidence",
        "evidence_count": len([item for item in attachments if clean_spaces(item.get("text_excerpt"))]),
    }, 200


def document_response(orchestrator, *, data: dict[str, Any]):
    answer = clean_spaces(data.get("answer"))
    if not answer:
        return {"ok": False, "errore": "Contenuto del documento mancante."}, 400
    title = orchestrator.dependencies.infer_export_title(
        title=str(data.get("title") or ""),
        question=str(data.get("question") or ""),
        answer=answer,
    )
    citations = data.get("citations") or []
    context_label = str(data.get("context_label") or "").strip()
    docx_bytes = orchestrator.dependencies.build_docx_bytes(
        title=title,
        question=str(data.get("question") or ""),
        answer=answer,
        citations=citations if isinstance(citations, list) else [],
        context_label=context_label,
    )
    file_name = orchestrator.dependencies.build_export_filename(title, "docx")
    return send_file(
        BytesIO(docx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=file_name,
    )


def chat_response(
    orchestrator,
    *,
    user,
    studio,
    data: dict[str, Any],
    resolve_messages,
    messages_with_effective_question,
):
    orchestrator.auth_guard.ensure_can_access(
        user=user,
        studio=studio,
        pratica_id=str(data.get("pratica_id") or ""),
    )
    messages = list(data.get("messages", []) or [])[-12:]
    attachments = list(data.get("attachments") or [])
    fascicolo_id = str(data.get("fascicolo_id", "") or "")
    mode = clean_spaces(data.get("mode")) or "general"
    current_user_message, previous_user_text, history_messages = resolve_messages(
        explicit_question="",
        messages=messages,
    )
    routing = orchestrator.dependencies.resolve_social_and_operational_intent(
        current_user_message,
        previous_user_text=previous_user_text,
    )
    if routing.is_social_only:
        reply = orchestrator.dependencies.build_social_only_reply(routing.social_kind, routing.raw_text) or "Dimmi pure."

        def generate_social():
            yield f"data: {json.dumps({'token': reply})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate_social()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    base_question = str(routing.effective_query or current_user_message).strip() or "Richiesta operativa"
    followup = orchestrator.dependencies.resolve_followup_query(
        base_question,
        previous_user_text=previous_user_text,
    )
    user_effective_question = str(followup.effective_query or base_question).strip() or "Richiesta operativa"
    social_prefix = str(routing.social_prefix or "").strip() if routing.is_social_with_request else ""
    runtime = orchestrator.dependencies.resolved_runtime()
    api_base_url = str(runtime.get("api_base_url") or "").rstrip("/")
    base_url = str(runtime.get("base_url") or "").rstrip("/")
    studio_context = build_context_payload(
        orchestrator,
        effective_question=user_effective_question,
        history_messages=history_messages,
        routing=routing,
        pratica_id=str(data.get("pratica_id") or ""),
        fascicolo_id=fascicolo_id,
        mode=mode,
    )
    studio_context = apply_manual_free_web_context(data, studio_context)
    resolved_effective_question = str(studio_context.get("effective_question") or user_effective_question).strip() or "Richiesta operativa"
    direct_guard_reply = ""
    if not _should_bypass_documentary_source_guard(studio_context):
        direct_guard_reply = orchestrator.dependencies.build_unverified_pdf_reply(
            resolved_effective_question,
            studio_context.get("verified_legal_references") or studio_context.get("sources") or [],
        )
        if not direct_guard_reply:
            direct_guard_reply = clean_spaces(studio_context.get("answer_guardrail_message"))
    if direct_guard_reply:
        def generate_direct():
            yield f"data: {json.dumps({'token': direct_guard_reply})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate_direct()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    bounded_payload = build_bounded_http_payload(
        user=user,
        studio=studio,
        data=data,
        current_user_message=current_user_message,
        resolved_effective_question=resolved_effective_question,
        studio_context=studio_context,
        attachments=attachments,
    )
    if bounded_payload:
        direct_answer = str(bounded_payload.get("answer") or "").replace("\r", "").strip()

        def generate_bounded():
            yield f"data: {json.dumps({'token': direct_answer})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate_bounded()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    if not _raw_chat_allowed(data):
        direct_answer = _raw_chat_blocked_message()

        def generate_blocked():
            yield f"data: {json.dumps({'token': direct_answer})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate_blocked()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    allow_web_search = bool(data.get("allow_web_search")) or bool(data.get("web_search"))
    language_guidance = orchestrator.dependencies.build_language_guidance(
        question=resolved_effective_question,
        social_prefix=social_prefix,
        research_strategy=str(studio_context.get("research_strategy") or "").strip(),
        focus_topic=str(studio_context.get("focus_topic") or "").strip(),
        web_execution_requested=bool(studio_context.get("web_execution_requested")) or bool(followup.is_web_request) or allow_web_search,
        is_daily_overview=bool(routing.is_daily_overview),
    )
    stream_opening_line = str(language_guidance.opening_line or "").strip() or social_prefix
    rewrite_last_user_message = bool(followup.reused_previous_topic or routing.reused_previous_topic)
    llm_messages = (
        messages_with_effective_question(
            messages,
            effective_question=resolved_effective_question,
            original_question=current_user_message,
        )
        if rewrite_last_user_message
        else [dict(item or {}) for item in messages]
    )
    studio_prompt_block = str(studio_context.get("prompt_block", "") or "").strip()
    studio_prompt_block = "\n\n".join(
        block
        for block in [
            studio_prompt_block,
            page_context_prompt_block(data),
            routing_prompt_block(routing, opening_line=stream_opening_line),
            followup_prompt_block(followup, free_web_enabled=bool(studio_context.get("free_web_enabled"))),
            str(language_guidance.prompt_block or "").strip(),
        ]
        if block
    )
    system_content = orchestrator.dependencies.build_prompt(
        question=resolved_effective_question,
        fascicolo_id=fascicolo_id,
        messages=history_messages,
        studio_context=studio_prompt_block,
        social_prefix="",
        social_kind=routing.social_kind,
        opening_line="",
    )

    payload = orchestrator.llm_provider.build_chat_payload(
        runtime=runtime,
        llm_messages=llm_messages,
        system_content=system_content,
    )

    try:
        audit_trace(
            query=current_user_message or "Richiesta assistente PCT",
            prompt_question=resolved_effective_question,
            engine_ids=studio_context.get("engine_ids") or [],
            source_ids=studio_context.get("source_ids") or [],
            ai_model=str(runtime.get("chat_model") or "mistral"),
            result_summary="Richiesta inviata all'assistente Lex.",
            warning="Risposta generativa locale: verificare sempre le fonti ufficiali prima dell'uso professionale.",
        )
    except Exception:
        current_app.logger.exception("Errore audit assistente_chat")

    metrics_registry = current_app.extensions.get("runtime_metrics")
    started_at = monotonic()
    generator = orchestrator.llm_provider.stream_chat(
        requests_module=orchestrator.dependencies.requests_module,
        api_base_url=api_base_url,
        payload=payload,
        base_url=base_url,
        opening_line=stream_opening_line,
        on_first_token=(
            (lambda elapsed_ms: metrics_registry.observe_lex_first_token(elapsed_ms))
            if metrics_registry is not None
            else None
        ),
        started_at=started_at,
    )
    return Response(
        stream_with_context(generator()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
