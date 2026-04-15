"""Calcolo confidence di dominio per Lex."""

from __future__ import annotations


def compute_confidence(evidence_count: int) -> float:
    if evidence_count >= 5:
        return 0.9
    if evidence_count >= 2:
        return 0.7
    return 0.4
