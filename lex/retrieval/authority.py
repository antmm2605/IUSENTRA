"""Ranking di autorita' delle fonti Lex."""

from __future__ import annotations


def authority_rank(source_type: str) -> int:
    ranking = {
        "normativa": 100,
        "compliance": 95,
        "telematico": 90,
        "giurisprudenza": 85,
        "documento": 70,
        "fascicolo": 65,
    }
    return ranking.get(source_type, 50)
