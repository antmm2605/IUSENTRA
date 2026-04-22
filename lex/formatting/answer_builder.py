"""Costruzione delle risposte JSON di Lex."""

from __future__ import annotations

from typing import Any

from lex.contracts import LexResponse as WorkflowLexResponse
from lex.domain.confidence import compute_confidence
from lex.schemas import LexGroundingResult

from .citations import build_citations
from .sections import build_sections


class AnswerBuilder:
    def build_response(self, request, context, workflow, evidence, draft, verdict) -> WorkflowLexResponse:
        strict_workflow = workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti"}
        citations = list((evidence or {}).get("citations") or [])
        evidence_pack = dict((evidence or {}).get("evidence_pack") or {})
        official_sources = list((evidence or {}).get("official_sources") or evidence_pack.get("official_sources") or [])
        trusted_sources = list((evidence or {}).get("trusted_sources") or evidence_pack.get("trusted_sources") or [])
        if strict_workflow:
            considered_sources = official_sources or trusted_sources or [citation.title for citation in citations if getattr(citation, "title", "")]
        else:
            compared_sources_preview = list((evidence or {}).get("source_comparison") or evidence_pack.get("compared_sources") or [])
            considered_sources = [
                str(item.get("title") or "").strip()
                for item in compared_sources_preview
                if str(item.get("title") or "").strip()
            ] or [citation.title for citation in citations if getattr(citation, "title", "")]
        missing_evidence = list((evidence or {}).get("coverage_gaps") or evidence_pack.get("coverage_gaps") or [])
        compared_sources = list((evidence or {}).get("source_comparison") or evidence_pack.get("compared_sources") or [])
        fallback_triggered = bool((evidence or {}).get("fallback_triggered") or evidence_pack.get("fallback_triggered"))
        evidence_sufficient = bool((evidence or {}).get("evidence_sufficient") or evidence_pack.get("sufficient"))
        retrieval_cache = dict((evidence or {}).get("cache") or {})
        requested_registry_sources = list(evidence_pack.get("metadata", {}).get("source_registry_requested") or [])
        restricted_registry_sources = list(evidence_pack.get("metadata", {}).get("source_registry_restricted") or [])
        partner_registry_sources = list(evidence_pack.get("metadata", {}).get("source_registry_partner") or [])
        credentialed_registry_sources = list(evidence_pack.get("metadata", {}).get("source_registry_credentialed") or [])
        evidence_count = len(list((evidence or {}).get("items") or []))
        aggregate_trust = float(evidence_pack.get("aggregate_trust_score") or 0.0)
        aggregate_freshness = float(evidence_pack.get("aggregate_freshness_score") or 0.0)
        aggregate_context = float(evidence_pack.get("aggregate_context_fit_score") or 0.0)
        aggregate_consensus = float(evidence_pack.get("aggregate_consensus_score") or 0.0)
        confidence = compute_confidence(evidence_count)
        if any(value > 0 for value in (aggregate_trust, aggregate_freshness, aggregate_context, aggregate_consensus)):
            confidence = (
                confidence * 0.35
                + aggregate_trust * 0.25
                + aggregate_freshness * 0.10
                + aggregate_context * 0.15
                + aggregate_consensus * 0.15
            )
        if official_sources:
            confidence += 0.05
        if missing_evidence:
            confidence -= min(0.2, len(missing_evidence) * 0.05)
        if str(getattr(verdict, "risk_level", "low") or "low") in {"high", "critical"}:
            confidence -= 0.1
        if not strict_workflow:
            if evidence_sufficient and evidence_count:
                confidence = max(confidence, 0.82 if workflow == "economico" else 0.72)
            elif evidence_count:
                confidence = max(confidence, 0.62)
        confidence = max(0.0, min(0.99, round(confidence, 4)))
        answer_mode = "grounded" if evidence_sufficient else "needs_review"
        next_actions: list[str] = []
        if workflow in {"telematico", "telematico_status"}:
            next_actions.append("Verifica canale ed esito ufficiale prima di procedere")
        if workflow == "udienza":
            next_actions.append("Controlla documenti chiave e scadenze collegate")
        if workflow == "atto":
            next_actions.append("Verifica campi mancanti, allegati e conformita del modello")
        if workflow in {"economico", "cabina", "next_action"}:
            next_actions.append("Conferma i dati operativi nel modulo sorgente prima di eseguire l'azione")
        if fallback_triggered:
            next_actions.append("Verifica le fonti esterne ufficiali utilizzate nel fallback")
        if missing_evidence and "Colma i gap di evidenza prima di chiudere la risposta" not in next_actions:
            next_actions.append("Colma i gap di evidenza prima di chiudere la risposta")
        if restricted_registry_sources:
            next_actions.append("Se serve una fonte riservata, usa le credenziali o il portale dedicato dello studio")
        elif partner_registry_sources or credentialed_registry_sources:
            next_actions.append("Per le fonti partner, verifica credenziali e abilitazioni prima di chiudere il parere")

        return WorkflowLexResponse(
            answer=str(getattr(draft, "text", "") or "").strip(),
            citations=citations,
            warnings=list(getattr(verdict, "warnings", []) or []),
            next_actions=next_actions,
            risk_level=str(getattr(verdict, "risk_level", "low") or "low"),
            legal_basis=(official_sources or trusted_sources) if strict_workflow else [],
            considered_sources=considered_sources,
            compared_sources=compared_sources,
            missing_evidence=missing_evidence,
            confidence=confidence,
            answer_mode=answer_mode,
            evidence_summary={
                "evidence_count": evidence_count,
                "official_count": len(official_sources),
                "trusted_count": len(trusted_sources),
                "fallback_triggered": fallback_triggered,
                "evidence_sufficient": evidence_sufficient,
                "requested_source_count": len(requested_registry_sources),
                "restricted_source_count": len(restricted_registry_sources),
                "partner_source_count": len(partner_registry_sources),
            },
            metadata={
                "workflow": workflow,
                "provider": str(getattr(draft, "metadata", {}).get("provider") or ""),
                "evidence_count": evidence_count,
                "official_sources": official_sources,
                "trusted_sources": trusted_sources,
                "coverage_gaps": missing_evidence,
                "fallback_triggered": fallback_triggered,
                "evidence_sufficient": evidence_sufficient,
                "compared_sources": compared_sources,
                "retrieval_cache": retrieval_cache,
                "source_registry_requested": requested_registry_sources,
                "restricted_sources": restricted_registry_sources,
                "partner_sources": partner_registry_sources,
                "credentialed_sources": credentialed_registry_sources,
                "confidence": confidence,
                "answer_mode": answer_mode,
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
            "confidence_label": grounding.confidence_label,
            "confidence_reason": grounding.reasoning,
            "warnings": sections["warnings"],
            "sources": list(sources or []),
            "citations": build_citations(sources),
            "actions": sections["actions"],
        }
