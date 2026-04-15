"""Ranking delle evidenze Lex."""

from __future__ import annotations


def rank_evidence(items, request, workflow: str):
    return sorted(list(items or []), key=lambda item: float(item.score), reverse=True)
