"""Lex tool wrapper for the governed operational knowledge layer."""

from __future__ import annotations

from typing import Any

from lex.operational_knowledge.service import OperationalKnowledgeService
from lex.operational_knowledge.settings import OperationalKnowledgeSettings

from .base import BaseLexTool


class OperationalKnowledgeTool(BaseLexTool):
    tool_name = "operational_knowledge"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        question = str(kwargs.get("question") or kwargs.get("query") or "").strip()
        if not question:
            return {"ok": False, "reason": "missing_question"}
        settings = OperationalKnowledgeSettings.from_env()
        if not settings.enabled:
            return {"ok": False, "reason": "feature_flag_disabled"}
        answer = OperationalKnowledgeService(settings=settings).answer(
            question=question,
            user=kwargs.get("user"),
            studio=kwargs.get("studio"),
            tenant_id=str(kwargs.get("tenant_id") or ""),
            metadata=dict(kwargs.get("metadata") or {}),
        )
        if answer is None:
            return {"ok": False, "reason": "not_operational_query"}
        payload = answer.to_dict()
        payload["ok"] = True
        payload.setdefault("workflow", "operational_knowledge")
        payload.setdefault("provider", "deterministic")
        payload.setdefault("metadata", {})
        payload["metadata"].setdefault("workflow", "operational_knowledge")
        payload["metadata"].setdefault("provider", "deterministic")
        return payload
