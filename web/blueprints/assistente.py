"""
web/blueprints/assistente.py — Assistente virtuale PCT (Lex).

Integrazione Ollama locale — nessuna API key esterna richiesta.
Modello consigliato: mistral, llama3.2, phi3 (configurabile via PCT_OLLAMA_MODEL)

Route:
    GET  /api/assistente/stato   → verifica Ollama + modelli disponibili
    POST /api/assistente/chat    → chat streaming (Server-Sent Events)
"""
from __future__ import annotations

import json
from io import BytesIO

import requests
from flask import (
    Blueprint,
    Response,
    current_app,
    g,
    request,
    send_file,
    stream_with_context,
)

from web.helpers import get_legal_intelligence
from web.services.assistente_language_guidance import build_language_guidance
from web.services.assistente_prompt import build_assistente_prompt
from web.services.assistente_followup import resolve_followup_query
from web.services.assistente_social_intent import (
    build_social_only_reply,
    latest_user_message,
    resolve_social_and_operational_intent,
)
from web.services.assistente_studio_context import build_lex_studio_context, warm_lex_studio_context
from web.services.assistente_today_summary import build_today_operational_summary
from web.services.assistente_document_export import (
    build_docx_bytes,
    build_export_filename,
    infer_export_title,
)
from web.services.ollama_runtime import (
    resolved_ollama_runtime,
    warm_ollama_chat_runtime,
)
from pct.legal_intelligence import fonti_per_query, motori_per_query
from tools.lex_document_context import build_attachment_prompt_block, parse_attachment_payloads

assistente = Blueprint("assistente", __name__)


