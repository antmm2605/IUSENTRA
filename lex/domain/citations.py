"""Regole citazioni del dominio Lex."""

from __future__ import annotations


def citation_required(intent: str) -> bool:
    return intent in {
        "ask_lex",
        "summarize_fascicolo",
        "prepare_udienza",
        "explain_telematico_error",
        "draft_act_support",
    }
