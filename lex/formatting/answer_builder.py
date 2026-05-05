"""Costruzione delle risposte JSON di Lex."""

from __future__ import annotations

from typing import Any

from lex.contracts import LexResponse as WorkflowLexResponse
from lex.domain.confidence import compute_confidence
from lex.guards.italian_response_guard import rewrite_or_reject_non_italian_response
from lex.schemas import LexGroundingResult

from .citations import build_citations
from .professional_answer import ProfessionalAnswerComposer
from .sections import build_sections


class AnswerBuilder:
    def build_response(self, request, context, workflow, evidence, draft, verdict) -> WorkflowLexResponse:
        strict_workflow = workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti"}
        practical_workflow = workflow in {
            "fascicolo",
            "udienza",
            "atto",
            "documento",
            "question_answering",
            "economico",
            "next_action",
            "cabina",
            "telematico",
            "telematico_status",
            "compliance",
        }
        citations = list((evidence or {}).get("citations") or [])
        evidence_pack = dict((evidence or {}).get("evidence_pack") or {})
        official_sources = list((evidence or {}).get("official_sources") or evidence_pack.get("official_sources") or [])
        trusted_sources = list((evidence or {}).get("trusted_sources") or evidence_pack.get("trusted_sources") or [])
        if strict_workflow:
            considered_sources = official_sources or trusted_sources or [citation.title for citation in citations if getattr(citation, "title", "")]
        elif practical_workflow:
            considered_sources = [citation.title for citation in citations if getattr(citation, "title", "")]
            if not considered_sources:
                considered_sources = [
                    str(item.get("title") or "").strip()
                    for item in list((evidence or {}).get("items") or [])
                    if isinstance(item, dict) and str(item.get("title") or "").strip()
                ]
            considered_sources = considered_sources[:6]
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
        draft_metadata = dict(getattr(draft, "metadata", {}) or {})
        case_law_warnings = list(draft_metadata.get("case_law_warnings") or [])
        case_law_fallback_used = bool(draft_metadata.get("case_law_fallback_used"))
        legal_quality_warnings = list(draft_metadata.get("legal_quality_warnings") or [])
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
        if workflow == "giurisprudenza" and case_law_fallback_used:
            confidence = min(confidence, 0.68)
        elif workflow == "giurisprudenza" and case_law_warnings:
            confidence = min(confidence, 0.74)
        if legal_quality_warnings:
            confidence = min(confidence, 0.69)
        if not strict_workflow:
            if evidence_sufficient and evidence_count:
                confidence = max(confidence, 0.82 if workflow == "economico" else 0.72)
            elif evidence_count:
                confidence = max(confidence, 0.62)
        if not evidence_sufficient:
            confidence = min(confidence, 0.54)
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
        if not evidence_sufficient and not missing_evidence:
            next_actions.append("Aggancia evidenze, fonti o contesto di fascicolo prima di usare la risposta.")
        if restricted_registry_sources:
            next_actions.append("Se serve una fonte riservata, usa le credenziali o il portale dedicato dello studio")
        elif partner_registry_sources or credentialed_registry_sources:
            next_actions.append("Per le fonti partner, verifica credenziali e abilitazioni prima di chiudere il parere")

        professional = ProfessionalAnswerComposer().compose(
            request=request,
            context=dict(context or {}),
            workflow=workflow,
            draft_text=str(getattr(draft, "text", "") or "").strip(),
            risk_level=str(getattr(verdict, "risk_level", "low") or "low"),
            confidence=confidence,
            answer_mode=answer_mode,
            evidence_count=evidence_count,
            official_sources=official_sources,
            trusted_sources=trusted_sources,
            considered_sources=considered_sources,
            missing_evidence=missing_evidence,
            evidence_sufficient=evidence_sufficient,
            fallback_triggered=fallback_triggered,
            existing_next_actions=next_actions,
        )
        final_answer = rewrite_or_reject_non_italian_response(
            professional.answer,
            {"workflow": workflow, "request": request},
        )
        italian_guard_applied = final_answer != professional.answer
        next_actions = self._unique_strings([*next_actions, *professional.next_actions])
        warnings = self._unique_strings(
            [
                *list(getattr(verdict, "warnings", []) or []),
                *case_law_warnings,
                *legal_quality_warnings,
                *professional.warnings,
                *(["Risposta normalizzata in italiano dal guard linguistico Lex."] if italian_guard_applied else []),
                *([] if evidence_sufficient else ["Evidenze insufficienti: risposta in modalita' needs_review."]),
            ]
        )
        try:
            from lex.telemetry.provenance import build_provenance_envelope

            provenance_envelope = build_provenance_envelope(
                query=str(getattr(request, "query", "") or ""),
                answer=final_answer,
                workflow=workflow,
                provider_metadata=draft_metadata,
                evidence_items=list((evidence or {}).get("items") or []),
                citations=citations,
                parameters={
                    "confidence": confidence,
                    "answer_mode": answer_mode,
                    "risk_level": str(getattr(verdict, "risk_level", "low") or "low"),
                },
            )
        except Exception:
            provenance_envelope = {}

        return WorkflowLexResponse(
            answer=final_answer,
            citations=citations,
            warnings=warnings,
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
                "case_law_guard_applied": bool(draft_metadata.get("case_law_guard_applied")),
                "case_law_fallback_used": case_law_fallback_used,
                "case_law_warnings": case_law_warnings,
                "legal_quality_guard_applied": bool(draft_metadata.get("legal_quality_guard_applied")),
                "legal_quality_warnings": legal_quality_warnings,
                "italian_response_guard_applied": italian_guard_applied,
                "evidence_count": evidence_count,
                "official_sources": official_sources,
                "trusted_sources": trusted_sources,
                "coverage_gaps": missing_evidence,
                "fallback_triggered": fallback_triggered,
                "fascicolo_first": bool(
                    dict(getattr(request, "metadata", {}) or {}).get("fascicolo_first")
                    or evidence_pack.get("metadata", {}).get("fascicolo_first")
                ),
                "external_sources_used": bool(
                    evidence_pack.get("metadata", {}).get("external_sources_used")
                    or fallback_triggered
                    or official_sources
                ),
                "external_sources_reason": (
                    dict(getattr(request, "metadata", {}) or {}).get("external_sources_reason")
                    or evidence_pack.get("metadata", {}).get("external_sources_reason")
                    or None
                ),
                "evidence_sufficient": evidence_sufficient,
                "compared_sources": compared_sources,
                "retrieval_cache": retrieval_cache,
                "source_registry_requested": requested_registry_sources,
                "restricted_sources": restricted_registry_sources,
                "partner_sources": partner_registry_sources,
                "credentialed_sources": credentialed_registry_sources,
                "confidence": confidence,
                "confidence_label": self._confidence_label(confidence),
                "answer_mode": answer_mode,
                "professional_answer": professional.metadata,
                "provenance": provenance_envelope,
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
        clean_answer = rewrite_or_reject_non_italian_response(answer, {"mode": mode})
        sections = build_sections(clean_answer, grounding.warnings, actions)
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

    def _unique_strings(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            clean = str(value or "").strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(clean)
        return result

    def _confidence_label(self, value: float) -> str:
        if value >= 0.8:
            return "alta"
        if value >= 0.55:
            return "media"
        return "bassa"
