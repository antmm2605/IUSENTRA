"""Facciata compatibile per la logica follow-up di Lex.

Il modulo reale vive in ``lex.memory.followup``.
"""

from lex.memory.followup import (
    FollowupResolution,
    has_direct_web_topic,
    is_internal_operational_topic,
    is_short_followup,
    is_web_execution_request,
    latest_user_message,
    normalize_user_text,
    resolve_followup_query,
    should_trigger_web_search,
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
