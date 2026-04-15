"""Adapter fascicoli per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.retrieval.fascicoli import search_fascicolo_sources

from . import row_to_evidence


class FascicoliSource:
    source_name = "fascicoli"

    def search(self, queries, request, context):
        if not request.fascicolo_id:
            return []
        return [
            row_to_evidence(row, "fascicolo")
            for row in search_fascicolo_sources(str(request.fascicolo_id or ""), queries[0] if queries else request.query, context)
        ]
