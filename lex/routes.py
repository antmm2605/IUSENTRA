"""Route Flask del modulo Lex."""

from __future__ import annotations

from typing import Callable

from flask import Blueprint, g, redirect, request, url_for

from .service import LexService


def register_routes(
    bp: Blueprint,
    *,
    service: LexService,
    login_required: Callable | None = None,
) -> None:
    guard = login_required or (lambda fn: fn)

    @guard
    def lex_chat_page():
        user = g.get("utente_corrente")
        if not user:
            return redirect(url_for("auth.login"))
        return (
            {
                "ok": False,
                "code": "LEX_STANDALONE_REMOVED",
                "message": "La pagina Lex standalone e' stata rimossa. Usa l'icona Lex flottante nell'applicazione.",
            },
            410,
            {"Cache-Control": "no-store"},
        )

    @guard
    def assistente_stato():
        payload, status = service.stato()
        return payload, status

    @guard
    def assistente_gateway_stato():
        payload, status = service.gateway_status()
        return payload, status

    @guard
    def assistente_context():
        payload, status = service.context(
            user=g.get("utente_corrente"),
            studio=g.get("studio_corrente"),
            data=request.get_json(silent=True) or {},
        )
        return payload, status

    @guard
    def assistente_warmup():
        data = request.get_json(silent=True) or {}
        payload, status = service.warmup(
            question=str(data.get("question", "") or "").strip(),
            context_label=str(data.get("context_label", "") or "").strip(),
        )
        return payload, status

    @guard
    def assistente_attachments():
        data = request.get_json(silent=True) or {}
        payload, status = service.attachments(files=data.get("files") or [])
        return payload, status

    @guard
    def assistente_documento():
        return service.documento(data=request.get_json(silent=True) or {})

    @guard
    def assistente_chat():
        return service.chat(
            user=g.get("utente_corrente"),
            studio=g.get("studio_corrente"),
            data=request.get_json(silent=True) or {},
        )

    bp.add_url_rule("/lex", view_func=lex_chat_page, methods=["GET"])
    bp.add_url_rule("/api/assistente/stato", view_func=assistente_stato, methods=["GET"])
    bp.add_url_rule("/api/assistente/gateway/stato", view_func=assistente_gateway_stato, methods=["GET"])
    bp.add_url_rule("/api/assistente/context", view_func=assistente_context, methods=["POST"])
    bp.add_url_rule("/api/assistente/warmup", view_func=assistente_warmup, methods=["POST"])
    bp.add_url_rule("/api/assistente/attachments", view_func=assistente_attachments, methods=["POST"])
    bp.add_url_rule("/api/assistente/documento", view_func=assistente_documento, methods=["POST"])
    bp.add_url_rule("/api/assistente/chat", view_func=assistente_chat, methods=["POST"])
