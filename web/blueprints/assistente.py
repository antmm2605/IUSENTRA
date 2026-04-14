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
from web.services.assistente_prompt import (
    build_assistente_prompt,
    latest_user_message,
)
from web.services.assistente_studio_context import build_lex_studio_context, warm_lex_studio_context
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
    question = str(data.get("question", "") or "").strip() or latest_user_message(messages)
    history_messages = messages[:-1] if question and latest_user_message(messages) == question else messages
    if not question:
        return {"ok": False, "errore": "Domanda mancante.", "prompt": "", "sources": [], "citations": []}, 200

    runtime = resolved_ollama_runtime()
    studio_context = build_lex_studio_context(question, mode="chat", messages=history_messages)
    effective_question = str(studio_context.get("effective_question") or question).strip() or question
    prompt = build_assistente_prompt(
        question=effective_question,
        fascicolo_id=fascicolo_id,
        messages=history_messages,
        studio_context=studio_context.get("prompt_block", ""),
        include_conversation=True,
    )
    if attachments:
        prompt += "\n\n" + build_attachment_prompt_block(attachments)

    try:
        get_legal_intelligence().registra_trace_risposta(
            query=question,
            user=getattr(g.get("utente_corrente"), "username", ""),
            engine_ids=studio_context.get("engine_ids") or motori_per_query(effective_question),
            source_ids=studio_context.get("source_ids") or fonti_per_query(effective_question),
            ai_model=runtime.get("chat_model") or "mistral",
            result_summary="Contesto assistente Lex preparato per il companion locale.",
            warning="La risposta finale viene generata sul dispositivo cliente tramite companion locale.",
        )
    except Exception:
        current_app.logger.exception("Errore audit assistente_context")

    return {
        "ok": True,
        "query_type": "assistente_chat",
        "question": question,
        "prompt": prompt,
        "sources": studio_context.get("sources") or [],
        "citations": studio_context.get("citations") or [],
        "attachments": attachments,
        "focus_label": str(studio_context.get("focus_label") or "").strip(),
        "focus_topic": str(studio_context.get("focus_topic") or "").strip(),
        "web_fallback_used": bool(studio_context.get("web_fallback_used")),
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
    last_user_message = latest_user_message(messages)
    history_messages = messages[:-1] if last_user_message and latest_user_message(messages) == last_user_message else messages
    runtime = resolved_ollama_runtime()
    api_base_url = str(runtime.get("api_base_url") or "").rstrip("/")
    base_url = str(runtime.get("base_url") or "").rstrip("/")
    chat_model = str(runtime.get("chat_model") or "mistral").strip() or "mistral"
    keep_alive = str(runtime.get("keep_alive") or "10m").strip() or "10m"
    studio_context = build_lex_studio_context(last_user_message, mode="chat", messages=history_messages)
    effective_question = str(studio_context.get("effective_question") or last_user_message).strip() or "Richiesta operativa"

    # System prompt + eventuale contesto fascicolo
    system_content = build_assistente_prompt(
        question=effective_question,
        fascicolo_id=fascicolo_id,
        messages=history_messages,
        studio_context=studio_context.get("prompt_block", ""),
    )
    if attachments:
        system_content += "\n\n" + build_attachment_prompt_block(attachments)

    payload = {
        "model": chat_model,
        "messages": [{"role": "system", "content": system_content}] + messages,
        "stream": True,
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0.3,   # risposte più precise/deterministiche
            "num_ctx": 4096,
        },
    }

    try:
        get_legal_intelligence().registra_trace_risposta(
            query=last_user_message or "Richiesta assistente PCT",
            user=getattr(g.get("utente_corrente"), "username", ""),
            engine_ids=studio_context.get("engine_ids") or motori_per_query(effective_question),
            source_ids=studio_context.get("source_ids") or fonti_per_query(effective_question),
            ai_model=chat_model,
            result_summary="Richiesta inviata all'assistente Lex.",
            warning="Risposta generativa locale: verificare sempre le fonti ufficiali prima dell'uso professionale.",
        )
    except Exception:
        current_app.logger.exception("Errore audit assistente_chat")

    def generate():
        try:
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
