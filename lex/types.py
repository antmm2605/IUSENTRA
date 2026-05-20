from __future__ import annotations

from typing import Literal

IntentType = Literal[
    "ask_lex",
    "summarize_fascicolo",
    "sintesi_documento",
    "prepare_udienza",
    "analyze_document",
    "explain_telematico_error",
    "suggest_next_action",
    "compare_documents",
    "draft_act_support",
    "template_act_lookup",
    "template_act_prefill",
    "template_act_create",
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
    "cliente_anagrafica",
    "comunicazioni_lookup",
    "studio_context_lookup",
]

RiskLevel = Literal["low", "medium", "high", "critical"]

WorkflowType = Literal[
    "chat",
    "fascicolo",
    "udienza",
    "atto",
    "atto_da_template",
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
    "studio_data_lookup",
    "giurisprudenza_specifica",
    "termini_processuali",
    "drafting_legal_letter",
    "deposito_telematico",
    "lex_feedback_diagnostico",
]

ProviderType = Literal["ollama", "openai", "mock", "deterministic"]

SourceType = Literal[
    "fascicolo",
    "documento",
    "documento_chunk",
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
