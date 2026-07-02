from __future__ import annotations

from lex.evaluation.learning_metrics import compute_learning_signals, official_source_ratio


def _by_name(signals):
    return {signal.name: signal for signal in signals}


def test_delta_collezioni_e_flag_no_new_information():
    before = {"legal_terms": 1, "citations": 0}
    after = {"legal_terms": 4, "citations": 2, "unknown_concepts": 3}
    signals = _by_name(compute_learning_signals(before, after, cycle_index=0))
    assert signals["nuovi_legal_terms"].value == 3.0
    assert signals["nuovi_citations"].value == 2.0
    assert signals["unknown_concepts_aperti"].value == 3.0
    assert signals["no_new_information"].value == 0.0


def test_no_new_information_scatta_quando_nulla_cresce():
    counts = {"legal_terms": 5, "citations": 2, "source_readings": 1, "research_questions": 4, "unknown_concepts": 3}
    signals = _by_name(compute_learning_signals(counts, dict(counts), cycle_index=1))
    assert signals["no_new_information"].value == 1.0
    assert signals["no_new_information"].cycle_index == 1


def test_official_source_ratio_pesato():
    assert official_source_ratio([]) == 0.0
    ratio = official_source_ratio([{"tier": "tier_1"}, {"tier": "unknown"}])
    assert 0.5 < ratio < 0.6  # (1.0 + 0.08) / 2
    signals = _by_name(
        compute_learning_signals({}, {}, cycle_index=0, trust_payloads=[{"tier": "tier_1"}, {"tier": "tier_1"}])
    )
    assert signals["official_source_ratio"].value == 1.0


def test_coverage_per_area():
    signals = _by_name(compute_learning_signals({}, {}, cycle_index=0, area_readings={"privacy": 2, "civile": 1}))
    assert signals["coverage_area_privacy"].value == 2.0
    assert signals["coverage_area_civile"].value == 1.0
