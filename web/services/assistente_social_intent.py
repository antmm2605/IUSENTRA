"""Facciata compatibile per il routing sociale e operativo di Lex.

Il modulo reale vive in ``lex.memory.social_intent``.
"""

from lex.memory.social_intent import (
    SocialRoutingResult,
    build_daily_overview_lead,
    build_relational_reply,
    build_social_only_reply,
    build_social_prefix,
    is_daily_overview_request,
    is_operational_internal_topic,
    is_referential_followup,
    is_small_talk_message,
    latest_user_message,
    prepend_social_prefix,
    resolve_social_and_operational_intent,
    split_social_and_request,
)

__all__ = [
    "SocialRoutingResult",
    "build_daily_overview_lead",
    "build_relational_reply",
    "build_social_only_reply",
    "build_social_prefix",
    "is_daily_overview_request",
    "is_operational_internal_topic",
    "is_referential_followup",
    "is_small_talk_message",
    "latest_user_message",
    "prepend_social_prefix",
    "resolve_social_and_operational_intent",
    "split_social_and_request",
]
