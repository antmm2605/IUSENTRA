"""Classificazione rischio di dominio per Lex."""

from __future__ import annotations


def classify_risk(query: str) -> str:
    q = str(query or "").lower()
    if any(token in q for token in ("deposito", "termine", "firma", "ricorso")):
        return "high"
    return "low"