def _richiedi_login(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return {"errore": "non autenticato"}, 401
        return fn(*args, **kwargs)

    return wrapper


def _normalized_attachments(raw: list[dict[str, object]] | None) -> list[dict[str, object]]:
    attachments: list[dict[str, object]] = []
    for item in list(raw or []):
        excerpt = str(item.get("text_excerpt") or "").strip()
        if not excerpt:
            continue
        attachments.append(
            {
                "id": str(item.get("id") or "").strip(),
                "name": str(item.get("name") or "Documento").strip() or "Documento",
                "mime_type": str(item.get("mime_type") or "").strip(),
                "size_bytes": item.get("size_bytes") or 0,
                "page_count": item.get("page_count"),
                "text_excerpt": excerpt,
                "text_chars": item.get("text_chars") or len(excerpt),
                "truncated": bool(item.get("truncated")),
            }
        )
    return attachments


def _messages_with_effective_question(
    messages: list[dict[str, object]] | None,
    *,
    effective_question: str,
    original_question: str,
) -> list[dict[str, object]]:
    normalized = [dict(item or {}) for item in list(messages or [])]
    if not normalized:
        return []
    clean_effective = str(effective_question or "").strip()
    clean_original = str(original_question or "").strip()
    if not clean_effective or clean_effective == clean_original:
        return normalized

    for idx in range(len(normalized) - 1, -1, -1):
        role = str(normalized[idx].get("role") or "").strip().lower()
        if role != "user":
            continue
        normalized[idx]["content"] = clean_effective
        break
    return normalized


def _social_context_payload(question: str, reply: str) -> dict[str, object]:
    return {
        "ok": True,
        "query_type": "social_only",
        "question": "",
        "prompt": "",
        "answer": reply,
        "sources": [],
        "citations": [],
        "attachments": [],
        "focus_label": "",
        "focus_topic": "sociale",
        "web_fallback_used": False,
        "social_kind": "social_only",
        "social_prefix": "",
        "effective_question": "",
        "routing": {
            "reason": "social_only",
            "is_social_only": True,
            "is_social_with_request": False,
            "is_daily_overview": False,
            "is_followup": False,
            "reused_previous_topic": False,
            "social_kind": "social_only",
            "social_prefix": "",
            "request_text": "",
            "effective_query": "",
        },
        "followup_resolution": {
            "effective_query": "",
            "is_followup": False,
            "is_web_request": False,
            "needs_web_search": False,
            "reused_previous_topic": False,
            "reason": "social_only",
        },
    }


def _resolve_current_and_previous_user_messages(
    *,
    explicit_question: str,
    messages: list[dict[str, object]] | None,
) -> tuple[str, str, list[dict[str, object]]]:
    normalized_messages = [dict(item or {}) for item in list(messages or [])]
    current_from_messages = latest_user_message(normalized_messages)
    current_explicit = str(explicit_question or "").strip()

    if current_explicit and current_explicit != current_from_messages:
        return current_explicit, current_from_messages, normalized_messages

    current_user_message = current_explicit or current_from_messages
    if current_user_message and current_from_messages == current_user_message:
        history_messages = normalized_messages[:-1]
        previous_user_message = latest_user_message(normalized_messages, skip_last=True)
        return current_user_message, previous_user_message, history_messages

    previous_user_message = latest_user_message(normalized_messages, skip_last=True)
    return current_user_message, previous_user_message, normalized_messages


def _routing_payload(routing) -> dict[str, object]:
    return {
        "reason": str(routing.reason or "").strip(),
        "is_social_only": bool(routing.is_social_only),
        "is_social_with_request": bool(routing.is_social_with_request),
        "is_daily_overview": bool(routing.is_daily_overview),
        "is_followup": bool(routing.is_followup),
        "reused_previous_topic": bool(routing.reused_previous_topic),
        "social_kind": str(routing.social_kind or "").strip(),
        "social_prefix": str(routing.social_prefix or "").strip(),
        "request_text": str(routing.request_text or "").strip(),
        "effective_query": str(routing.effective_query or "").strip(),
    }


def _followup_resolution_payload(followup) -> dict[str, object]:
    return {
        "effective_query": str(followup.effective_query or "").strip(),
        "is_followup": bool(followup.is_followup),
        "is_web_request": bool(followup.is_web_request),
        "needs_web_search": bool(followup.needs_web_search),
        "reused_previous_topic": bool(followup.reused_previous_topic),
        "reason": str(followup.reason or "").strip(),
    }


def _followup_prompt_block(followup) -> str:
    lines: list[str] = []
    if bool(followup.reused_previous_topic) and str(followup.previous_user_text or "").strip():
        lines.append(
            "Follow-up conversazionale: il tema utile e' gia' emerso nel turno precedente e va ereditato senza chiedere di nuovo l'argomento."
        )
    if bool(followup.is_web_request):
        lines.append(
            "Richiesta web presa in carico: Lex deve controllare direttamente, usare fonti ufficiali pertinenti e riportare risultati concreti, non un elenco di siti da consultare."
        )
    if bool(followup.needs_web_search):
        lines.append(
            "In questa risposta il web va usato solo come supporto operativo mirato, dopo aver sfruttato il contesto interno utile."
        )
    return "\n".join(lines).strip()


def _routing_prompt_block(routing, *, opening_line: str = "") -> str:
    lines: list[str] = []
    if bool(routing.is_daily_overview):
        lines.append(
            "Overview giornaliera: Lex deve costruire un quadro operativo di oggi ordinato per priorita', partendo da scadenze, udienze, agenda e fascicoli attivi."
        )
    if bool(routing.is_followup) and bool(routing.reused_previous_topic):
        lines.append(
            "Follow-up breve: il contesto del turno precedente va riusato senza ripartire da zero."
        )
    clean_opening_line = str(opening_line or "").strip()
    if clean_opening_line:
        lines.append(
            "L'apertura iniziale e' gia' stata resa all'utente: dopo quel testo Lex deve continuare direttamente con il contenuto operativo senza ripetere il saluto."
        )
    return "\n".join(lines).strip()


def _build_context_payload(
    *,
    effective_question: str,
    history_messages: list[dict[str, object]],
    routing,
) -> dict[str, object]:
    if bool(routing.is_daily_overview):
        return build_today_operational_summary(question=effective_question)
    return build_lex_studio_context(effective_question, mode="chat", messages=history_messages)


# ── Route: stato ──────────────────────────────────────────────────────────────

@assistente.route("/api/assistente/stato")
@_richiedi_login
def assistente_stato():
    try:
        runtime = resolved_ollama_runtime()
        api_base_url = str(runtime.get("api_base_url") or "").rstrip("/")
        base_url = str(runtime.get("base_url") or "").rstrip("/")
        chat_model = str(runtime.get("chat_model") or "mistral").strip() or "mistral"
        r = requests.get(f"{api_base_url}/tags", timeout=3)
        modelli = [m["name"] for m in r.json().get("models", [])]
        return {
            "ok": True,
            "url": base_url,
            "modello_attivo": chat_model,
            "modelli": modelli,
        }
    except requests.exceptions.ConnectionError:
        return {
            "ok": False,
            "errore": "Ollama non raggiungibile",
            "suggerimento": "Avvia Ollama con: ollama serve",
            "modelli": [],
        }, 200
    except Exception as e:
        return {"ok": False, "errore": str(e), "modelli": []}, 200


@assistente.route("/api/assistente/context", methods=["POST"])
@_richiedi_login
def assistente_context():
    data = request.get_json(silent=True) or {}
    messages = list(data.get("messages", []) or [])[-12:]
    attachments = _normalized_attachments(data.get("attachments"))
    fascicolo_id = str(data.get("fascicolo_id", "") or "").strip()
    current_user_message, previous_user_message, history_messages = _resolve_current_and_previous_user_messages(
        explicit_question=str(data.get("question", "") or "").strip(),
        messages=messages,
    )
    if not current_user_message:
        return {"ok": False, "errore": "Domanda mancante.", "prompt": "", "sources": [], "citations": []}, 200

    routing = resolve_social_and_operational_intent(
        current_user_message,
        previous_user_text=previous_user_message,
    )
    if routing.is_social_only:
        reply = build_social_only_reply(routing.social_kind, routing.raw_text) or "Dimmi pure."
        payload = _social_context_payload(current_user_message, reply)
        payload["routing"] = _routing_payload(routing)
        payload["social_kind"] = routing.social_kind
        payload["social_prefix"] = routing.social_prefix
        return payload, 200

    base_question = str(routing.effective_query or current_user_message).strip() or current_user_message
    followup = resolve_followup_query(
        base_question,
        previous_user_text=previous_user_message,
    )
    user_effective_question = str(followup.effective_query or base_question).strip() or base_question
    social_prefix = str(routing.social_prefix or "").strip() if routing.is_social_with_request else ""

    runtime = resolved_ollama_runtime()
    studio_context = _build_context_payload(
        effective_question=user_effective_question,
        history_messages=history_messages,
        routing=routing,
    )
    resolved_effective_question = str(studio_context.get("effective_question") or user_effective_question).strip() or user_effective_question
    prompt_question = resolved_effective_question
    web_execution_requested = bool(studio_context.get("web_execution_requested")) or bool(followup.is_web_request)
    language_guidance = build_language_guidance(
        question=prompt_question,
        social_prefix=social_prefix,
        research_strategy=str(studio_context.get("research_strategy") or "").strip(),
        focus_topic=str(studio_context.get("focus_topic") or "").strip(),
        web_execution_requested=web_execution_requested,
        is_daily_overview=bool(routing.is_daily_overview),
    )
    opening_line = str(language_guidance.opening_line or "").strip()
    prompt_social_prefix = "" if opening_line else social_prefix
    followup_block = _followup_prompt_block(followup)
    routing_block = _routing_prompt_block(routing, opening_line=opening_line)
    web_fallback_used = bool(studio_context.get("web_fallback_used")) or bool(
        followup.is_web_request and followup.needs_web_search
    )
    studio_prompt_block = str(studio_context.get("prompt_block", "") or "").strip()
    studio_prompt_block = "\n\n".join(
        block
        for block in [studio_prompt_block, routing_block, followup_block, str(language_guidance.prompt_block or "").strip()]
        if block
    )
    prompt = build_assistente_prompt(
        question=prompt_question,
        fascicolo_id=fascicolo_id,
        messages=history_messages,
        studio_context=studio_prompt_block,
        include_conversation=True,
        social_prefix=prompt_social_prefix,
        social_kind=routing.social_kind,
        opening_line=opening_line,
    )
    if attachments:
        prompt += "\n\n" + build_attachment_prompt_block(attachments)

    try:
        get_legal_intelligence().registra_trace_risposta(
            query=current_user_message,
            user=getattr(g.get("utente_corrente"), "username", ""),
            engine_ids=studio_context.get("engine_ids") or motori_per_query(prompt_question),
            source_ids=studio_context.get("source_ids") or fonti_per_query(prompt_question),
            ai_model=runtime.get("chat_model") or "mistral",
            result_summary="Contesto assistente Lex preparato per il companion locale.",
            warning="La risposta finale viene generata sul dispositivo cliente tramite companion locale.",
        )
    except Exception:
        current_app.logger.exception("Errore audit assistente_context")

    return {
        "ok": True,
        "query_type": "assistente_chat",
        "question": current_user_message,
        "effective_question": resolved_effective_question,
        "prompt": prompt,
        "sources": studio_context.get("sources") or [],
        "citations": studio_context.get("citations") or [],
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
        "routing": _routing_payload(routing),
        "followup_resolution": _followup_resolution_payload(followup),
    }, 200


@assistente.route("/api/assistente/warmup", methods=["POST"])
@_richiedi_login
def assistente_warmup():
    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "") or "").strip()
    context_label = str(data.get("context_label", "") or "").strip()
    warmed = warm_lex_studio_context(question=question, context_label=context_label)
    runtime = warm_ollama_chat_runtime()
    return {
        "ok": True,
        "prewarmed": True,
        "sources_ready": len(warmed.get("sources") or []),
        "runtime": runtime,
    }, 200


