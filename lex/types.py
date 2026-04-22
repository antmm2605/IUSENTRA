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
    "research_normativa",
    "research_giurisprudenza",
    "research_prassi",
    "research_sources",
    "check_compliance",
    "explain_normative_change",
    "summarize_legal_update",
    "evaluate_preventivo",
    "evaluate_tariffario",
    "evaluate_fatturazione",
    "resolve_operational_question",
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
    "normativa",
    "giurisprudenza",
    "prassi",
    "research",
    "cabina",
    "economico",
    "compliance",
    "fonti",
    "telematico_status",
    "documento",
    "question_answering",
]

ProviderType = Literal["ollama", "openai", "mock", "deterministic"]

SourceType = Literal[
    "fascicolo",
    "documento",
    "anagrafica",
    "agenda",
    "scadenziario",
    "giurisprudenza",
    "legal_intelligence",
    "template_atto",
    "preventivo",
    "tariffario",
    "fattura",
    "strumento",
    "telematico",
    "normativa",
    "compliance",
    "web_ufficiale",
    "web_istituzionale",
    "web_editoriale",
    "legal_updates",
]

ModuleType = Literal[
    "cabina",
    "fascicoli",
    "documenti",
    "agenda",
    "scadenziario",
    "telematico",
    "preventivi",
    "tariffario",
    "fatture",
    "anagrafiche",
    "strumenti",
    "ricerca_legale",
    "compliance",
]

FactKind = Literal["fatto_certo", "fatto_derivato", "ipotesi", "suggerimento", "alert"]
PackStatus = Literal["ok", "empty", "warning"]
InsightType = Literal["operational", "economic", "compliance", "hearing"]