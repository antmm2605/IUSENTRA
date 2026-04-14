from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from web.services.assistente_web_execution import (
    is_web_execution_request as is_web_execution_command,
    resolve_effective_query as resolve_web_effective_query,
)


@dataclass(slots=True)
class FollowupResolution:
    raw_text: str
    normalized_text: str
    previous_user_text: str
    effective_query: str
    is_followup: bool
    is_web_request: bool
    needs_web_search: bool
    reused_previous_topic: bool
    reason: str


_SHORT_FOLLOWUP_PATTERNS = (
    r"\be le ultime\b",
    r"\be gli ultimi\b",
    r"\be quelle\b",
    r"\be quelli\b",
    r"\bmi dici\b",
    r"\bmi trovi\b",
    r"\bpuoi vedere\b",
    r"\bpuoi cercare\b",
    r"\bpuoi controllare\b",
    r"\bpuoi verificare\b",
    r"\bcontrolla\b",
    r"\bverifica\b",
    r"\bcerca\b",
)

_REFERENTIAL_PATTERNS = (
    r"\bquelli\b",
    r"\bquelle\b",
    r"\bquello\b",
    r"\bquesti\b",
    r"\bqueste\b",
    r"\bquesto\b",
    r"\ble ultime\b",
    r"\bgli ultimi\b",
    r"\blo stesso\b",
    r"\bquello prima\b",
    r"\bquelli di prima\b",
    r"\bcome sopra\b",
)

_DIRECT_WEB_TOPICS = (
    "sentenza",
    "sentenze",
    "cassazione",
    "corte costituzionale",
    "tar",
    "consiglio di stato",
    "giurisprudenza",
    "massima",
    "norma",
    "normativa",
    "legge",
    "decreto",
    "regolamento",
    "eur-lex",
    "curia",
    "cedu",
    "mediazione",
    "pec",
    "firma digitale",
    "pst",
    "pdp",
    "pat",
    "reginde",
    "fatturapa",
    "agenzia entrate",
)

_OPERATIONAL_INTERNAL_TOPICS = (
    "udienza",
    "udienze",
    "agenda",
    "appuntamento",
    "appuntamenti",
    "scadenza",
    "scadenze",
    "fascicolo",
    "fascicoli",
    "cliente",
    "clienti",
    "preventivo",
    "preventivi",
    "fattura",
    "fatture",
    "parcella",
    "parcelle",
    "documento",
    "documenti",
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_user_text(text: str) -> str:
    value = _clean_spaces(text).lower()
    value = re.sub(r"\s+", " ", value)
    return value


def latest_user_message(
    messages: list[dict[str, object]] | None,
    *,
    skip_last: bool = False,
) -> str:
    rows = list(messages or [])
    if skip_last and rows:
        rows = rows[:-1]
    for message in reversed(rows):
        if str(message.get("role") or "").strip().lower() != "user":
            continue
        content = _clean_spaces(message.get("content"))
        if content:
            return content
    return ""


def is_web_execution_request(text: str) -> bool:
    return bool(is_web_execution_command(text))


def is_short_followup(text: str, *, max_words: int = 8) -> bool:
    q = normalize_user_text(text)
    if not q:
        return False
    words = q.split()
    if len(words) <= max_words:
        return True
    return any(re.search(pattern, q) for pattern in _SHORT_FOLLOWUP_PATTERNS)


def has_referential_language(text: str) -> bool:
    q = normalize_user_text(text)
    if not q:
        return False
    return any(re.search(pattern, q) for pattern in _REFERENTIAL_PATTERNS)


def has_direct_web_topic(text: str) -> bool:
    q = normalize_user_text(text)
    if not q:
        return False
    return any(token in q for token in _DIRECT_WEB_TOPICS)


def is_internal_operational_topic(text: str) -> bool:
    q = normalize_user_text(text)
    if not q:
        return False
    return any(token in q for token in _OPERATIONAL_INTERNAL_TOPICS)


def should_trigger_web_search(query: str) -> bool:
    q = normalize_user_text(query)
    if not q:
        return False

    if is_internal_operational_topic(q) and not has_direct_web_topic(q):
        return False

    if has_direct_web_topic(q):
        return True

    if is_web_execution_request(q):
        return True

    return False


def resolve_followup_query(
    current_text: str,
    *,
    previous_user_text: str = "",
) -> FollowupResolution:
    raw = _clean_spaces(current_text)
    current = normalize_user_text(raw)
    previous = _clean_spaces(previous_user_text)
    previous_norm = normalize_user_text(previous)

    if not current:
        return FollowupResolution(
            raw_text=raw,
            normalized_text=current,
            previous_user_text=previous,
            effective_query="",
            is_followup=False,
            is_web_request=False,
            needs_web_search=False,
            reused_previous_topic=False,
            reason="empty_current",
        )

    current_is_web_request = is_web_execution_request(current)
    current_is_short_followup = is_short_followup(current)
    current_has_reference = has_referential_language(current)
    web_effective_query = _clean_spaces(resolve_web_effective_query(raw, previous))
    web_reuses_previous_topic = bool(previous and web_effective_query == previous and web_effective_query != raw)

    if previous_norm and current_is_web_request and current_is_short_followup and web_reuses_previous_topic:
        return FollowupResolution(
            raw_text=raw,
            normalized_text=current,
            previous_user_text=previous,
            effective_query=web_effective_query,
            is_followup=True,
            is_web_request=True,
            needs_web_search=should_trigger_web_search(web_effective_query),
            reused_previous_topic=True,
            reason="web_request_reuses_previous_topic",
        )

    if previous_norm and current_is_short_followup and current_has_reference:
        merged = f"{previous} {raw}".strip()
        return FollowupResolution(
            raw_text=raw,
            normalized_text=current,
            previous_user_text=previous,
            effective_query=merged,
            is_followup=True,
            is_web_request=current_is_web_request,
            needs_web_search=should_trigger_web_search(merged),
            reused_previous_topic=True,
            reason="referential_followup_merged_with_previous",
        )

    if previous_norm and current_is_web_request and web_reuses_previous_topic and not has_direct_web_topic(current):
        return FollowupResolution(
            raw_text=raw,
            normalized_text=current,
            previous_user_text=previous,
            effective_query=web_effective_query,
            is_followup=True,
            is_web_request=True,
            needs_web_search=should_trigger_web_search(web_effective_query),
            reused_previous_topic=True,
            reason="generic_web_request_uses_previous_topic",
        )

    return FollowupResolution(
        raw_text=raw,
        normalized_text=current,
        previous_user_text=previous,
        effective_query=raw,
        is_followup=False,
        is_web_request=current_is_web_request,
        needs_web_search=should_trigger_web_search(raw),
        reused_previous_topic=False,
        reason="standalone_query",
    )


__all__ = [
    "FollowupResolution",
    "has_direct_web_topic",
    "is_internal_operational_topic",
    "is_short_followup",
    "is_web_execution_request",
    "latest_user_message",
    "normalize_user_text",
    "resolve_followup_query",
    "should_trigger_web_search",
]
