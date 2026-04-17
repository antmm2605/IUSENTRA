"""Adapter documenti per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.retrieval.documenti import search_document_sources


class DocumentiSource:
    source_name = "documenti"

    def search(self, queries, request, context):
        # search_document_sources restituisce già EvidenceItem — nessuna conversione necessaria
        return search_document_sources(
            str(request.fascicolo_id or ""),
            queries[0] if queries else request.query,
            context,
        )
