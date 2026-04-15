"""Wiring runtime del modulo Lex.

Questo modulo tiene insieme le dipendenze reali usate in produzione,
cosi' il lato ``web`` resta una facciata sottile e il package ``lex``
possiede davvero il proprio bootstrap applicativo.
"""

from __future__ import annotations

from functools import wraps

import requests
from flask import g

from tools.lex_document_context import (
    build_attachment_prompt_block,
    parse_attachment_payloads,
)

from .dependencies import LexDependencies
from .context.studio_context import build_lex_studio_context, warm_lex_studio_context
from .context.today_summary import build_today_operational_summary
from .formatting.document_export import (
    build_docx_bytes,
    build_export_filename,
    infer_export_title,
)
from .guards.legal_reference_guard import build_unverified_pdf_reply
from .memory.followup import resolve_followup_query
from .memory.social_intent import (
    build_social_only_reply,
    latest_user_message,
    resolve_social_and_operational_intent,
)
from .providers.health import resolved_runtime, warm_runtime
from .prompts.language_guidance import build_language_guidance
from .prompts.prompt_builder import build_assistente_prompt


# Alias di compatibilita' per test e moduli legacy.
resolved_ollama_runtime = resolved_runtime
warm_ollama_chat_runtime = warm_runtime


def require_authenticated_flask_user(fn):
    """Protegge le route Lex quando non c'e' un utente autenticato."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return {"errore": "non autenticato"}, 401
        return fn(*args, **kwargs)

    return wrapper


def build_runtime_lex_dependencies() -> LexDependencies:
    """Costruisce il set di dipendenze reali usate dal modulo Lex."""

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


__all__ = [
    "build_assistente_prompt",
    "build_attachment_prompt_block",
    "build_docx_bytes",
    "build_export_filename",
    "build_language_guidance",
    "build_lex_studio_context",
    "build_runtime_lex_dependencies",
    "build_social_only_reply",
    "build_today_operational_summary",
    "build_unverified_pdf_reply",
    "infer_export_title",
    "latest_user_message",
    "parse_attachment_payloads",
    "requests",
    "require_authenticated_flask_user",
    "resolved_ollama_runtime",
    "resolved_runtime",
    "resolve_followup_query",
    "resolve_social_and_operational_intent",
    "warm_lex_studio_context",
    "warm_ollama_chat_runtime",
    "warm_runtime",
]