@assistente.route("/api/assistente/attachments", methods=["POST"])
@_richiedi_login
def assistente_attachments():
    data = request.get_json(silent=True) or {}
    attachments, errors = parse_attachment_payloads(data.get("files") or [])
    return {
        "ok": True,
        "attachments": attachments,
        "errors": errors,
        "prompt_block": build_attachment_prompt_block(attachments),
    }, 200


@assistente.route("/api/assistente/documento", methods=["POST"])
@_richiedi_login
def assistente_documento():
    try:
        data = request.get_json(silent=True) or {}
        answer = str(data.get("answer") or "").strip()
        if not answer:
            return {"ok": False, "errore": "Contenuto del documento mancante."}, 400

        title = infer_export_title(
            title=str(data.get("title") or ""),
            question=str(data.get("question") or ""),
            answer=answer,
        )
        citations = data.get("citations") or []
        context_label = str(data.get("context_label") or "").strip()
        docx_bytes = build_docx_bytes(
            title=title,
            question=str(data.get("question") or ""),
            answer=answer,
            citations=citations if isinstance(citations, list) else [],
            context_label=context_label,
        )
        file_name = build_export_filename(title, "docx")
        return send_file(
            BytesIO(docx_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=file_name,
        )
    except Exception as exc:
        current_app.logger.exception("Errore assistente_documento: %s", exc)
        return {"ok": False, "errore": str(exc)}, 200


# ── Route: chat (streaming SSE) ───────────────────────────────────────────────

@assistente.route("/api/assistente/chat", methods=["POST"])
@_richiedi_login
def assistente_chat():
    data = request.get_json(silent=True) or {}
    messages: list = list(data.get("messages", []) or [])[-12:]
    attachments = _normalized_attachments(data.get("attachments"))
    fascicolo_id: str = data.get("fascicolo_id", "")
    current_user_message, previous_user_text, history_messages = _resolve_current_and_previous_user_messages(
        explicit_question="",
        messages=messages,
    )
    routing = resolve_social_and_operational_intent(
        current_user_message,
        previous_user_text=previous_user_text,
    )
    if routing.is_social_only:
        reply = build_social_only_reply(routing.social_kind, routing.raw_text) or "Dimmi pure."

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
    followup = resolve_followup_query(
        base_question,
        previous_user_text=previous_user_text,
    )
    user_effective_question = str(followup.effective_query or base_question).strip() or "Richiesta operativa"
    social_prefix = str(routing.social_prefix or "").strip() if routing.is_social_with_request else ""
    runtime = resolved_ollama_runtime()
    api_base_url = str(runtime.get("api_base_url") or "").rstrip("/")
    base_url = str(runtime.get("base_url") or "").rstrip("/")
    chat_model = str(runtime.get("chat_model") or "mistral").strip() or "mistral"
    keep_alive = str(runtime.get("keep_alive") or "10m").strip() or "10m"
    studio_context = _build_context_payload(
        effective_question=user_effective_question,
        history_messages=history_messages,
        routing=routing,
    )
    resolved_effective_question = str(studio_context.get("effective_question") or user_effective_question).strip() or "Richiesta operativa"
    prompt_question = resolved_effective_question
    language_guidance = build_language_guidance(
        question=prompt_question,
        social_prefix=social_prefix,
        research_strategy=str(studio_context.get("research_strategy") or "").strip(),
        focus_topic=str(studio_context.get("focus_topic") or "").strip(),
        web_execution_requested=bool(studio_context.get("web_execution_requested")) or bool(followup.is_web_request),
        is_daily_overview=bool(routing.is_daily_overview),
    )
    stream_opening_line = str(language_guidance.opening_line or "").strip() or social_prefix
    rewrite_last_user_message = bool(followup.reused_previous_topic or routing.reused_previous_topic)
    llm_messages = (
        _messages_with_effective_question(
            messages,
            effective_question=resolved_effective_question,
            original_question=current_user_message,
        )
        if rewrite_last_user_message
        else [dict(item or {}) for item in messages]
    )
    followup_block = _followup_prompt_block(followup)
    routing_block = _routing_prompt_block(routing, opening_line=stream_opening_line)
    studio_prompt_block = str(studio_context.get("prompt_block", "") or "").strip()
    studio_prompt_block = "\n\n".join(
        block
        for block in [studio_prompt_block, routing_block, followup_block, str(language_guidance.prompt_block or "").strip()]
        if block
    )

    # System prompt + eventuale contesto fascicolo
    system_content = build_assistente_prompt(
        question=prompt_question,
        fascicolo_id=fascicolo_id,
        messages=history_messages,
        studio_context=studio_prompt_block,
        social_prefix="",
        social_kind=routing.social_kind,
        opening_line="",
    )
    if attachments:
        system_content += "\n\n" + build_attachment_prompt_block(attachments)

    payload = {
        "model": chat_model,
        "messages": [{"role": "system", "content": system_content}] + llm_messages,
        "stream": True,
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0.3,   # risposte più precise/deterministiche
            "num_ctx": 4096,
        },
    }

    try:
        get_legal_intelligence().registra_trace_risposta(
            query=current_user_message or "Richiesta assistente PCT",
            user=getattr(g.get("utente_corrente"), "username", ""),
            engine_ids=studio_context.get("engine_ids") or motori_per_query(prompt_question),
            source_ids=studio_context.get("source_ids") or fonti_per_query(prompt_question),
            ai_model=chat_model,
            result_summary="Richiesta inviata all'assistente Lex.",
            warning="Risposta generativa locale: verificare sempre le fonti ufficiali prima dell'uso professionale.",
        )
    except Exception:
        current_app.logger.exception("Errore audit assistente_chat")

    def generate():
        try:
            prefixed = False
            if stream_opening_line:
                yield f"data: {json.dumps({'token': stream_opening_line + ' '})}\n\n"
                prefixed = True
            r = requests.post(
                f"{api_base_url}/chat",
                json=payload,
                stream=True,
                timeout=180,
            )
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
                except (json.JSONDecodeError, KeyError):
                    continue
        except requests.exceptions.ConnectionError:
            msg = (
                "Ollama non è raggiungibile. "
                "Assicurati che Ollama sia avviato con: `ollama serve`\n"
                f"URL configurato: {base_url}"
            )
            yield f"data: {json.dumps({'errore': msg})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'errore': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disabilita il buffering Nginx per SSE
            "Connection": "keep-alive",
        },
    )
