"""Costruzione delle risposte JSON di Lex."""

from __future__ import annotations

from typing import Any

from .citations import build_citations
from .sections import build_sections
from lex.schemas import LexGroundingResult


class AnswerBuilder:
    def build_chat_payload(
        self,
        *,
        answer: str,
        sources: list[dict[str, Any]] | None,
        grounding: LexGroundingResult,
        mode: str,
    ) -> dict[str, Any]:
        actions = [
            {"key": "summary", "label": "Riassumi fascicolo"},
            {"key": "criticita", "label": "Trova criticita'"},
            {"key": "bozza", "label": "Prepara bozza"},
            {"key": "fonti", "label": "Mostra fonti"},
        ]
        sections = build_sections(answer, grounding.warnings, actions)
        return {
            "ok": True,
            "mode": mode,
            "answer": sections["answer"],
            "grounded": grounding.grounded,
            "confidence": grounding.confidence,
            "warnings": sections["warnings"],
            "sources": list(sources or []),
            "citations": build_citations(sources),
            "actions": sections["actions"],
        }
