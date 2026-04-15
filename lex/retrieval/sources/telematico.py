"""Adapter telematico per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.retrieval.pst import search_pst_sources

from . import row_to_evidence


class TelematicoSource:
    source_name = "telematico"

    def search(self, queries, request, context):
        return [
            row_to_evidence(row, "telematico")
            for row in search_pst_sources(queries[0] if queries else request.query)
        ]
