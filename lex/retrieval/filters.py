"""Filtri di retrieval per il modulo Lex."""

from __future__ import annotations


class RetrievalFilters:
    def apply(self, items, request, context, workflow: str):
        return [item for item in list(items or []) if item]
