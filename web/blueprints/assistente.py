"""Facciata compatibile del blueprint Lex.

Il motore reale vive nel package ``lex/``.
Questo modulo mantiene:

- il nome blueprint ``assistente``
- gli endpoint ``/api/assistente/*``
- i punti di monkeypatch usati dai test esistenti
"""

from __future__ import annotations

import requests
from flask import g

from lex.blueprint import create_lex_blueprint
from lex.context.today_summary import build_today_operational_summary
from lex.dependencies import LexDependencies
from lex.memory.followup import resolve_followup_query
from lex.memory.social_intent import (
    build_social_only_reply,
    latest_user_message,
    resolve_social_and_operational_intent,
)
from lex.prompts.language_guidance import build_language_guidance
from lex.prompts.prompt_builder import build_assistente_prompt
from web.services.assistente_document_export import (
    build_docx_bytes,
    build_export_filename,
    infer_export_title,
)
from web.services.assistente_legal_reference_guard import build_unverified_pdf_reply
from web.services.assistente_studio_context import (
    build_lex_studio_context,
    warm_lex_studio_context,
)
from web.services.ollama_runtime import (
    resolved_ollama_runtime,
    warm_ollama_chat_runtime,
)
from tools.lex_document_context import (
    build_attachment_prompt_block,
    parse_attachment_payloads,
)


def _richiedi_login(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return {"errore": "non autenticato"}, 401
        return fn(*args, **kwargs)

    return wrapper


def _build_lex_dependencies() -> LexDependencies:
    return LexDependencies(
        requests_module=requests,
        build_studio_context=build_lex_studio_context,
        warm_studio_context=warm_lex_studio_context,
        build_today_summary=build_today_operational_summary,
        build_language_guidance=build_language_guidance,
        build_prompt=build_assistente_prompt,
        resolve_followup_query=resolve_followup_query,
        resolve_social_and_operational_intent=resolve_social_and_operational_intent,
        latest_user_message=latest_user_message,
        build_social_only_reply=build_social_only_reply,
        resolved_runtime=resolved_ollama_runtime,
        warm_runtime=warm_ollama_chat_runtime,
        build_unverified_pdf_reply=build_unverified_pdf_reply,
        build_docx_bytes=build_docx_bytes,
        build_export_filename=build_export_filename,
        infer_export_title=infer_export_title,
        build_attachment_prompt_block=build_attachment_prompt_block,
        parse_attachment_payloads=parse_attachment_payloads,
    )


assistente = create_lex_blueprint(
    dependency_factory=_build_lex_dependencies,
    login_required=_richiedi_login,
)


__all__ = [
    "assistente",
    "build_assistente_prompt",
    "build_attachment_prompt_block",
    "build_docx_bytes",
    "build_export_filename",
    "build_language_guidance",
    "build_lex_studio_context",
    "build_social_only_reply",
    "build_today_operational_summary",
    "build_unverified_pdf_reply",
    "infer_export_title",
    "latest_user_message",
    "parse_attachment_payloads",
    "requests",
    "resolved_ollama_runtime",
    "resolve_followup_query",
    "resolve_social_and_operational_intent",
    "warm_lex_studio_context",
    "warm_ollama_chat_runtime",
]
