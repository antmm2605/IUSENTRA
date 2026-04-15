"""Test locali del service Lex."""

from __future__ import annotations

from lex.guards.grounding import GroundingGuard


def test_grounding_guard_marks_low_confidence_without_sources():
    result = GroundingGuard().evaluate(sources=[])

    assert result.grounded is False
    assert result.confidence == 0.1
