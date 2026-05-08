"""Composizione professionale delle risposte finali di Lex.

Struttura in 10 sezioni per ogni risposta legale importante:
  1. Sintesi operativa
  2. Fonti consultate
  3. Dato certo
  4. Ragionamento
  5. Applicazione pratica al fascicolo (se presente)
  6. Rischi e punti da verificare
  7. Prossime azioni
  8. Confidence
  9. Missing evidence
 10. Warning

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

# Workflow che richiedono la struttura completa in 10 sezioni
FULL_STRUCTURE_WORKFLOWS = STRICT_WORKFLOWS | PRACTICAL_WORKFLOWS


@dataclass(slots=True)
class ProfessionalAnswerResult:
    answer: str
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ProfessionalAnswerComposer:
    """Rende le risposte Lex leggibili, verificabili e operative.

    Per ogni risposta legale importante produce una struttura in 10 sezioni
    distinte: fonte, ragionamento e prudenza sono sempre separati e mai
    mescolati nella narrazione.

    Quando answer_mode='needs_review': risposta breve ma utile,
    missing_evidence valorizzato, next_actions concrete.
    """

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

        needs_review = answer_mode == "needs_review"
        ctx = dict(context or {})

        human_review_required = self._human_review_required(
            workflow=workflow,
            risk_level=risk_level,
            evidence_sufficient=evidence_sufficient,
            missing_evidence=missing_evidence,
        )
        quality_label = self._quality_label(
            confidence=confidence,
            human_review_required=human_review_required,
        )

        # Calcola prossime azioni prima di costruire le sezioni
        professional_actions = self._next_actions(
            workflow=workflow,
            request=request,
            risk_level=risk_level,
            evidence_sufficient=evidence_sufficient,
            existing_next_actions=existing_next_actions,
            missing_evidence=missing_evidence,
        )

        # Costruzione sezioni 1-10
        sections: list[tuple[str, list[str] | str]] = []

        # ------------------------------------------------------------------ #
        # Sezione 1 — Sintesi operativa                                        #
        # ------------------------------------------------------------------ #
        sections.append((self._main_heading(workflow), clean_draft))

        # ------------------------------------------------------------------ #
        # Sezione 2 — Fonti consultate                                         #
        # ------------------------------------------------------------------ #
        fonti_lines = self._fonti_lines(
            official_sources=official_sources,
            trusted_sources=trusted_sources,
            considered_sources=considered_sources,
            evidence_count=evidence_count,
            fallback_triggered=fallback_triggered,
        )
        if fonti_lines:
            sections.append(("Fonti consultate", fonti_lines))

        # ------------------------------------------------------------------ #
        # Sezione 3 — Dato certo                                               #
        # (solo se vi sono fonti ufficiali o evidenze sufficienti)             #
        # ------------------------------------------------------------------ #
        dato_certo_lines = self._dato_certo_lines(
            workflow=workflow,
            official_sources=official_sources,
            trusted_sources=trusted_sources,
            evidence_count=evidence_count,
            evidence_sufficient=evidence_sufficient,
        )
        if dato_certo_lines:
            sections.append(("Dato certo", dato_certo_lines))

        # ------------------------------------------------------------------ #
        # Sezione 4 — Ragionamento                                             #
        # (visibile in workflow strict o quando evidence_sufficient)           #
        # ------------------------------------------------------------------ #
        ragionamento_lines = self._ragionamento_lines(
            workflow=workflow,
            confidence=confidence,
            quality_label=quality_label,
            evidence_count=evidence_count,
            evidence_sufficient=evidence_sufficient,
        )
        if ragionamento_lines:
            sections.append(("Ragionamento", ragionamento_lines))

        # ------------------------------------------------------------------ #
        # Sezione 5 — Applicazione pratica al fascicolo (se presente)          #
        # ------------------------------------------------------------------ #
        fascicolo_lines = self._fascicolo_lines(
            workflow=workflow,
            context=ctx,
        )
        if fascicolo_lines:
            sections.append(("Applicazione pratica al fascicolo", fascicolo_lines))

        # ------------------------------------------------------------------ #
        # Sezione 6 — Rischi e punti da verificare                             #
        # ------------------------------------------------------------------ #
        rischi_lines = self._rischi_lines(
            workflow=workflow,
            risk_level=risk_level,
            answer_mode=answer_mode,
            evidence_count=evidence_count,
            evidence_sufficient=evidence_sufficient,
        )
        if rischi_lines:
            sections.append(("Rischi e punti da verificare", rischi_lines))

        # ------------------------------------------------------------------ #
        # Sezione 7 — Prossime azioni                                          #
        # ------------------------------------------------------------------ #
        if professional_actions:
            sections.append(("Prossime azioni", professional_actions))

        # ------------------------------------------------------------------ #
        # Sezione 8 — Confidence                                               #
        # ------------------------------------------------------------------ #
        confidence_lines = self._confidence_lines(
            confidence=confidence,
            quality_label=quality_label,
            human_review_required=human_review_required,
        )
        if confidence_lines:
            sections.append(("Confidence", confidence_lines))

        # ------------------------------------------------------------------ #
        # Sezione 9 — Missing evidence                                         #
        # ------------------------------------------------------------------ #
        missing_lines = self._missing_evidence_lines(
            missing_evidence=missing_evidence,
            needs_review=needs_review,
        )
        if missing_lines:
            sections.append(("Evidenze mancanti", missing_lines))

        # ------------------------------------------------------------------ #
        # Sezione 10 — Warning                                                 #
        # ------------------------------------------------------------------ #
        warning_lines = self._warning_lines(
            workflow=workflow,
            risk_level=risk_level,
            evidence_sufficient=evidence_sufficient,
            human_review_required=human_review_required,
            fallback_triggered=fallback_triggered,
        )
        if warning_lines:
            sections.append(("Avvertenze", warning_lines))

        # Warnings strutturati per il chiamante
        warnings: list[str] = []
        if human_review_required:
            warnings.append(
                "Risposta da revisionare: rischio elevato o fonti non ancora complete."
            )
        if risk_level in HIGH_RISK_LEVELS:
            warnings.append(
                "Rischio elevato: verificare prima di qualsiasi atto esterno o deposito."
            )
        if needs_review and missing_evidence:
            for item in missing_evidence[:3]:
                clean_item = self._clean(str(item))
                if clean_item:
                    warnings.append(f"Evidenza mancante: {clean_item.rstrip('.')}.")

        metadata = {
            "enabled": True,
            "version": "3",
            "workflow": workflow,
            "quality_label": quality_label,
            "human_review_required": human_review_required,
            "answer_mode": answer_mode,
            "sections": [heading for heading, _ in sections],
            "section_count": len(sections),
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

    # ------------------------------------------------------------------ #
    # Sezione helpers                                                       #
    # ------------------------------------------------------------------ #

    def _main_heading(self, workflow: str) -> str:
        if workflow in STRICT_WORKFLOWS:
            return "Sintesi operativa"
        if workflow in {"fascicolo", "udienza", "telematico", "telematico_status", "compliance"}:
            return "Sintesi operativa"
        if workflow in {"economico", "cabina", "next_action"}:
            return "Sintesi operativa"
        return "Sintesi operativa"

    def _fonti_lines(
        self,
        *,
        official_sources: list[str],
        trusted_sources: list[str],
        considered_sources: list[str],
        evidence_count: int,
        fallback_triggered: bool,
    ) -> list[str]:
        lines: list[str] = []
        if official_sources:
            lines.append("Fonti ufficiali: " + self._join_preview(official_sources) + ".")
        if trusted_sources:
            lines.append("Fonti interne verificate: " + self._join_preview(trusted_sources) + ".")
        if considered_sources and not official_sources and not trusted_sources:
            lines.append("Fonti considerate: " + self._join_preview(considered_sources) + ".")
        if evidence_count:
            lines.append(f"Evidenze elaborate: {evidence_count}.")
        if fallback_triggered:
            lines.append("Fallback controllato attivato verso fonti esterne governate.")
        return self._dedupe(lines)

    def _dato_certo_lines(
        self,
        *,
        workflow: str,
        official_sources: list[str],
        trusted_sources: list[str],
        evidence_count: int,
        evidence_sufficient: bool,
    ) -> list[str]:
        lines: list[str] = []
        if official_sources and evidence_sufficient:
            lines.append(
                "Risposta basata su fonti ufficiali verificate: "
                + self._join_preview(official_sources, limit=3) + "."
            )
        elif trusted_sources and evidence_sufficient:
            lines.append(
                "Risposta basata su fonti interne verificate: "
                + self._join_preview(trusted_sources, limit=3) + "."
            )
        elif evidence_count and evidence_sufficient:
            lines.append(
                f"Risposta agganciata a {evidence_count} "
                f"{'evidenza' if evidence_count == 1 else 'evidenze'} sufficienti."
            )
        elif not evidence_sufficient:
            lines.append(
                "Le fonti disponibili non sono sufficienti per un dato certo: "
                "la risposta e' orientativa."
            )
        return lines

    def _ragionamento_lines(
        self,
        *,
        workflow: str,
        confidence: float,
        quality_label: str,
        evidence_count: int,
        evidence_sufficient: bool,
    ) -> list[str]:
        lines: list[str] = []
        if workflow in STRICT_WORKFLOWS:
            if evidence_sufficient and evidence_count:
                lines.append(
                    "Le evidenze ufficiali disponibili supportano la risposta con "
                    f"attendibilita' {quality_label} ({round(confidence * 100)}%)."
                )
            elif evidence_count:
                lines.append(
                    "Evidenze presenti ma non ancora conclusive per una risposta autonoma: "
                    "la risposta richiede verifica professionale."
                )
            else:
                lines.append(
                    "Non ci sono evidenze agganciate: la risposta e' orientativa "
                    "e richiede integrazione di fonti ufficiali."
                )
        elif workflow in PRACTICAL_WORKFLOWS:
            if evidence_sufficient:
                lines.append(
                    f"Ragionamento su evidenze operative sufficienti "
                    f"(attendibilita': {quality_label})."
                )
            elif evidence_count:
                lines.append(
                    "Evidenze operative presenti ma parziali: "
                    "controllare il contesto prima dell'uso esterno."
                )
        return lines

    def _fascicolo_lines(
        self,
        *,
        workflow: str,
        context: dict[str, Any],
    ) -> list[str]:
        lines: list[str] = []
        structured_context = dict(context.get("structured_context") or {})
        fascicolo = structured_context.get("fascicolo") or context.get("fascicolo") or {}
        if not isinstance(fascicolo, dict):
            return []
        numero = self._clean(str(fascicolo.get("numero") or fascicolo.get("rg") or ""))
        titolo = self._clean(str(fascicolo.get("titolo") or fascicolo.get("oggetto") or ""))
        ufficio = self._clean(str(fascicolo.get("ufficio") or fascicolo.get("tribunale") or ""))
        giudice = self._clean(str(fascicolo.get("giudice") or ""))
        stato = self._clean(str(fascicolo.get("stato") or fascicolo.get("status") or ""))
        if numero:
            lines.append(f"Fascicolo di riferimento: {numero}.")
        elif titolo:
            lines.append(f"Pratica di riferimento: {titolo}.")
        if ufficio:
            lines.append(f"Ufficio giudiziario: {ufficio}.")
        if giudice:
            lines.append(f"Giudice assegnato: {giudice}.")
        if stato:
            lines.append(f"Stato del fascicolo: {stato}.")
        return self._dedupe(lines)

    def _rischi_lines(
        self,
        *,
        workflow: str,
        risk_level: str,
        answer_mode: str,
        evidence_count: int,
        evidence_sufficient: bool,
    ) -> list[str]:
        lines: list[str] = []
        if risk_level in HIGH_RISK_LEVELS:
            lines.append(
                "Rischio alto: non usare la risposta come atto o parere definitivo "
                "senza revisione professionale."
            )
        if not evidence_count:
            lines.append(
                "Non risultano evidenze agganciate: verificare il contesto sorgente "
                "prima di qualsiasi uso esterno."
            )
        if not evidence_sufficient and workflow in STRICT_WORKFLOWS:
            lines.append(
                "Per una risposta legale conclusiva servono fonti ufficiali "
                "o richiami verificati."
            )
        elif answer_mode != "grounded":
            lines.append(
                "La risposta e' operativa ma richiede controllo umano "
                "prima dell'uso esterno."
            )
        return self._dedupe(lines)

    def _confidence_lines(
        self,
        *,
        confidence: float,
        quality_label: str,
        human_review_required: bool,
    ) -> list[str]:
        pct = round(confidence * 100)
        lines = [f"Attendibilita': {quality_label} ({pct}%)."]
        if human_review_required:
            lines.append(
                "Revisione professionale richiesta prima di uso esterno, "
                "deposito o invio al cliente."
            )
        return lines

    def _missing_evidence_lines(
        self,
        *,
        missing_evidence: list[str],
        needs_review: bool,
    ) -> list[str]:
        if not missing_evidence:
            return []
        lines: list[str] = []
        # In needs_review mostriamo piu' dettagli (fino a 5 gap)
        limit = 5 if needs_review else 4
        for item in missing_evidence[:limit]:
            value = self._clean(str(item))
            if value:
                lines.append(value.rstrip(".") + ".")
        remaining = len(missing_evidence) - limit
        if remaining > 0:
            lines.append(f"Altri gap da verificare: {remaining}.")
        return lines

    def _warning_lines(
        self,
        *,
        workflow: str,
        risk_level: str,
        evidence_sufficient: bool,
        human_review_required: bool,
        fallback_triggered: bool,
    ) -> list[str]:
        lines: list[str] = []
        if risk_level in HIGH_RISK_LEVELS:
            lines.append(
                "Rischio elevato: verificare con un professionista "
                "prima di depositare o inviare al cliente."
            )
        if human_review_required and risk_level not in HIGH_RISK_LEVELS:
            lines.append(
                "Risposta da revisionare: evidenze o fonti non ancora complete."
            )
        if not evidence_sufficient and workflow in STRICT_WORKFLOWS:
            lines.append(
                "Evidenze non sufficienti per il workflow selezionato: "
                "integrare fonti ufficiali prima di chiudere il parere."
            )
        if fallback_triggered:
            lines.append(
                "Fallback attivato: verificare le fonti esterne ufficiali utilizzate."
            )
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
            actions.append(
                "Apri il fascicolo e controlla documenti, attivita', "
                "udienze e comunicazioni citate."
            )
        elif workflow == "udienza":
            actions.append(
                "Verifica scadenze, documenti preparatori e ultimo "
                "provvedimento prima dell'udienza."
            )
        elif workflow in {"telematico", "telematico_status"}:
            actions.append(
                "Controlla sempre ricevute, esiti e log del portale "
                "ufficiale prima di depositare."
            )
        elif workflow == "compliance":
            actions.append(
                "Chiudi prima i blocchi di conformita' e poi ripeti "
                "il controllo pre-deposito."
            )
        elif workflow in {"economico", "cabina", "next_action"}:
            actions.append(
                "Aggiorna i dati gestionali collegati prima di "
                "confermare l'azione al cliente."
            )
        elif workflow in STRICT_WORKFLOWS:
            actions.append(
                "Verifica le fonti ufficiali e conserva i riferimenti "
                "usati nella pratica."
            )

        if "bozza" in query or "atto" in query:
            actions.append(
                "Prima di redigere, verifica campi obbligatori, allegati e procura."
            )
        if missing_evidence or not evidence_sufficient:
            actions.append(
                "Integra le evidenze mancanti e rilancia Lex sul contesto aggiornato."
            )
        if risk_level in HIGH_RISK_LEVELS:
            actions.append(
                "Fai validare la risposta da un professionista prima di "
                "inviarla o depositarla."
            )

        return self._dedupe(actions)[:6]

    # ------------------------------------------------------------------ #
    # Utility                                                               #
    # ------------------------------------------------------------------ #

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
                rendered.append(
                    f"**{heading}**\n" + "\n".join(f"- {line}" for line in lines)
                )
        return "\n\n".join(rendered).strip()

    def _join_preview(self, values: list[str], limit: int = 4) -> str:
        clean_values = [
            self._clean(str(value))
            for value in values
            if self._clean(str(value))
        ]
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
