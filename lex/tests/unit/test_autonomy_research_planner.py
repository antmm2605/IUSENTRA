from __future__ import annotations

from lex.autonomy.models import UnknownConcept
from lex.autonomy.research_planner import plan_research


def test_norma_non_letta_diventa_domanda_normativa():
    concept = UnknownConcept(concept="art. 2043 c.c.", kind="norma_non_letta", area="civile", priority=0.9)
    questions = plan_research([concept])
    assert questions[0].question == "Cosa stabilisce art. 2043 c.c.?"
    assert questions[0].target_citation == "art. 2043 c.c."
    assert questions[0].required_source_types == ["normativa"]
    assert questions[0].origin_concept_id == concept.stable_id()


def test_termine_sconosciuto_diventa_domanda_di_definizione():
    concept = UnknownConcept(concept="accesso civico", kind="termine_sconosciuto", area="amministrativo", priority=0.7)
    questions = plan_research([concept])
    assert "accesso civico" in questions[0].question
    assert questions[0].target_term == "accesso civico"


def test_area_scoperta_delega_al_generatore_di_produzione():
    concept = UnknownConcept(concept="copertura area civile", kind="area_scoperta", area="civile", priority=0.7)
    questions = plan_research([concept], max_questions=5)
    assert questions
    assert all(question.area == "civile" for question in questions)
    assert any("fonti normative primarie" in question.question for question in questions)


def test_priorita_dedup_e_tetto():
    concepts = [
        UnknownConcept(concept="art. 2043 c.c.", kind="norma_non_letta", area="civile", priority=0.9),
        UnknownConcept(concept="art. 2043 c.c.", kind="norma_non_letta", area="civile", priority=0.9),
        UnknownConcept(concept="copertura area privacy", kind="area_scoperta", area="privacy", priority=0.7),
        UnknownConcept(concept="termine x", kind="termine_sconosciuto", area="civile", priority=0.6),
    ]
    questions = plan_research(concepts, max_questions=3)
    assert len(questions) == 3
    texts = [question.question for question in questions]
    assert len(set(texts)) == 3  # niente duplicati
    assert questions[0].priority >= questions[-1].priority
