"""Risoluzione leggera del focus conversazionale di Lex."""

from __future__ import annotations

import re
from typing import Any

from web.services.assistente_web_execution import resolve_web_execution_intent


_TOPIC_RULES: tuple[dict[str, Any], ...] = (
    {
        "topic": "dashboard",
        "keywords": ("panoramica", "situazione studio", "quadro generale", "dashboard"),
        "sections": ("Impostazioni studio", "PEC e canali email", "Quadro operativo"),
        "focus_label": "quadro generale dello studio",
        "include_live_web": False,
    },
    {
        "topic": "udienze",
        "keywords": ("udienza", "udienze", "calendario udienze", "udienza imminente"),
        "sections": ("Agenda", "Fascicoli", "Scadenziario"),
        "focus_label": "udienze rilevanti",
        "include_live_web": False,
    },
    {
        "topic": "agenda",
        "keywords": ("agenda", "calendario", "appuntamento", "appuntamenti", "riunione"),
        "sections": ("Agenda", "Scadenziario"),
        "focus_label": "agenda studio",
        "include_live_web": False,
    },
    {
        "topic": "scadenze",
        "keywords": ("scadenza", "scadenze", "termine", "termini"),
        "sections": ("Scadenziario", "Agenda"),
        "focus_label": "scadenze rilevanti",
        "include_live_web": False,
    },
    {
        "topic": "fascicoli",
        "keywords": ("fascicolo", "fascicoli", "pratica", "pratiche", "rg", "procedimento", "procedimenti"),
        "sections": ("Fascicoli", "Agenda"),
        "focus_label": "fascicoli rilevanti",
        "include_live_web": False,
    },
    {
        "topic": "clienti",
        "keywords": ("cliente", "clienti", "assistito", "assistiti", "anagrafica"),
        "sections": ("Clienti", "Soggetti"),
        "focus_label": "clienti rilevanti",
        "include_live_web": False,
    },
    {
        "topic": "soggetti",
        "keywords": ("soggetto", "soggetti", "parte", "parti", "difensore", "codifensore", "domiciliatario"),
        "sections": ("Soggetti", "Clienti"),
        "focus_label": "parti e soggetti",
        "include_live_web": False,
    },
    {
        "topic": "documenti",
        "keywords": ("documento", "documenti", "allegato", "allegati", "verbale", "memoria", "bozza"),
        "sections": ("RAG documentale locale", "Fascicoli", "Template atti"),
        "focus_label": "documenti collegati",
        "include_live_web": False,
    },
    {
        "topic": "preventivi",
        "keywords": ("preventivo", "preventivi", "offerta", "offerte"),
        "sections": ("Preventivi", "Tariffario", "Clienti"),
        "focus_label": "preventivi",
        "include_live_web": False,
    },
    {
        "topic": "fatture",
        "keywords": ("fattura", "fatture", "fatturazione", "parcella", "parcelle", "saldo", "pagamento"),
        "sections": ("Fatturazione", "Clienti"),
        "focus_label": "fatture e pagamenti",
        "include_live_web": False,
    },
    {
        "topic": "pec_firma",
        "keywords": ("pec", "firma", "firmato", "p7m", "cades", "token", "smart card", "certificato"),
        "sections": ("PEC e canali email", "Impostazioni studio"),
        "focus_label": "PEC e firma digitale",
        "include_live_web": False,
    },
    {
        "topic": "sentenze_web",
        "keywords": (
            "sentenza",
            "sentenze",
            "massima",
            "giurisprudenza",
            "cassazione",
            "tar",
            "consiglio di stato",
            "normativa",
            "norma",
            "legge",
            "decreto",
            "provvedimento",
        ),
        "sections": ("Archivio sentenze", "Ricerca legale e fonti web"),
        "focus_label": "ricerca legale aggiornata",
        "include_live_web": True,
    },
)

_FOLLOW_UP_MARKERS: tuple[str, ...] = (
    "quelli",
    "quelle",
    "quello",
    "quella",
    "quei",
    "quegli",
    "questi",
    "queste",
    "quale dei due",
    "quale delle due",
    "quale dei tre",
    "quale delle tre",
    "le 2 fasi",
    "le due fasi",
    "quello prima",
    "quella prima",
)

