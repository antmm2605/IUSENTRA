"""Riconoscimento leggero delle richieste web esecutive per Lex."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WebExecutionIntent:
    requested: bool
    inherited_previous_theme: bool
    current_text: str = ""
    previous_user_text: str = ""
    effective_query: str = ""


_EXECUTION_PATTERNS: tuple[str, ...] = (
    r"\bcontrolla tu\b",
    r"\bpuoi controllare tu\b",
    r"\bcontrolla sul web\b",
    r"\bpuoi controllare sul web\b",
    r"\bcerca tu\b",
    r"\bcercalo tu\b",
    r"\bcerca sul web\b",
    r"\bfammi la ricerca\b",
    r"\bfai tu la ricerca\b",
    r"\bverifica\b",
    r"\bverifica tu\b",
    r"\bpuoi verificare\b",
    r"\bguarda tu\b",
    r"\bpuoi guardare\b",
    r"\bguardi tu\b",
)

_FOLLOW_UP_WEB_ONLY_PATTERNS: tuple[str, ...] = (
    "controlla tu",
    "puoi controllare tu",
    "controlla sul web",
    "puoi controllare sul web",
    "puoi controllare tu sul web",
    "cerca tu",
    "cercalo tu",
    "cerca sul web",
    "fammi la ricerca",
    "fai tu la ricerca",
    "verifica",
    "verifica tu",
    "puoi verificare",
    "guarda tu",
    "puoi guardare",
    "guardi tu",
    "puoi verificare sul web",
)

_WEB_EXECUTION_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "al",
        "alla",
        "che",
        "controlla",
        "controllare",
        "cerca",
        "cercalo",
        "cercare",
        "con",
        "da",
        "devi",
        "fai",
        "fammi",
        "guarda",
        "guardare",
        "guardi",
        "il",
        "io",
        "la",
        "le",
        "lo",
        "mi",
        "on",
        "per",
        "piu",
        "puoi",
        "ricerca",
        "sul",
        "sulla",
        "tu",
        "un",
        "una",
        "verifica",
        "verificare",
        "web",
    }
)


def _normalize_text(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def _normalize_key(text: str) -> str:
    value = _normalize_text(text).lower()
    return value


def _clean_token(token: str) -> str:
    return "".join(ch for ch in str(token or "").lower() if ch.isalnum())


def is_web_execution_request(text: str) -> bool:
    q = _normalize_key(text)
    if not q:
        return False
    return any(re.search(pattern, q) for pattern in _EXECUTION_PATTERNS) or " sul web" in q or q.endswith("web")


def previous_user_message(
    messages: list[dict[str, object]] | None,
    *,
    current_text: str = "",
) -> str:
    current = _normalize_key(current_text)
    skipped_current_user = False
    for message in reversed(messages or []):
        role = _normalize_key(message.get("role"))
        content = _normalize_text(message.get("content"))
        if role != "user" or not content.strip():
            continue
        if not skipped_current_user and current and _normalize_key(content) == current:
            skipped_current_user = True
            continue
        return content
    return ""


def _has_substantive_theme(text: str) -> bool:
    tokens = [_clean_token(token) for token in _normalize_key(text).split(" ")]
    meaningful = [
        token
        for token in tokens
        if token and len(token) > 2 and token not in _WEB_EXECUTION_STOPWORDS
    ]
    return bool(meaningful)


def _is_short_follow_up_web_request(text: str) -> bool:
    q = _normalize_key(text)
    if not q or not is_web_execution_request(q):
        return False
    if q in _FOLLOW_UP_WEB_ONLY_PATTERNS:
        return True
    if not _has_substantive_theme(q):
        return True
    tokens = [token for token in q.split(" ") if token]
    return len(tokens) <= 6 and not _has_substantive_theme(q)


def resolve_effective_query(current_text: str, previous_user_text: str) -> str:
    current = _normalize_text(current_text)
    previous = _normalize_text(previous_user_text)
    if _is_short_follow_up_web_request(current) and previous:
        return previous
    return current


def resolve_web_execution_intent(
    current_text: str,
    *,
    messages: list[dict[str, object]] | None = None,
) -> WebExecutionIntent:
    current = _normalize_text(current_text)
    previous = previous_user_message(messages, current_text=current)
    requested = is_web_execution_request(current)
    effective_query = resolve_effective_query(current, previous)
    inherited_previous_theme = bool(requested and previous and effective_query == previous and effective_query != current)
    return WebExecutionIntent(
        requested=requested,
        inherited_previous_theme=inherited_previous_theme,
        current_text=current,
        previous_user_text=previous,
        effective_query=effective_query or current,
    )


__all__ = [
    "WebExecutionIntent",
    "is_web_execution_request",
    "previous_user_message",
    "resolve_effective_query",
    "resolve_web_execution_intent",
]
