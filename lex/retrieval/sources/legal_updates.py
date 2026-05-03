"""Adapter Update Intelligence SQL per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.retrieval.legal_updates import search_legal_update_sources

from . import row_to_evidence


class LegalUpdatesSource:
    source_name = "legal_updates"

    def search(self, queries, request, context):
        query = queries[0] if queries else request.query
        return [
            row_to_evidence(row, "legal_updates")
            for row in search_legal_update_sources(query, request=request, limit=10)
        ]
