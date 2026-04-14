from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from web.services.assistente_social_intent import build_daily_overview_lead, prepend_social_prefix


@dataclass(slots=True)
class LanguageGuidance:
    opening_line: str
    prompt_block: str
    mode: str


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _contains_query_token(text: str, token: str) -> bool:
    haystack = _clean_spaces(text).lower()
    needle = _clean_spaces(token).lower()
    if not haystack or not needle:
        return False
    return needle in haystack


def _is_case_law_lookup(question: str) -> bool:
    text = _clean_spaces(question).lower()
    if not text:
        return False
    has_case_law = any(
        _contains_query_token(text, token)
        for token in ("sentenza", "sentenze", "giurisprudenza", "massima", "pronuncia", "pronunce", "provvedimento")
    )
    has_scope = any(
        _contains_query_token(text, token)
        for token in ("civile", "civili", "cassazione", "tar", "consiglio di stato", "amministrativ", "penal")
    )
    return has_case_law and has_scope


def _is_normative_lookup(question: str) -> bool:
    text = _clean_spaces(question).lower()
    if not text:
        return False
    return any(
        _contains_query_token(text, token)
        for token in ("norma", "normativa", "legge", "decreto", "articolo", "regolamento", "circolare")
    )


def _build_prompt_block(mode: str) -> str:
    if mode == "daily_overview":
        return (
            "Regia linguistica: apri subito con il quadro operativo della giornata, senza saluti inutili, "
            "e ordina la risposta per priorita', attivita' urgenti e prossimo passo concreto."
        )
    if mode == "civil_case_law_web":
        return (
            "Regia linguistica: niente saluti automatici, niente placeholder e niente richieste premature di restringimento. "
            "Per questa ricerca ampia parti dalle sentenze civili piu' recenti e rilevanti, con priorita' alla Cassazione e alle fonti ufficiali, "
            "poi solo dopo proponi un eventuale affinamento per materia."
        )
    if mode == "case_law_web":
        return (
            "Regia linguistica: prendi in carico la ricerca subito, senza scaricare il perimetro sull'utente. "
            "Parti dalle pronunce piu' recenti e rilevanti e riporta risultati concreti prima di eventuali limiti."
        )
    if mode == "normative_web":
        return (
            "Regia linguistica: prendi in carico la verifica normativa in modo diretto, senza saluti o template. "
            "Parti dai riferimenti normativi piu' aggiornati e dalle fonti ufficiali pertinenti."
        )
    if mode == "generic_web":
        return (
            "Regia linguistica: se l'utente chiede una verifica web operativa, Lex deve partire da un criterio utile e immediato, "
            "senza chiedere subito chiarimenti se la richiesta e' gia' comprensibile."
        )
    return ""


def build_language_guidance(
    *,
    question: str,
    social_prefix: str = "",
    research_strategy: str = "",
    focus_topic: str = "",
    web_execution_requested: bool = False,
    is_daily_overview: bool = False,
) -> LanguageGuidance:
    clean_question = _clean_spaces(question)
    clean_social_prefix = _clean_spaces(social_prefix)
    clean_strategy = _clean_spaces(research_strategy)
    clean_topic = _clean_spaces(focus_topic)

    if is_daily_overview:
        return LanguageGuidance(
            opening_line=build_daily_overview_lead(clean_social_prefix),
            prompt_block=_build_prompt_block("daily_overview"),
            mode="daily_overview",
        )

    if clean_strategy == "auto_narrow_recent_civil_case_law" or clean_topic == "sentenze_civili":
        return LanguageGuidance(
            opening_line=prepend_social_prefix(
                clean_social_prefix,
                "Controllo io sul web. Parto dalle sentenze civili piu' recenti e rilevanti, dando precedenza alla Cassazione e alle fonti ufficiali disponibili.",
            ),
            prompt_block=_build_prompt_block("civil_case_law_web"),
            mode="civil_case_law_web",
        )

    if web_execution_requested and _is_case_law_lookup(clean_question):
        return LanguageGuidance(
            opening_line=prepend_social_prefix(
                clean_social_prefix,
                "Controllo io sul web. Parto dalle pronunce piu' recenti e rilevanti, con priorita' alle fonti ufficiali disponibili.",
            ),
            prompt_block=_build_prompt_block("case_law_web"),
            mode="case_law_web",
        )

    if web_execution_requested and _is_normative_lookup(clean_question):
        return LanguageGuidance(
            opening_line=prepend_social_prefix(
                clean_social_prefix,
                "Controllo io sul web. Parto dai riferimenti normativi piu' aggiornati e dalle fonti ufficiali pertinenti.",
            ),
            prompt_block=_build_prompt_block("normative_web"),
            mode="normative_web",
        )

    if web_execution_requested:
        return LanguageGuidance(
            opening_line=prepend_social_prefix(
                clean_social_prefix,
                "Controllo io sul web. Parto dai riferimenti piu' recenti e rilevanti, con priorita' alle fonti ufficiali disponibili.",
            ),
            prompt_block=_build_prompt_block("generic_web"),
            mode="generic_web",
        )

    return LanguageGuidance(opening_line="", prompt_block="", mode="")


__all__ = ["LanguageGuidance", "build_language_guidance"]
