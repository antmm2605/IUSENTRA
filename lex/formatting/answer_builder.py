"""Costruzione delle risposte JSON di Lex."""

from __future__ import annotations

from typing import Any

from lex.contracts import LexResponse as WorkflowLexResponse
from .citations import build_citations
from .sections import build_sections
from lex.schemas import LexGroundingResult


class AnswerBuilder:
    def build_response(self, request, context, workflow, evidence, draft, verdict) -> WorkflowLexResponse:
        citations = list((evidence or {}).get("citations") or [])
        next_actions: list[str] = []
        if workflow == "telematico":
            next_actions.append("Verifica canale ed esito ufficiale prima di procedere")
        if workflow == "udienza":
            next_actions.append("Controlla documenti chiave e scadenze collegate")
        if workflow == "atto":
            next_actions.append("Verifica campi mancanti, allegati e conformita del modello")

        return WorkflowLexResponse(
            answer=str(getattr(draft, "text", "") or "").strip(),
            citations=citations,
            warnings=list(getattr(verdict, "warnings", []) or []),
            next_actions=next_actions,
            risk_level=str(getattr(verdict, "risk_level", "low") or "low"),
            metadata={
                "workflow": workflow,
                "provider": str(getattr(draft, "metadata", {}).get("provider") or ""),
                "evidence_count": len(list((evidence or {}).get("items") or [])),
            },
        )

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
