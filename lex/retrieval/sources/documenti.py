"""Adapter documenti per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.retrieval.documenti import search_document_sources

from . import row_to_evidence


class DocumentiSource:
    source_name = "documenti"

    def search(self, queries, request, context):
        return [
            row_to_evidence(row, "documento")
            for row in search_document_sources(str(request.fascicolo_id or ""), queries[0] if queries else request.query, context)
        ]
