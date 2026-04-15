"""Risoluzione del workflow applicativo di Lex."""

from __future__ import annotations

from .contracts import LexRequest
from .types import WorkflowType


class LexRouter:
    def resolve_workflow(self, request: LexRequest) -> WorkflowType:
        if request.intent == "prepare_udienza":
            return "udienza"
        if request.intent in {"draft_act_support", "validate_draft"}:
            return "atto"
        if request.intent == "summarize_fascicolo":
            return "fascicolo"
        if request.intent == "explain_telematico_error":
            return "telematico"
        if request.intent == "suggest_next_action":
            return "next_action"
        if request.intent in {"analyze_document", "compare_documents"}:
            return "fascicolo"
        return "chat"
