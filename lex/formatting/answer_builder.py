"""Costruzione delle risposte JSON di Lex."""

from __future__ import annotations

from typing import Any

from lex.contracts import LexResponse as WorkflowLexResponse
from lex.domain.confidence import compute_confidence
from lex.guards.italian_response_guard import rewrite_or_reject_non_italian_response
from lex.guards.user_facing_output_guard import check_output_safety
from lex.research.case_law_exact_search import parse_case_law_reference
from lex.schemas import LexGroundingResult

from .citations import build_citations
from .professional_answer import ProfessionalAnswerComposer
from .sections import build_sections

_DRAFTING_LETTER_WORKFLOWS = {"drafting_legal_letter", "lettera", "bozza_lettera", "pec_comunicazioni"}


class AnswerBuilder:
    def build_response(self, request, context, workflow, evidence, draft, verdict) -> WorkflowLexResponse:
        strict_workflow = workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti", "giurisprudenza_specifica"}
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
            "deposito_telematico",
            "compliance",
        }
        citations = list((evidence or {}).get("citations") or [])
        evidence_pack = dict((evidence or {}).get("evidence_pack") or {})
        # studio_data_lookup: nessuna fonte esterna, nessuna citazione da sentenze
        if workflow == "studio_data_lookup":
            official_sources = []
            trusted_sources = []
            considered_sources = []
        else:
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
        source_context_lines = self._source_context_lines(evidence or {})
        if strict_workflow and considered_sources and not source_context_lines:
            missing_evidence.append("Le fonti agganciate non contengono un estratto testuale sufficiente.")
            evidence_sufficient = False
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
        # Sentenza specifica: confidence massima 0.45 senza exact_match, 0.55 senza testo completo
        if workflow == "giurisprudenza_specifica":
            exact_match = bool(evidence_pack.get("metadata", {}).get("exact_match_found"))
            has_full_text = bool(evidence_pack.get("metadata", {}).get("has_full_text"))
            if not exact_match:
                confidence = min(confidence, 0.45)
            elif not has_full_text:
                confidence = min(confidence, 0.55)
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
        # Per studio_data_lookup: non mostrare "grounded" (è lookup, non reasoning)
        if workflow == "studio_data_lookup":
            answer_mode = "lookup"
        elif workflow == "giurisprudenza_specifica" and not bool(evidence_pack.get("metadata", {}).get("exact_match_found")):
            answer_mode = "needs_review"
        else:
            answer_mode = "grounded" if evidence_sufficient else "needs_review"
        next_actions: list[str] = []
        if workflow in {"telematico", "telematico_status", "deposito_telematico"}:
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

        if workflow == "studio_data_lookup":
            return self._build_studio_data_lookup_response(
                request=request,
                draft=draft,
                verdict=verdict,
            )

        if workflow == "giurisprudenza_specifica":
            return self._build_case_law_specific_response(
                request=request,
                evidence=evidence,
                draft=draft,
                verdict=verdict,
                confidence=confidence,
            )

        if workflow in _DRAFTING_LETTER_WORKFLOWS:
            return self._build_drafting_letter_response(
                request=request,
                draft=draft,
                verdict=verdict,
                confidence=max(confidence, 0.72),
            )

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
            source_context_lines=source_context_lines,
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
        output_safe, sanitized_answer = check_output_safety(
            final_answer,
            workflow=workflow,
            question=str(getattr(request, "query", "") or ""),
        )
        output_guard_applied = sanitized_answer != final_answer or not output_safe
        final_answer = sanitized_answer
        next_actions = self._unique_strings([*next_actions, *professional.next_actions])
        warnings = self._unique_strings(
            [
                *list(getattr(verdict, "warnings", []) or []),
                *case_law_warnings,
                *legal_quality_warnings,
                *professional.warnings,
                *(["Risposta normalizzata in italiano dal guard linguistico Lex."] if italian_guard_applied else []),
                *(["Output tecnico rimosso dalla risposta utente."] if output_guard_applied else []),
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

        metadata_workflow = {
            "giurisprudenza_specifica": "giurisprudenza",
            "deposito_telematico": "telematico_status",
        }.get(workflow, workflow)
        workflow_detail = workflow if metadata_workflow != workflow else ""

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
                "workflow": metadata_workflow,
                "workflow_detail": workflow_detail,
                "provider": str(getattr(draft, "metadata", {}).get("provider") or ""),
                "case_law_guard_applied": bool(draft_metadata.get("case_law_guard_applied")),
                "case_law_fallback_used": case_law_fallback_used,
                "case_law_warnings": case_law_warnings,
                "legal_quality_guard_applied": bool(draft_metadata.get("legal_quality_guard_applied")),
                "legal_quality_warnings": legal_quality_warnings,
                "italian_response_guard_applied": italian_guard_applied,
                "user_facing_output_guard_applied": output_guard_applied,
                "evidence_count": evidence_count,
                "official_sources": official_sources,
                "trusted_sources": trusted_sources,
                "coverage_gaps": missing_evidence,
                "source_context_lines": source_context_lines,
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

    def _source_context_lines(self, evidence: dict[str, Any]) -> list[str]:
        rows: list[str] = []
        for item in list((evidence or {}).get("items") or [])[:8]:
            if isinstance(item, dict):
                title = str(item.get("title") or item.get("source_name") or item.get("authority") or "").strip()
                text = str(item.get("content") or item.get("excerpt") or item.get("text") or "").strip()
                url = str(item.get("official_url") or item.get("url") or "").strip()
            else:
                title = str(getattr(item, "title", "") or getattr(item, "authority", "") or "").strip()
                text = str(getattr(item, "content", "") or getattr(item, "excerpt", "") or "").strip()
                url = str(getattr(item, "official_url", "") or getattr(item, "url", "") or "").strip()
                metadata = getattr(item, "metadata", None)
                if not url and isinstance(metadata, dict):
                    url = str(metadata.get("official_url") or metadata.get("url") or "").strip()
            title = self._clean_text(title)
            text = self._clean_text(text)
            if not title or not text:
                continue
            if len(text) > 260:
                text = text[:257].rstrip() + "..."
            suffix = f" ({url})" if url else ""
            rows.append(f"Contesto fonte - {title}{suffix}: {text}")
        return self._unique_strings(rows)

    def _clean_text(self, value: str) -> str:
        return " ".join(str(value or "").replace("\r", "\n").split()).strip()

    def _build_case_law_specific_response(
        self,
        *,
        request,
        evidence: dict[str, Any],
        draft,
        verdict,
        confidence: float,
    ) -> WorkflowLexResponse:
        evidence_pack = dict((evidence or {}).get("evidence_pack") or {})
        metadata = dict(evidence_pack.get("metadata") or {})
        reference = parse_case_law_reference(str(getattr(request, "query", "") or ""))
        number = metadata.get("official_number") or reference.number
        date = metadata.get("official_date") or reference.date
        kind = str(metadata.get("exact_reference_kind") or reference.kind or "sentenza").capitalize()
        pronuncia = f"{kind} n. {number}" + (f" del {date}" if date else "")
        exact_match = bool(metadata.get("exact_match_found"))
        official_url = str(metadata.get("official_url") or "")
        official_title = str(metadata.get("official_title") or pronuncia)
        official_court = str(metadata.get("official_court") or reference.court or "fonte ufficiale")
        has_full_text = bool(metadata.get("has_full_text"))
        has_dispositivo = bool(metadata.get("has_dispositivo"))
        has_motivazione = bool(metadata.get("has_motivazione"))
        local_fragment_found = bool(metadata.get("local_case_law_fragment_found"))
        official_search_run = bool(metadata.get("official_search_run"))
        web_blocked_reason = str(metadata.get("web_blocked_reason") or "")
        cap = float(metadata.get("confidence_cap") or (0.55 if exact_match else 0.45))
        confidence = min(confidence, cap)
        missing_parts = list(metadata.get("local_case_law_missing_parts") or [])
        if not has_full_text:
            missing_parts.append("testo integrale")
        if not has_motivazione:
            missing_parts.append("motivazione")
        if not has_dispositivo:
            missing_parts.append("dispositivo")
        if not official_url:
            missing_parts.append("URL/PDF ufficiale")
        missing_parts = self._unique_strings([str(item) for item in missing_parts if str(item or "").strip()])

        if exact_match:
            certain = [f"Numero e data risultano coerenti con il riferimento richiesto: {pronuncia}."]
            if official_url:
                certain.append("La fonte e' un dominio ufficiale o riconosciuto.")
            answer_lines = [
                "Ho individuato la pronuncia richiesta.",
                "",
                f"Pronuncia: {pronuncia}",
                f"Fonte: {official_court}",
                f"Link ufficiale: {official_url or 'non disponibile'}",
                "",
                "Cosa e' certo:",
                *[f"- {item}" for item in certain],
                "",
                "Cosa manca:",
                *([f"- {item}" for item in missing_parts] if missing_parts else ["- nessun elemento essenziale tra quelli disponibili"]),
                "",
                "Uso pratico:",
                "Prima di citarla in un atto o parere, acquisisci o verifica il testo integrale ufficiale.",
                "",
                "Prossima azione:",
                "Apri la fonte ufficiale e conserva il riferimento nel fascicolo.",
            ]
            answer_mode = "grounded" if has_full_text else "needs_review"
            considered_sources = [official_title]
            legal_basis = [official_title]
        else:
            reason_line = (
                "La ricerca web ufficiale non e' disponibile o non e' riuscita: " + web_blocked_reason
                if web_blocked_reason
                else "Non considero sufficienti risultati generici o sentenze diverse."
            )
            fragment_line = (
                "Ho trovato solo un frammento locale, che considero un indizio e non una fonte completa."
                if local_fragment_found
                else "Non ho trovato una fonte completa verificabile nelle evidenze disponibili."
            )
            answer_lines = [
                "Non posso completare una risposta legale affidabile con i riferimenti oggi verificati.",
                "",
                f"Non ho trovato una conferma ufficiale esatta della {pronuncia} nelle fonti interrogate.",
                "",
                fragment_line,
                reason_line,
                "",
                "Prossima azione:",
                "verifica manualmente sul portale ufficiale oppure carica il link, il PDF o il testo integrale della pronuncia.",
            ]
            answer_mode = "needs_review"
            considered_sources = []
            legal_basis = []

        final_answer = "\n".join(answer_lines).strip()
        final_answer = rewrite_or_reject_non_italian_response(final_answer, {"workflow": "giurisprudenza_specifica", "request": request})
        _, final_answer = check_output_safety(
            final_answer,
            workflow="giurisprudenza_specifica",
            question=str(getattr(request, "query", "") or ""),
        )
        warnings = self._unique_strings(
            [
                *list(getattr(verdict, "warnings", []) or []),
                *list(metadata.get("case_law_warnings") or []),
                *([] if official_search_run else ["Ricerca ufficiale non eseguita o non disponibile."]),
                *([] if exact_match else ["Conferma ufficiale esatta non trovata."]),
            ]
        )
        next_actions = self._unique_strings(
            [
                "Verifica o acquisisci il testo integrale ufficiale prima dell'uso in atto.",
            ]
        )
        retrieved_count = len(list((evidence or {}).get("items") or []))
        discarded_count = int(metadata.get("discarded_unrelated_case_law_count") or 0)
        coverage_gaps = self._unique_strings(
            [
                *list((evidence or {}).get("coverage_gaps") or []),
                *list(evidence_pack.get("coverage_gaps") or []),
            ]
        )
        response_metadata = {
            **metadata,
            "workflow": "giurisprudenza",
            "workflow_detail": "giurisprudenza_specifica",
            "provider": str(getattr(draft, "metadata", {}).get("provider") or ""),
            "confidence": confidence,
            "confidence_label": self._confidence_label(confidence),
            "answer_mode": answer_mode,
            "evidence_sufficient": bool(exact_match and has_full_text),
            "coverage_gaps": coverage_gaps or missing_parts,
        }
        return WorkflowLexResponse(
            answer=final_answer,
            citations=[],
            warnings=warnings,
            next_actions=next_actions,
            risk_level=str(getattr(verdict, "risk_level", "high") or "high"),
            legal_basis=legal_basis,
            considered_sources=considered_sources,
            compared_sources=[],
            missing_evidence=missing_parts,
            confidence=confidence,
            answer_mode=answer_mode,
            evidence_summary={
                "retrieved_count": retrieved_count,
                "exact_match_count": 1 if exact_match else 0,
                "relevant_count": 1 if exact_match else 0,
                "discarded_count": discarded_count,
                "local_fragment_found": local_fragment_found,
                "completed_from_web": bool(metadata.get("completed_from_web")),
                "official_search_run": official_search_run,
                "evidence_sufficient": bool(exact_match and has_full_text),
            },
            metadata=response_metadata,
        )

    def _build_studio_data_lookup_response(self, *, request, draft, verdict) -> WorkflowLexResponse:
        lookup_meta: dict[str, Any] = {}
        answer = str(getattr(draft, "text", "") or "").strip()
        try:
            from lex.tools.studio_data_gateway import build_cliente_answer, find_cliente

            lookup = find_cliente(str(getattr(request, "query", "") or ""))
            answer = build_cliente_answer(lookup)
            lookup_meta = {
                "studio_data_lookup_used": True,
                "studio_data_lookup_type": lookup.lookup_type,
                "studio_data_lookup_query": lookup.query,
                "studio_data_lookup_cleaned_query": lookup.cleaned_query,
                "studio_data_lookup_matches": len(lookup.matches),
                "studio_data_lookup_status": lookup.status,
                "web_used": False,
                "web_forbidden_reason": "Richiesta dati interni studio",
            }
        except Exception:
            lookup_meta = {
                "studio_data_lookup_used": True,
                "studio_data_lookup_type": "cliente",
                "studio_data_lookup_query": str(getattr(request, "query", "") or ""),
                "studio_data_lookup_cleaned_query": str(getattr(request, "query", "") or ""),
                "studio_data_lookup_matches": 0,
                "studio_data_lookup_status": "error",
                "web_used": False,
                "web_forbidden_reason": "Richiesta dati interni studio",
            }
        answer = rewrite_or_reject_non_italian_response(answer, {"workflow": "studio_data_lookup", "request": request})
        _, answer = check_output_safety(
            answer,
            workflow="studio_data_lookup",
            question=str(getattr(request, "query", "") or ""),
        )
        status = str(lookup_meta.get("studio_data_lookup_status") or "not_found")
        confidence = {"found": 0.86, "multiple_matches": 0.62, "not_found": 0.42, "error": 0.25}.get(status, 0.42)
        return WorkflowLexResponse(
            answer=answer,
            citations=[],
            warnings=list(getattr(verdict, "warnings", []) or []),
            next_actions=["Apri la scheda cliente o aggiorna l'anagrafica se mancano dati."],
            risk_level=str(getattr(verdict, "risk_level", "low") or "low"),
            legal_basis=[],
            considered_sources=[],
            compared_sources=[],
            missing_evidence=[],
            confidence=confidence,
            answer_mode="lookup",
            evidence_summary={
                "lookup_status": status,
                "lookup_type": lookup_meta.get("studio_data_lookup_type") or "cliente",
                "match_count": int(lookup_meta.get("studio_data_lookup_matches") or 0),
                "web_used": False,
            },
            metadata={
                "workflow": "studio_data_lookup",
                "provider": str(getattr(draft, "metadata", {}).get("provider") or "deterministic"),
                "answer_mode": "lookup",
                "confidence": confidence,
                "confidence_label": self._confidence_label(confidence),
                "studio_internal_only": True,
                "external_sources_used": False,
                **lookup_meta,
            },
        )

    def _build_drafting_letter_response(self, *, request, draft, verdict, confidence: float) -> WorkflowLexResponse:
        answer = str(getattr(draft, "text", "") or "").strip()
        answer = rewrite_or_reject_non_italian_response(answer, {"workflow": "drafting_legal_letter", "request": request})
        _, answer = check_output_safety(
            answer,
            workflow="drafting_legal_letter",
            question=str(getattr(request, "query", "") or ""),
        )
        confidence = max(0.0, min(0.99, round(float(confidence or 0.72), 4)))
        return WorkflowLexResponse(
            answer=answer,
            citations=[],
            warnings=list(getattr(verdict, "warnings", []) or []),
            next_actions=[
                "Completa i campi mancanti prima dell'invio.",
                "Verifica allegati, importi, termini e procura o mandato prima della spedizione.",
            ],
            risk_level=str(getattr(verdict, "risk_level", "medium") or "medium"),
            legal_basis=[],
            considered_sources=[],
            compared_sources=[],
            missing_evidence=[],
            confidence=confidence,
            answer_mode="draft",
            evidence_summary={
                "drafting_template": True,
                "evidence_sufficient": True,
                "unrelated_sources_suppressed": True,
            },
            metadata={
                "workflow": "drafting_legal_letter",
                "provider": str(getattr(draft, "metadata", {}).get("provider") or "deterministic"),
                "answer_mode": "draft",
                "confidence": confidence,
                "confidence_label": self._confidence_label(confidence),
                "external_sources_used": False,
                "unrelated_sources_suppressed": True,
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