_GENERIC_SECTION_FALLBACK: tuple[str, ...] = ("Fascicoli", "Clienti", "Agenda", "Scadenziario")
_GENERIC_OPERATIONAL_FOLLOW_UP_PATTERNS: tuple[str, ...] = (
    r"\bprossim[a-z']*\b",
    r"\battivit[a-z']*\b",
    r"\bazione\b",
    r"\bazioni\b",
    r"\badempiment[a-z']*\b",
    r"\bpasso successivo\b",
    r"\bcosa facciamo\b",
    r"\bda dove partiamo\b",
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _word_count(text: str) -> int:
    return len([token for token in _clean_spaces(text).split(" ") if token])


def _contains_keyword(haystack: str, keyword: str) -> bool:
    clean_haystack = _clean_spaces(haystack).lower()
    clean_keyword = _clean_spaces(keyword).lower()
    if not clean_haystack or not clean_keyword:
        return False
    if " " in clean_keyword:
        return clean_keyword in clean_haystack
    return re.search(rf"(?<![a-z0-9]){re.escape(clean_keyword)}(?![a-z0-9])", clean_haystack) is not None


def _find_topic_rule(question: str) -> dict[str, Any] | None:
    haystack = _clean_spaces(question).lower()
    if not haystack:
        return None
    for rule in _TOPIC_RULES:
        if any(_contains_keyword(haystack, keyword) for keyword in rule["keywords"]):
            return rule
    return None


def _looks_like_follow_up(question: str) -> bool:
    haystack = _clean_spaces(question).lower()
    if not haystack:
        return False
    if any(marker in haystack for marker in _FOLLOW_UP_MARKERS):
        return True
    return _word_count(haystack) <= 4 and _find_topic_rule(haystack) is None


def _looks_like_generic_operational_follow_up(question: str) -> bool:
    haystack = _clean_spaces(question).lower()
    if not haystack:
        return False
    return any(re.search(pattern, haystack) for pattern in _GENERIC_OPERATIONAL_FOLLOW_UP_PATTERNS)


def _recent_topic_rule(messages: list[dict[str, object]] | None, current_question: str) -> dict[str, Any] | None:
    current_clean = _clean_spaces(current_question).lower()
    skipped_current_user = False
    for message in reversed(messages or []):
        role = _clean_spaces(message.get("role")).lower()
        content = _clean_spaces(message.get("content")).lower()
        if not content:
            continue
        if role == "user" and not skipped_current_user and content == current_clean:
            skipped_current_user = True
            continue
        rule = _find_topic_rule(content)
        if rule:
            return rule
    return None


def _topic_label(rule: dict[str, Any], question: str) -> str:
    topic = str(rule.get("topic") or "").strip()
    text = _clean_spaces(question).lower()
    if topic in {"udienze", "agenda"} and "oggi" in text:
        return "udienze di oggi"
    if topic in {"udienze", "fascicoli"} and "attiv" in text:
        return "procedimenti attivi"
    if topic == "scadenze" and "oggi" in text:
        return "scadenze di oggi"
    if topic == "documenti" and "mancant" in text:
        return "documenti mancanti"
    return str(rule.get("focus_label") or "tema operativo").strip()


def _effective_question(question: str, rule: dict[str, Any] | None, *, is_follow_up: bool) -> str:
    clean_question = _clean_spaces(question)
    if not clean_question or not rule or not is_follow_up:
        return clean_question
    topic = str(rule.get("topic") or "").replace("_", " ").strip()
    if not topic:
        return clean_question
    return f"{topic} {clean_question}".strip()


def resolve_conversation_focus(
    question: str,
    *,
    messages: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    """Determina il focus minimo utile per richieste brevi e follow-up."""

    clean_question = _clean_spaces(question)
    web_intent = resolve_web_execution_intent(clean_question, messages=messages)
    base_question = _clean_spaces(web_intent.effective_query or clean_question)
    current_rule = _find_topic_rule(base_question)
    prior_rule = _recent_topic_rule(messages, clean_question)
    is_follow_up = _looks_like_follow_up(clean_question) or web_intent.inherited_previous_theme

    resolved_rule = current_rule
    if resolved_rule is None and is_follow_up:
        resolved_rule = prior_rule

    if resolved_rule is None and prior_rule is not None and _word_count(base_question) <= 3:
        resolved_rule = prior_rule
        is_follow_up = True

    if resolved_rule is None and prior_rule is not None and _looks_like_generic_operational_follow_up(base_question):
        resolved_rule = prior_rule
        is_follow_up = True

    if resolved_rule is None:
        return {
            "topic": "",
            "focus_label": "",
            "effective_question": base_question or clean_question,
            "section_titles": list(_GENERIC_SECTION_FALLBACK),
            "include_live_web": bool(web_intent.requested),
            "is_follow_up": bool(is_follow_up),
            "has_explicit_overview": False,
            "web_execution_requested": bool(web_intent.requested),
            "inherited_previous_theme": bool(web_intent.inherited_previous_theme),
            "previous_user_text": web_intent.previous_user_text,
        }

    focus_label = _topic_label(resolved_rule, clean_question if not web_intent.inherited_previous_theme else base_question)
    effective_question = (
        base_question
        if web_intent.inherited_previous_theme
        else _effective_question(clean_question, resolved_rule, is_follow_up=is_follow_up)
    )
    return {
        "topic": str(resolved_rule.get("topic") or "").strip(),
        "focus_label": focus_label,
        "effective_question": effective_question,
        "section_titles": list(resolved_rule.get("sections") or _GENERIC_SECTION_FALLBACK),
        "include_live_web": bool(resolved_rule.get("include_live_web")) or bool(web_intent.requested),
        "is_follow_up": is_follow_up,
        "has_explicit_overview": str(resolved_rule.get("topic") or "").strip() == "dashboard",
        "web_execution_requested": bool(web_intent.requested),
        "inherited_previous_theme": bool(web_intent.inherited_previous_theme),
        "previous_user_text": web_intent.previous_user_text,
    }


__all__ = ["resolve_conversation_focus"]
