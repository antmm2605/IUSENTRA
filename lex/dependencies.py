"""Dipendenze iniettate nel modulo Lex."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class LexDependencies:
    requests_module: Any
    build_studio_context: Callable[..., dict[str, Any]]
    warm_studio_context: Callable[..., dict[str, Any]]
    build_today_summary: Callable[..., dict[str, Any]]
    build_language_guidance: Callable[..., Any]
    build_prompt: Callable[..., str]
    resolve_followup_query: Callable[..., Any]
    resolve_social_and_operational_intent: Callable[..., Any]
    latest_user_message: Callable[..., str]
    build_social_only_reply: Callable[..., str]
    resolved_runtime: Callable[[], dict[str, Any]]
    warm_runtime: Callable[[], dict[str, Any]]
    build_unverified_pdf_reply: Callable[..., str]
    build_docx_bytes: Callable[..., bytes]
    build_export_filename: Callable[..., str]
    infer_export_title: Callable[..., str]
    build_attachment_prompt_block: Callable[..., str]
    parse_attachment_payloads: Callable[..., tuple[list[dict[str, Any]], list[str]]]


DependencyFactory = Callable[[], LexDependencies]
