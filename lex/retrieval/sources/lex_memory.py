"""Adapter della memoria di apprendimento autonomo per il retrieval Lex."""

from __future__ import annotations

from lex.retrieval.learning_memory import search_learning_memory

from . import row_to_evidence


class LexMemorySource:
    """Ciò che Lex ha imparato da fonti ufficiali (estratti con ancora e trust)."""

    source_name = "lex_memory"

    def __init__(self, memory_dir=None) -> None:
        self._memory_dir = memory_dir

    def search(self, queries, request, context):
        query = queries[0] if queries else getattr(request, "query", "")
        return [
            row_to_evidence(row, "lex_memory")
            for row in search_learning_memory(query, memory_dir=self._memory_dir, limit=6)
        ]
