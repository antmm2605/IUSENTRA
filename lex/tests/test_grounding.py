from __future__ import annotations

from lex.guards.grounding import GroundingGuard


def test_grounding_guard_marks_low_confidence_without_sources():
    result = GroundingGuard().evaluate(sources=[])

    assert result.grounded is False
    assert result.enough_sources is False
    assert result.confidence == 0.1
    assert result.warnings == ["Nessuna fonte disponibile"]


def test_grounding_guard_marks_limited_confidence_with_one_source():
    result = GroundingGuard().evaluate(
        sources=[
            {
                "title": "Documento 1",
                "excerpt": "Testo rilevante",
            }
        ]
    )

    assert result.grounded is True
    assert result.enough_sources is False
    assert result.confidence == 0.45
    assert result.warnings == ["Base documentale limitata"]


def test_grounding_guard_marks_high_confidence_with_two_sources():
    result = GroundingGuard().evaluate(
        sources=[
            {"title": "Documento 1", "excerpt": "Testo rilevante"},
            {"title": "Documento 2", "excerpt": "Altro testo rilevante"},
        ]
    )

    assert result.grounded is True
    assert result.enough_sources is True
    assert result.confidence == 0.85
    assert result.warnings == []
