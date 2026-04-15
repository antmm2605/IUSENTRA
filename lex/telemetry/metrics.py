"""Metriche leggere del modulo Lex."""

from __future__ import annotations


def build_metrics_payload(*, sources_ready: int = 0) -> dict[str, int]:
    return {"sources_ready": int(sources_ready or 0)}
