"""Payload UI condivisi per le route di Lex."""

from __future__ import annotations

from typing import Any


def social_context_payload(question: str, reply: str) -> dict[str, object]:
    return {
        "ok": True,
        "query_type": "social_only",
        "question": "",
        "prompt": "",
        "answer": reply,
        "sources": [],
        "citations": [],
        "attachments": [],
        "focus_label": "",
        "focus_topic": "sociale",
        "web_fallback_used": False,
        "social_kind": "social_only",
        "social_prefix": "",
        "effective_question": "",
        "disable_exports": True,
        "execution_policy": {
            "mode": "social_only",
            "summary_label": "risposta relazionale diretta",
            "llm_role": "nessuno",
            "truth_strategy": "nessun_fatto_sensibile",
            "requires_verified_legal_reference": False,
            "requires_verified_normative_freshness": False,
            "requires_verified_pdf": False,
            "requires_internal_state_source": False,
            "forbid_invented_missing_data": True,
            "allow_web_fallback": False,
            "prompt_block": "",
        },
        "routing": {
            "reason": "social_only",
            "is_social_only": True,
            "is_social_with_request": False,
            "is_daily_overview": False,
            "is_followup": False,
            "reused_previous_topic": False,
            "social_kind": "social_only",
            "social_prefix": "",
            "request_text": "",
            "effective_query": "",
        },
        "followup_resolution": {
            "effective_query": "",
            "is_followup": False,
            "is_web_request": False,
            "needs_web_search": False,
            "reused_previous_topic": False,
            "reason": "social_only",
        },
    }


def direct_answer_payload(
    question: str,
    reply: str,
    *,
    query_type: str = "direct_answer",
    sources: list[dict[str, object]] | None = None,
    citations: list[str] | None = None,
    legal_reference_guard_active: bool = False,
) -> dict[str, object]:
    return {
        "ok": True,
        "query_type": query_type,
        "question": question,
        "prompt": "",
        "answer": reply,
        "sources": list(sources or []),
        "citations": list(citations or []),
        "attachments": [],
        "focus_label": "",
        "focus_topic": "",
        "web_fallback_used": False,
        "social_kind": "",
        "social_prefix": "",
        "effective_question": "",
        "opening_line": "",
        "daily_overview_lead": "",
        "language_mode": "",
        "disable_exports": True,
        "legal_reference_guard_active": bool(legal_reference_guard_active),
        "execution_policy": {
            "mode": query_type,
            "summary_label": "risposta deterministica diretta",
            "llm_role": "nessuno",
            "truth_strategy": "guardia_applicativa",
            "requires_verified_legal_reference": bool(legal_reference_guard_active),
            "requires_verified_normative_freshness": False,
            "requires_verified_pdf": True,
            "requires_internal_state_source": False,
            "forbid_invented_missing_data": True,
            "allow_web_fallback": False,
            "prompt_block": "",
        },
        "routing": {
            "reason": query_type,
            "is_social_only": False,
            "is_social_with_request": False,
            "is_daily_overview": False,
            "is_followup": False,
            "reused_previous_topic": False,
            "social_kind": "",
            "social_prefix": "",
            "request_text": "",
            "effective_query": "",
        },
        "followup_resolution": {
            "effective_query": "",
            "is_followup": False,
            "is_web_request": False,
            "needs_web_search": False,
            "reused_previous_topic": False,
            "reason": query_type,
        },
    }


def routing_payload(routing: Any) -> dict[str, object]:
    return {
        "reason": str(getattr(routing, "reason", "") or "").strip(),
        "is_social_only": bool(getattr(routing, "is_social_only", False)),
        "is_social_with_request": bool(getattr(routing, "is_social_with_request", False)),
        "is_daily_overview": bool(getattr(routing, "is_daily_overview", False)),
        "is_followup": bool(getattr(routing, "is_followup", False)),
        "reused_previous_topic": bool(getattr(routing, "reused_previous_topic", False)),
        "social_kind": str(getattr(routing, "social_kind", "") or "").strip(),
        "social_prefix": str(getattr(routing, "social_prefix", "") or "").strip(),
        "request_text": str(getattr(routing, "request_text", "") or "").strip(),
        "effective_query": str(getattr(routing, "effective_query", "") or "").strip(),
    }


def followup_resolution_payload(followup: Any) -> dict[str, object]:
    return {
        "effective_query": str(getattr(followup, "effective_query", "") or "").strip(),
        "is_followup": bool(getattr(followup, "is_followup", False)),
        "is_web_request": bool(getattr(followup, "is_web_request", False)),
        "needs_web_search": bool(getattr(followup, "needs_web_search", False)),
        "reused_previous_topic": bool(getattr(followup, "reused_previous_topic", False)),
        "reason": str(getattr(followup, "reason", "") or "").strip(),
    }
