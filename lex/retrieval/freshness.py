"""Utility di freshness per le fonti Lex."""

from __future__ import annotations


def compute_freshness(metadata: dict) -> float:
    return float((metadata or {}).get("freshness", 0.0))
