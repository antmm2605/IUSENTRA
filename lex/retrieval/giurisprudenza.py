"""Retrieval giurisprudenziale per Lex."""

from __future__ import annotations

from lex.schemas import LexSource
from web.helpers import get_giurisprudenza


def search_giurisprudenza_sources(message: str) -> list[LexSource]:
    gestore = get_giurisprudenza()
    rows = []
    if hasattr(gestore, "resolve_lex_giurisprudenza_route"):
        try:
            rows = list((gestore.resolve_lex_giurisprudenza_route(message) or {}).get("corpus_rows") or [])
        except Exception:
            rows = []
    if not rows:
        rows = list(gestore.cerca_corpus_professionale(q=message, limit=4) or [])
    results: list[LexSource] = []
    for row in rows[:4]:
        results.append(
            LexSource(
                source_type="giurisprudenza",
                source_id=str(row.get("id") or row.get("sentenza_id") or ""),
                title=str(row.get("titolo") or row.get("citation") or "Sentenza"),
                excerpt=str(row.get("text") or row.get("principio_sintetico") or row.get("massima_ufficiale") or "").strip(),
                score=float(row.get("score") or 0.85),
                metadata={
                    "verified_reference": bool(row.get("verified_reference")),
                    "official_url": row.get("official_url") or row.get("url_pagina_ufficiale") or "",
                },
            )
        )
    return results
