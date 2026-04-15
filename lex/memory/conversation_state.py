"""Gestione minima e testabile dello stato conversazionale di Lex."""

from __future__ import annotations

from typing import Any


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def latest_user_message(messages: list[dict[str, object]] | None, *, skip_last: bool = False) -> str:
    rows = list(messages or [])
    if skip_last and rows:
        rows = rows[:-1]
    for message in reversed(rows):
        if _clean_spaces(message.get("role")).lower() != "user":
            continue
        content = _clean_spaces(message.get("content"))
        if content:
            return content
    return ""


def resolve_current_and_previous_user_messages(
    *,
    explicit_question: str,
    messages: list[dict[str, object]] | None,
) -> tuple[str, str, list[dict[str, object]]]:
    normalized_messages = [dict(item or {}) for item in list(messages or [])]
    current_from_messages = latest_user_message(normalized_messages)
    current_explicit = _clean_spaces(explicit_question)

    if current_explicit and current_explicit != current_from_messages:
        return current_explicit, current_from_messages, normalized_messages

    current_user_message = current_explicit or current_from_messages
    if current_user_message and current_from_messages == current_user_message:
        history_messages = normalized_messages[:-1]
        previous_user_message = latest_user_message(normalized_messages, skip_last=True)
        return current_user_message, previous_user_message, history_messages

    previous_user_message = latest_user_message(normalized_messages, skip_last=True)
    return current_user_message, previous_user_message, normalized_messages


def messages_with_effective_question(
    messages: list[dict[str, object]] | None,
    *,
    effective_question: str,
    original_question: str,
) -> list[dict[str, object]]:
    normalized = [dict(item or {}) for item in list(messages or [])]
    clean_effective = _clean_spaces(effective_question)
    clean_original = _clean_spaces(original_question)
    if not normalized or not clean_effective or clean_effective == clean_original:
        return normalized

    for idx in range(len(normalized) - 1, -1, -1):
        role = _clean_spaces(normalized[idx].get("role")).lower()
        if role != "user":
            continue
        normalized[idx]["content"] = clean_effective
        break
    return normalized
