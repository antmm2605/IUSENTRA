"""Adapter normative per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.retrieval.normativa import search_normativa_sources

from . import row_to_evidence


class NormativeSource:
    source_name = "normative"

    def search(self, queries, request, context):
        return [
            row_to_evidence(row, "normativa")
            for row in search_normativa_sources(queries[0] if queries else request.query)
        ]
