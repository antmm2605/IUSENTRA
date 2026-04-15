"""Tipi condivisi del bounded context Lex."""

from __future__ import annotations

from typing import Literal


IntentType = Literal[
    "ask_lex",
    "summarize_fascicolo",
    "prepare_udienza",
    "analyze_document",
    "explain_telematico_error",
    "suggest_next_action",
    "compare_documents",
    "draft_act_support",
    "validate_draft",
    "suggest_fascicolo_updates",
]

RiskLevel = Literal["low", "medium", "high", "critical"]

WorkflowType = Literal[
    "chat",
    "fascicolo",
    "udienza",
    "atto",
    "telematico",
    "intelligence",
    "next_action",
]

ProviderType = Literal["ollama", "openai", "mock"]

SourceType = Literal[
    "fascicolo",
    "documento",
    "agenda",
    "scadenziario",
    "giurisprudenza",
    "legal_intelligence",
    "template_atto",
    "preventivo",
    "telematico",
    "normativa",
    "compliance",
]
