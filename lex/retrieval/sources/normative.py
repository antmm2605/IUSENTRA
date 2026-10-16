"""Adapter normative per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.retrieval.normativa import search_normativa_sources

from . import row_to_evidence


class NormativeSource:
    source_name = "normative"

    def __init__(self, *, exact_reference_only: bool = False):
        self.exact_reference_only = exact_reference_only

    def search(self, queries, request, context):
        diagnostics = []
        options = {"exact_reference_only": True} if self.exact_reference_only else {}
        rows = search_normativa_sources(queries[0] if queries else request.query, diagnostics=diagnostics, **options)
        request.metadata["_normativa_diagnostics"] = diagnostics
        return [
            row_to_evidence(row, "normativa")
            for row in rows
        ]
