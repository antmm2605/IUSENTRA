from __future__ import annotations

from lex.autonomy.improvement_proposer import propose_improvements
from lex.knowledge.knowledge_base import KnowledgeBase


def _kb(tmp_path) -> KnowledgeBase:
    return KnowledgeBase(tmp_path, iso_now=lambda: "2026-07-02T10:00:00+00:00")


def _kinds(proposals):
    return {proposal.kind for proposal in proposals}


def test_p1_pattern_citazione_non_riconosciuto(tmp_path):
    kb = _kb(tmp_path)
    kb.append(
        "source_readings",
        "r1",
        {"url": "https://www.governo.it/x", "title": "Attuazione D.P.C.M. 12/2026", "status": "ok", "citations_normalized": ["L. 241/1990"], "warnings": []},
    )
    proposals = propose_improvements(kb)
    assert "pattern_citazione" in _kinds(proposals)
    p1 = next(proposal for proposal in proposals if proposal.kind == "pattern_citazione")
    assert "D.P.C.M." in p1.title
    assert p1.requires_human_review is True
    assert p1.suggested_tests


def test_p2_dominio_ufficiale_fuori_dai_tier(tmp_path):
    kb = _kb(tmp_path)
    for index in range(2):
        kb.append(
            "trust_assessments",
            f"ta{index}",
            {"domain": "esempio-istituzionale.gov.it", "area": "civile", "tier": "unknown", "official": True, "allowed_for_learning": False},
        )
    proposals = propose_improvements(kb)
    assert "source_policy" in _kinds(proposals)


def test_p3_domande_senza_area(tmp_path):
    kb = _kb(tmp_path)
    kb.append("research_questions", "q1", {"question": "Domanda uno?", "area": ""})
    kb.append("research_questions", "q2", {"question": "Domanda due?", "area": ""})
    proposals = propose_improvements(kb)
    assert "area_keywords" in _kinds(proposals)


def test_p4_concetto_ricorrente_per_ontologia(tmp_path):
    kb = _kb(tmp_path)
    kb.append("legal_terms", "t1", {"normalized": "accesso civico", "kind": "candidato", "occurrences": 3, "area": "amministrativo"})
    proposals = propose_improvements(kb)
    ontologia = [proposal for proposal in proposals if proposal.kind == "ontologia"]
    assert ontologia
    assert "accesso civico" in ontologia[0].title
    assert ontologia[0].target_module == "lex/knowledge/legal_ontology.py"


def test_p5_tier1_bloccato_da_robots(tmp_path):
    kb = _kb(tmp_path)
    kb.append("trust_assessments", "ta1", {"domain": "normattiva.it", "area": "civile", "tier": "tier_1", "official": True, "allowed_for_learning": True})
    kb.append("source_readings", "r1", {"url": "https://www.normattiva.it/x", "status": "robots_blocked", "citations_normalized": [], "warnings": []})
    proposals = propose_improvements(kb)
    assert "connettore_dedicato" in _kinds(proposals)


def test_memoria_vuota_nessuna_proposta(tmp_path):
    assert propose_improvements(_kb(tmp_path)) == []


def test_dedup_e_solo_lettura_della_memoria(tmp_path):
    kb = _kb(tmp_path)
    kb.append("legal_terms", "t1", {"normalized": "accesso civico", "kind": "candidato", "occurrences": 4, "area": "amministrativo"})
    first = propose_improvements(kb)
    second = propose_improvements(kb)
    assert [proposal.stable_id() for proposal in first] == [proposal.stable_id() for proposal in second]
    # Il proposer non scrive nulla: la memoria resta identica.
    assert kb.snapshot_counts()["improvement_proposals"] == 0
