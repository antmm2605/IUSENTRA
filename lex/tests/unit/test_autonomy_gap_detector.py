from __future__ import annotations

from lex.autonomy.gap_detector import detect_gaps
from lex.knowledge.concept_graph import ConceptGraph
from lex.knowledge.knowledge_base import KnowledgeBase


def _kb(tmp_path) -> KnowledgeBase:
    return KnowledgeBase(tmp_path, iso_now=lambda: "2026-07-02T10:00:00+00:00")


def _kinds(gaps):
    return {(gap.kind, gap.concept) for gap in gaps}


def test_r1_norma_citata_ma_non_letta(tmp_path):
    kb = _kb(tmp_path)
    kb.append("citations", "c1", {"normalized_text": "art. 2043 c.c.", "reference_type": "article", "confidence": 0.9, "area": "civile"})
    gaps = detect_gaps(kb, ConceptGraph())
    assert ("norma_non_letta", "art. 2043 c.c.") in _kinds(gaps)
    # Una volta letta la norma, la lacuna sparisce.
    kb.append("source_readings", "r1", {"url": "https://x", "status": "ok", "area": "civile", "citations_normalized": ["art. 2043 c.c."]})
    gaps_after = detect_gaps(kb, ConceptGraph())
    assert ("norma_non_letta", "art. 2043 c.c.") not in _kinds(gaps_after)


def test_r1_ignora_confidenza_bassa(tmp_path):
    kb = _kb(tmp_path)
    kb.append("citations", "c1", {"normalized_text": "2020", "reference_type": "year", "confidence": 0.62})
    kb.append("citations", "c2", {"normalized_text": "art. 1 c.c.", "reference_type": "article", "confidence": 0.5})
    assert not [gap for gap in detect_gaps(kb, ConceptGraph()) if gap.kind == "norma_non_letta"]


def test_r2_termine_candidato_ricorrente(tmp_path):
    kb = _kb(tmp_path)
    kb.append("legal_terms", "t1", {"normalized": "accesso civico", "kind": "candidato", "occurrences": 3, "area": "amministrativo", "confidence": 0.7})
    kb.append("legal_terms", "t2", {"normalized": "danno raro", "kind": "candidato", "occurrences": 1, "area": "civile", "confidence": 0.6})
    gaps = _kinds(detect_gaps(kb, ConceptGraph()))
    assert ("termine_sconosciuto", "accesso civico") in gaps
    assert ("termine_sconosciuto", "danno raro") not in gaps  # sotto soglia occorrenze


def test_r3_area_scoperta(tmp_path):
    kb = _kb(tmp_path)
    kb.append("citations", "c1", {"normalized_text": "art. 6 Regolamento (UE) 2016/679", "reference_type": "article", "confidence": 0.9, "area": "privacy"})
    gaps = _kinds(detect_gaps(kb, ConceptGraph(), min_sources_per_area=2))
    assert ("area_scoperta", "copertura area privacy") in gaps
    kb.append("source_readings", "r1", {"url": "https://a", "status": "ok", "area": "privacy", "citations_normalized": []})
    kb.append("source_readings", "r2", {"url": "https://b", "status": "ok", "area": "privacy", "citations_normalized": []})
    gaps_after = _kinds(detect_gaps(kb, ConceptGraph(), min_sources_per_area=2))
    assert ("area_scoperta", "copertura area privacy") not in gaps_after


def test_r4_fonti_deboli(tmp_path):
    kb = _kb(tmp_path)
    for index in range(3):
        kb.append("trust_assessments", f"ta{index}", {"area": "civile", "tier": "unknown", "domain": f"blog{index}.example.com"})
    gaps = _kinds(detect_gaps(kb, ConceptGraph()))
    assert ("fonte_debole", "affidabilità fonti area civile") in gaps


def test_r5_concetto_isolato(tmp_path):
    graph = ConceptGraph()
    graph.ensure_node("concetto", "danno ingiusto", area="civile", seen_at="t1")
    graph.ensure_node("concetto", "danno ingiusto", area="civile", seen_at="t2")
    gaps = _kinds(detect_gaps(_kb(tmp_path), graph))
    assert ("concetto_isolato", "danno ingiusto") in gaps


def test_ordinamento_stabile_per_priorita(tmp_path):
    kb = _kb(tmp_path)
    kb.append("citations", "c1", {"normalized_text": "art. 2043 c.c.", "reference_type": "article", "confidence": 0.9, "area": "civile"})
    graph = ConceptGraph()
    graph.ensure_node("concetto", "danno ingiusto", area="civile", seen_at="t1")
    graph.ensure_node("concetto", "danno ingiusto", area="civile", seen_at="t2")
    gaps = detect_gaps(kb, graph)
    priorities = [gap.priority for gap in gaps]
    assert priorities == sorted(priorities, reverse=True)
    assert gaps == detect_gaps(kb, graph)  # deterministico
