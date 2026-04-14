from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SocialRoutingResult:
    raw_text: str
    normalized_text: str
    social_kind: str
    social_prefix: str
    request_text: str
    effective_query: str
    is_social_only: bool
    is_social_with_request: bool
    is_daily_overview: bool
    is_followup: bool
    reused_previous_topic: bool
    reason: str


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: str) -> str:
    text = _clean_spaces(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _canonical_text(value: str) -> str:
    text = _normalize_text(value)
    return re.sub(r"^[\s,;:.!?-]+|[\s,;:.!?-]+$", "", text)


_GREETINGS = (
    "buongiorno",
    "buonasera",
    "buon pomeriggio",
    "ciao",
    "salve",
)

_THANKS = (
    "grazie",
    "grazie mille",
    "ti ringrazio",
    "molte grazie",
)

_ACKS = (
    "ok",
    "va bene",
    "perfetto",
    "ottimo",
    "bene",
    "d'accordo",
)

_FAREWELLS = (
    "a domani",
    "a dopo",
    "ci sentiamo dopo",
    "ci aggiorniamo",
    "buona giornata",
    "buona serata",
    "buona notte",
    "buon lavoro",
    "buon weekend",
)

_APOLOGIES = (
    "scusa",
    "scusami",
    "mi sono spiegato male",
    "mi sono spiegata male",
    "forse non sono stato chiaro",
    "forse non sono stata chiara",
)

_PRAISE = (
    "brava",
    "bravo",
    "complimenti",
    "ottimo lavoro",
    "molto bene",
)

_DAILY_OVERVIEW_PATTERNS = (
    r"\boggi cosa dobbiamo fare\b",
    r"\bcosa dobbiamo fare oggi\b",
    r"\bcosa facciamo oggi\b",
    r"\bda dove partiamo oggi\b",
    r"\bquadro di oggi\b",
    r"\bsituazione di oggi\b",
    r"\bpriorita di oggi\b",
    r"\bpriorità di oggi\b",
    r"\bcosa dobbiamo fare\b",
)

_REFERENTIAL_FOLLOWUPS = (
    r"\be oggi\b",
    r"\be adesso\b",
    r"\bcosa dobbiamo fare\b",
    r"\bda dove partiamo\b",
    r"\bquali sono le priorita\b",
    r"\bquali sono le priorità\b",
    r"\bche facciamo\b",
    r"\bpassiamo a\b",
    r"\bvediamo\b",
    r"\bcontinuiamo\b",
    r"\bquello\b",
    r"\bquelli\b",
    r"\bquelle\b",
    r"\bquesto\b",
    r"\bquesti\b",
    r"\bqueste\b",
    r"\bquello prima\b",
    r"\bcome sopra\b",
)

_INTERNAL_OPERATIONAL_TOPICS = (
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
    "attivita",
    "attività",
)


def latest_user_message(messages: list[dict[str, object]] | None, *, skip_last: bool = False) -> str:
    rows = list(messages or [])
    if skip_last and rows:
        rows = rows[:-1]
    for row in reversed(rows):
        if str(row.get("role") or "").strip().lower() != "user":
            continue
        content = _clean_spaces(row.get("content"))
        if content:
            return content
    return ""


def _exact_match(text: str, values: tuple[str, ...]) -> bool:
    return _canonical_text(text) in values


def _starts_with_phrase(text: str, values: tuple[str, ...]) -> tuple[str, str]:
    for value in values:
        match = re.match(rf"^({re.escape(value)})[\s,;:.!\-]*(.*)$", _clean_spaces(text), flags=re.IGNORECASE)
        if match:
            social = _clean_spaces(match.group(1))
            remaining = _clean_spaces(match.group(2))
            return social, remaining
    return "", text


def _detect_social_kind(text: str) -> str:
    if _exact_match(text, _GREETINGS):
        return "greeting"
    if _exact_match(text, _THANKS):
        return "thanks"
    if _exact_match(text, _ACKS):
        return "ack"
    if _exact_match(text, _FAREWELLS):
        return "farewell"
    if _exact_match(text, _APOLOGIES):
        return "apology"
    if _exact_match(text, _PRAISE):
        return "praise"
    return "none"


def _is_substantive_request_tail(text: str) -> bool:
    original = _clean_spaces(text)
    canonical = _canonical_text(original)
    if not canonical:
        return False

    if canonical in {"lex", "lex ai", "ai lex", "ai", "hacs", "hacs lex"}:
        return False

    tokens = [token for token in canonical.split() if token]
    if len(tokens) == 1 and "?" not in original and not any(char.isdigit() for char in canonical):
        return False

    return True


def split_social_and_request(text: str) -> tuple[str, str, str]:
    original = _clean_spaces(text)
    if not original:
        return "none", "", ""

    for kind, values in (
        ("greeting", _GREETINGS),
        ("thanks", _THANKS),
        ("ack", _ACKS),
        ("farewell", _FAREWELLS),
        ("apology", _APOLOGIES),
        ("praise", _PRAISE),
    ):
        social, remaining = _starts_with_phrase(original, values)
        if social:
            if remaining and not _is_substantive_request_tail(remaining):
                return kind, social, ""
            return kind, social, remaining

    detected = _detect_social_kind(original)
    if detected != "none":
        return detected, original, ""

    return "none", "", original


def is_daily_overview_request(text: str) -> bool:
    q = _normalize_text(text)
    if not q:
        return False
    return any(re.search(pattern, q) for pattern in _DAILY_OVERVIEW_PATTERNS)


def is_operational_internal_topic(text: str) -> bool:
    q = _normalize_text(text)
    if not q:
        return False
    return any(token in q for token in _INTERNAL_OPERATIONAL_TOPICS)


def is_referential_followup(text: str, *, max_words: int = 8) -> bool:
    q = _normalize_text(text)
    if not q:
        return False
    if any(re.search(pattern, q) for pattern in _REFERENTIAL_FOLLOWUPS):
        return True
    tokens = q.split()
    if len(tokens) > max_words:
        return False
    return any(token in q for token in ("quello", "quelli", "quelle", "questo", "questi", "queste", "oggi", "adesso"))


def build_social_prefix(kind: str, social_text: str) -> str:
    social_text = _normalize_text(social_text)

    if kind == "greeting":
        if social_text == "buongiorno":
            return "Buongiorno."
        if social_text == "buonasera":
            return "Buonasera."
        if social_text == "buon pomeriggio":
            return "Buon pomeriggio."
        if social_text == "ciao":
            return "Ciao."
        if social_text == "salve":
            return "Salve."
        return "Dimmi pure."

    if kind == "thanks":
        if social_text == "grazie mille":
            return "Di nulla."
        return "Prego."

    if kind == "ack":
        if social_text == "perfetto":
            return "Perfetto."
        if social_text == "ottimo":
            return "Ottimo."
        return "Va bene."

    if kind == "farewell":
        if social_text == "a domani":
            return "A domani."
        if social_text == "a dopo":
            return "A dopo."
        if social_text == "ci sentiamo dopo":
            return "A dopo."
        if social_text == "ci aggiorniamo":
            return "Va bene, ci aggiorniamo."
        if social_text == "buona giornata":
            return "Buona giornata."
        if social_text == "buona serata":
            return "Buona serata."
        if social_text == "buona notte":
            return "Buona notte."
        if social_text == "buon lavoro":
            return "Grazie, buon lavoro anche a te."
        if social_text == "buon weekend":
            return "Buon weekend."
        return "Va bene."

    if kind == "apology":
        return "Nessun problema."

    if kind == "praise":
        if social_text == "molto bene":
            return "Bene."
        return "Grazie."

    return ""


def build_social_only_reply(kind: str, social_text: str) -> str:
    prefix = build_social_prefix(kind, social_text)
    if kind == "greeting" and prefix in {"Buongiorno.", "Buonasera.", "Buon pomeriggio.", "Ciao.", "Salve."}:
        return prefix + " Dimmi pure."
    return prefix


def prepend_social_prefix(prefix: str, answer: str) -> str:
    clean_prefix = _clean_spaces(prefix)
    clean_answer = _clean_spaces(answer)
    if not clean_prefix:
        return clean_answer
    if not clean_answer:
        return clean_prefix
    if clean_answer.lower().startswith(clean_prefix.lower()):
        return clean_answer
    return f"{clean_prefix} {clean_answer}".strip()


def build_daily_overview_lead(prefix: str = "") -> str:
    return prepend_social_prefix(prefix, "Ti faccio subito il quadro operativo di oggi.")


def resolve_social_and_operational_intent(
    current_text: str,
    *,
    previous_user_text: str = "",
) -> SocialRoutingResult:
    raw = _clean_spaces(current_text)
    normalized = _normalize_text(raw)
    previous = _clean_spaces(previous_user_text)
    previous_norm = _normalize_text(previous)

    if not normalized:
        return SocialRoutingResult(
            raw_text=raw,
            normalized_text=normalized,
            social_kind="none",
            social_prefix="",
            request_text="",
            effective_query="",
            is_social_only=False,
            is_social_with_request=False,
            is_daily_overview=False,
            is_followup=False,
            reused_previous_topic=False,
            reason="empty_current",
        )

    social_kind, social_text, request_text = split_social_and_request(raw)
    social_prefix = build_social_prefix(social_kind, social_text) if social_kind != "none" else ""
    body_text = request_text or raw
    body_norm = _normalize_text(body_text)
    social_with_request = bool(social_kind != "none" and request_text)
    result_social_kind = f"{social_kind}_with_request" if social_with_request else social_kind

    if social_kind != "none" and not request_text:
        return SocialRoutingResult(
            raw_text=raw,
            normalized_text=normalized,
            social_kind=social_kind,
            social_prefix=social_prefix,
            request_text="",
            effective_query="",
            is_social_only=True,
            is_social_with_request=False,
            is_daily_overview=False,
            is_followup=False,
            reused_previous_topic=False,
            reason="social_only",
        )

    if previous_norm and is_referential_followup(body_norm):
        if is_daily_overview_request(body_norm) and is_operational_internal_topic(previous_norm):
            merged = f"{previous} {body_text}".strip()
            return SocialRoutingResult(
                raw_text=raw,
                normalized_text=normalized,
                social_kind=result_social_kind,
                social_prefix=social_prefix,
                request_text=body_text,
                effective_query=merged,
                is_social_only=False,
                is_social_with_request=social_with_request,
                is_daily_overview=False,
                is_followup=True,
                reused_previous_topic=True,
                reason="daily_followup_reused_previous",
            )
        if not is_daily_overview_request(body_norm):
            merged = f"{previous} {body_text}".strip()
            return SocialRoutingResult(
                raw_text=raw,
                normalized_text=normalized,
                social_kind=result_social_kind,
                social_prefix=social_prefix,
                request_text=body_text,
                effective_query=merged,
                is_social_only=False,
                is_social_with_request=social_with_request,
                is_daily_overview=False,
                is_followup=True,
                reused_previous_topic=True,
                reason="referential_followup_reused_previous",
            )

    if is_daily_overview_request(body_norm):
        return SocialRoutingResult(
            raw_text=raw,
            normalized_text=normalized,
            social_kind=result_social_kind,
            social_prefix=social_prefix,
            request_text=body_text,
            effective_query=body_text,
            is_social_only=False,
            is_social_with_request=social_with_request,
            is_daily_overview=True,
            is_followup=False,
            reused_previous_topic=False,
            reason="standalone_daily_overview",
        )

    if social_with_request:
        return SocialRoutingResult(
            raw_text=raw,
            normalized_text=normalized,
            social_kind=result_social_kind,
            social_prefix=social_prefix,
            request_text=body_text,
            effective_query=body_text,
            is_social_only=False,
            is_social_with_request=True,
            is_daily_overview=False,
            is_followup=False,
            reused_previous_topic=False,
            reason="social_plus_request_same_message",
        )

    return SocialRoutingResult(
        raw_text=raw,
        normalized_text=normalized,
        social_kind="none",
        social_prefix="",
        request_text=body_text,
        effective_query=body_text,
        is_social_only=False,
        is_social_with_request=False,
        is_daily_overview=False,
        is_followup=False,
        reused_previous_topic=False,
        reason="standalone_request",
    )


__all__ = [
    "SocialRoutingResult",
    "build_daily_overview_lead",
    "build_social_only_reply",
    "build_social_prefix",
    "is_daily_overview_request",
    "is_operational_internal_topic",
    "is_referential_followup",
    "latest_user_message",
    "prepend_social_prefix",
    "resolve_social_and_operational_intent",
    "split_social_and_request",
]
