"""Adapter giurisprudenza per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.retrieval.giurisprudenza import search_giurisprudenza_sources

from . import row_to_evidence


class GiurisprudenzaSource:
    source_name = "giurisprudenza"

    def search(self, queries, request, context):
        return [
            row_to_evidence(row, "giurisprudenza")
            for row in search_giurisprudenza_sources(queries[0] if queries else request.query)
        ]
