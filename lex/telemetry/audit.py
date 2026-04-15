"""Audit applicativo per Lex."""

from __future__ import annotations

from flask import g

from pct.legal_intelligence import fonti_per_query, motori_per_query
from web.helpers import get_legal_intelligence


def audit_trace(
    *,
    query: str,
    prompt_question: str,
    engine_ids: list[str] | None,
    source_ids: list[str] | None,
    ai_model: str,
    result_summary: str,
    warning: str,
) -> None:
    get_legal_intelligence().registra_trace_risposta(
        query=query,
        user=getattr(g.get("utente_corrente"), "username", ""),
        engine_ids=engine_ids or motori_per_query(prompt_question),
        source_ids=source_ids or fonti_per_query(prompt_question),
        ai_model=ai_model,
        result_summary=result_summary,
        warning=warning,
    )
