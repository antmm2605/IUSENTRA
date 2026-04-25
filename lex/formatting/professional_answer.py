"""Composizione professionale delle risposte finali di Lex.

Questo modulo non genera nuovo contenuto giuridico: organizza la bozza gia'
prodotta dal provider con evidenze, limiti e prossime azioni esplicite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STRICT_WORKFLOWS = {"normativa", "giurisprudenza", "prassi", "research", "fonti"}
PRACTICAL_WORKFLOWS = {
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
HIGH_RISK_LEVELS = {"high", "critical"}


@dataclass(slots=True)
class ProfessionalAnswerResult:
    answer: str
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ProfessionalAnswerComposer:
    """Rende le risposte Lex piu' leggibili, verificabili e operative."""

    def compose(
        self,
        *,
        request: Any,
        context: dict[str, Any] | None,
        workflow: str,
        draft_text: str,
        risk_level: str,
        confidence: float,
        answer_mode: str,
        evidence_count: int,
        official_sources: list[str],
        trusted_sources: list[str],
        considered_sources: list[str],
        missing_evidence: list[str],
        evidence_sufficient: bool,
        fallback_triggered: bool,
        existing_next_actions: list[str],
    ) -> ProfessionalAnswerResult:
        clean_draft = self._clean(draft_text)
        if not clean_draft:
            clean_draft = (
                "Non ho elementi sufficienti per una risposta affidabile. "
                "Serve integrare il contesto o selezionare un fascicolo/documento pertinente."
            )

        sections: list[tuple[str, list[str] | str]] = []
        sections.append((self._main_heading(workflow), clean_draft))

        verified_lines = self._verified_lines(
            workflow=workflow,
            context=context or {},
            evidence_count=evidence_count,
            official_sources=official_sources,
            trusted_sources=trusted_sources,
            considered_sources=considered_sources,
            fallback_triggered=fallback_triggered,
        )
        if verified_lines:
            sections.append(("Quadro verificato", verified_lines))

        human_review_required = self._human_review_required(
            workflow=workflow,
            risk_level=risk_level,
            evidence_sufficient=evidence_sufficient,
            missing_evidence=missing_evidence,
        )
        quality_label = self._quality_label(confidence=confidence, human_review_required=human_review_required)
        quality_lines = self._quality_lines(
            confidence=confidence,
            quality_label=quality_label,
            evidence_count=evidence_count,
            evidence_sufficient=evidence_sufficient,
            human_review_required=human_review_required,
        )
        if quality_lines:
            sections.append(("Qualita della risposta", quality_lines))

        limit_lines = self._limit_lines(
            workflow=workflow,
            risk_level=risk_level,
            answer_mode=answer_mode,
            evidence_count=evidence_count,
            missing_evidence=missing_evidence,
            evidence_sufficient=evidence_sufficient,
        )
        if limit_lines:
            sections.append(("Limiti e verifiche", limit_lines))

        professional_actions = self._next_actions(
            workflow=workflow,
            request=request,
            risk_level=risk_level,
            evidence_sufficient=evidence_sufficient,
            existing_next_actions=existing_next_actions,
            missing_evidence=missing_evidence,
        )
        if professional_actions:
            sections.append(("Prossime azioni", professional_actions))

        warnings: list[str] = []
        if human_review_required:
            warnings.append(
                "Risposta da revisionare: rischio elevato o fonti non ancora complete."
            )

        metadata = {
            "enabled": True,
            "version": "2",
            "workflow": workflow,
            "quality_label": quality_label,
            "human_review_required": human_review_required,
            "sections": [heading for heading, _ in sections],
            "source_profile": self._source_profile(
                official_sources=official_sources,
                trusted_sources=trusted_sources,
                evidence_count=evidence_count,
                fallback_triggered=fallback_triggered,
            ),
        }

        return ProfessionalAnswerResult(
            answer=self._render_sections(sections),
            warnings=warnings,
            next_actions=professional_actions,
            metadata=metadata,
        )

    def _main_heading(self, workflow: str) -> str:
        if workflow in STRICT_WORKFLOWS:
            return "Risposta professionale"
        if workflow in {"fascicolo", "udienza", "telematico", "telematico_status", "compliance"}:
            return "Sintesi operativa"
        if workflow in {"economico", "cabina", "next_action"}:
            return "Presidio operativo"
        return "Risposta"

    def _verified_lines(
        self,
        *,
        workflow: str,
        context: dict[str, Any],
        evidence_count: int,
        official_sources: list[str],
        trusted_sources: list[str],
        considered_sources: list[str],
        fallback_triggered: bool,
    ) -> list[str]:
        lines: list[str] = []
        structured_context = dict(context.get("structured_context") or {})
        fascicolo = structured_context.get("fascicolo") or context.get("fascicolo") or {}
        if isinstance(fascicolo, dict):
            numero = self._clean(str(fascicolo.get("numero") or fascicolo.get("rg") or ""))
            titolo = self._clean(str(fascicolo.get("titolo") or fascicolo.get("oggetto") or ""))
            if numero:
                lines.append(f"Fascicolo considerato: {numero}.")
            elif titolo and workflow in PRACTICAL_WORKFLOWS:
                lines.append(f"Contesto pratica considerato: {titolo}.")

        if evidence_count:
            lines.append(f"Evidenze elaborate: {evidence_count}.")
        if official_sources:
            lines.append("Fonti ufficiali considerate: " + self._join_preview(official_sources) + ".")
        elif trusted_sources:
            lines.append("Fonti interne/verificate considerate: " + self._join_preview(trusted_sources) + ".")
        elif considered_sources:
            lines.append("Fonti considerate: " + self._join_preview(considered_sources) + ".")
        if fallback_triggered:
            lines.append("E' stato usato un fallback controllato verso fonti esterne governate.")
        return self._dedupe(lines)

    def _limit_lines(
        self,
        *,
        workflow: str,
        risk_level: str,
        answer_mode: str,
        evidence_count: int,
        missing_evidence: list[str],
        evidence_sufficient: bool,
    ) -> list[str]:
        lines: list[str] = []
        if not evidence_count:
            lines.append("Non risultano evidenze agganciate alla risposta: serve verificare il contesto sorgente.")
        if missing_evidence:
            for item in missing_evidence[:4]:
                value = self._clean(str(item))
                if value:
                    lines.append(value.rstrip(".") + ".")
            if len(missing_evidence) > 4:
                lines.append(f"Altri gap da verificare: {len(missing_evidence) - 4}.")
        if not evidence_sufficient and workflow in STRICT_WORKFLOWS:
            lines.append("Per una risposta legale conclusiva servono fonti ufficiali o richiami verificati.")
        elif answer_mode != "grounded":
            lines.append("La risposta e' operativa ma richiede controllo umano prima dell'uso esterno.")
        if risk_level in HIGH_RISK_LEVELS:
            lines.append("Rischio alto: non usare la risposta come atto/parere definitivo senza revisione.")
        return self._dedupe(lines)

    def _next_actions(
        self,
        *,
        workflow: str,
        request: Any,
        risk_level: str,
        evidence_sufficient: bool,
        existing_next_actions: list[str],
        missing_evidence: list[str],
    ) -> list[str]:
        actions = list(existing_next_actions or [])
        query = self._clean(str(getattr(request, "query", "") or "")).lower()

        if workflow == "fascicolo":
            actions.append("Apri il fascicolo e controlla documenti, attivita', udienze e comunicazioni citate.")
        elif workflow == "udienza":
            actions.append("Verifica scadenze, documenti preparatori e ultimo provvedimento prima dell'udienza.")
        elif workflow in {"telematico", "telematico_status"}:
            actions.append("Controlla sempre ricevute, esiti e log del portale ufficiale prima di depositare.")
        elif workflow == "compliance":
            actions.append("Chiudi prima i blocchi di conformita' e poi ripeti il controllo pre-deposito.")
        elif workflow in {"economico", "cabina", "next_action"}:
            actions.append("Aggiorna i dati gestionali collegati prima di confermare l'azione al cliente.")
        elif workflow in STRICT_WORKFLOWS:
            actions.append("Verifica le fonti ufficiali e conserva i riferimenti usati nella pratica.")

        if "bozza" in query or "atto" in query:
            actions.append("Prima di redigere, verifica campi obbligatori, allegati e procura.")
        if missing_evidence or not evidence_sufficient:
            actions.append("Integra le evidenze mancanti e rilancia Lex sul contesto aggiornato.")
        if risk_level in HIGH_RISK_LEVELS:
            actions.append("Fai validare la risposta da un professionista prima di inviarla o depositarla.")

        return self._dedupe(actions)[:6]

    def _human_review_required(
        self,
        *,
        workflow: str,
        risk_level: str,
        evidence_sufficient: bool,
        missing_evidence: list[str],
    ) -> bool:
        if risk_level in HIGH_RISK_LEVELS:
            return True
        if missing_evidence:
            return True
        if workflow in STRICT_WORKFLOWS and not evidence_sufficient:
            return True
        return False

    def _quality_lines(
        self,
        *,
        confidence: float,
        quality_label: str,
        evidence_count: int,
        evidence_sufficient: bool,
        human_review_required: bool,
    ) -> list[str]:
        lines = [f"Attendibilita: {quality_label} ({round(confidence * 100)}%)."]
        if evidence_sufficient and evidence_count:
            lines.append("La risposta e' agganciata a evidenze sufficienti per il contesto richiesto.")
        elif evidence_count:
            lines.append("Sono presenti evidenze, ma non bastano ancora per una conclusione pienamente autonoma.")
        else:
            lines.append("Non ci sono evidenze agganciate: usare la risposta solo come orientamento.")
        if human_review_required:
            lines.append("Revisione professionale richiesta prima di uso esterno, deposito o invio al cliente.")
        return lines

    def _quality_label(self, *, confidence: float, human_review_required: bool) -> str:
        if human_review_required:
            return "da revisionare"
        if confidence >= 0.82:
            return "alta"
        if confidence >= 0.62:
            return "media"
        return "bassa"

    def _source_profile(
        self,
        *,
        official_sources: list[str],
        trusted_sources: list[str],
        evidence_count: int,
        fallback_triggered: bool,
    ) -> str:
        if official_sources:
            return "fonti ufficiali"
        if trusted_sources:
            return "fonti interne verificate"
        if evidence_count:
            return "evidenze operative"
        if fallback_triggered:
            return "fallback esterno controllato"
        return "contesto insufficiente"

    def _render_sections(self, sections: list[tuple[str, list[str] | str]]) -> str:
        rendered: list[str] = []
        for heading, body in sections:
            if isinstance(body, str):
                text = self._clean(body)
                if text:
                    rendered.append(f"**{heading}**\n{text}")
                continue
            lines = [self._clean(str(item)) for item in body if self._clean(str(item))]
            if lines:
                rendered.append(f"**{heading}**\n" + "\n".join(f"- {line}" for line in lines))
        return "\n\n".join(rendered).strip()

    def _join_preview(self, values: list[str], limit: int = 4) -> str:
        clean_values = [self._clean(str(value)) for value in values if self._clean(str(value))]
        preview = clean_values[:limit]
        suffix = f" (+{len(clean_values) - limit})" if len(clean_values) > limit else ""
        return ", ".join(preview) + suffix

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            clean = self._clean(value)
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(clean)
        return result

    def _clean(self, value: str) -> str:
        return " ".join(str(value or "").replace("\r", "\n").split())
