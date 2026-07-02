"""Trasforma le lacune (UnknownConcept) in domande di ricerca deterministiche.

Mappa 1:N per tipo di lacuna, dedup per stable_id e tetto per ciclo. Per le
aree scoperte riusa il generatore deterministico di produzione
`pct.legal_context_questions.generate_context_questions` (modulo regex puro,
sicuro da importare). Le domande sono costruite SOLO da campi strutturati
(norma normalizzata, termine, area): niente testo libero dei campioni, quindi
niente PII per costruzione.
"""

from __future__ import annotations

from lex.autonomy.models import ResearchQuestion, UnknownConcept


def plan_research(
    concepts: list[UnknownConcept],
    *,
    max_questions: int = 5,
) -> list[ResearchQuestion]:
    """Genera domande dalle lacune, ordinate per priorità, dedup, con tetto."""

    questions: list[ResearchQuestion] = []
    for concept in sorted(concepts, key=lambda item: (-item.priority, item.stable_id())):
        questions.extend(_questions_for(concept))
    deduped: dict[str, ResearchQuestion] = {}
    for question in questions:
        if question.question:
            deduped.setdefault(question.stable_id(), question)
    ordered = sorted(deduped.values(), key=lambda item: (-item.priority, item.stable_id()))
    return ordered[: max(1, int(max_questions))]


def _questions_for(concept: UnknownConcept) -> list[ResearchQuestion]:
    origin = concept.stable_id()
    if concept.kind == "norma_non_letta":
        return [
            ResearchQuestion(
                question=f"Cosa stabilisce {concept.concept}?",
                area=concept.area,
                kind=concept.kind,
                priority=concept.priority,
                target_citation=concept.concept,
                required_source_types=["normativa"],
                reason=concept.reason,
                origin_concept_id=origin,
            )
        ]
    if concept.kind == "termine_sconosciuto":
        return [
            ResearchQuestion(
                question=f"Qual è la definizione giuridica di '{concept.concept}' nel diritto {concept.area or 'italiano'}?",
                area=concept.area,
                kind=concept.kind,
                priority=concept.priority,
                target_term=concept.concept,
                required_source_types=["normativa", "giurisprudenza"],
                reason=concept.reason,
                origin_concept_id=origin,
            )
        ]
    if concept.kind == "area_scoperta":
        return _area_questions(concept, origin)
    if concept.kind in {"fonte_debole", "concetto_isolato"}:
        subject = concept.concept if concept.kind == "concetto_isolato" else f"la materia {concept.area}"
        return [
            ResearchQuestion(
                question=f"Quali fonti ufficiali primarie trattano {subject}?",
                area=concept.area,
                kind=concept.kind,
                priority=concept.priority,
                target_term=concept.concept if concept.kind == "concetto_isolato" else "",
                required_source_types=["normativa"],
                reason=concept.reason,
                origin_concept_id=origin,
            )
        ]
    return []


def _area_questions(concept: UnknownConcept, origin: str) -> list[ResearchQuestion]:
    # Riuso del generatore deterministico di produzione (regex puro).
    from pct.legal_context_questions import generate_context_questions

    rows = generate_context_questions(title=f"Area {concept.area}", matter=concept.area, limit=3)
    questions = [
        ResearchQuestion(
            question=str(row.get("question") or ""),
            area=concept.area,
            kind=concept.kind,
            priority=concept.priority,
            required_source_types=["normativa"],
            reason=str(row.get("reason") or concept.reason),
            origin_concept_id=origin,
        )
        for row in rows
        if str(row.get("question") or "").strip()
    ]
    # La domanda di copertura resta comunque, anche se il generatore tace.
    questions.append(
        ResearchQuestion(
            question=f"Quali sono le fonti normative primarie dell'area {concept.area}?",
            area=concept.area,
            kind=concept.kind,
            priority=concept.priority,
            required_source_types=["normativa"],
            reason=concept.reason,
            origin_concept_id=origin,
        )
    )
    return questions


__all__ = ["plan_research"]
