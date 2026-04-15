"""Adapter preventivi per il retrieval applicativo Lex."""

from __future__ import annotations


class PreventiviSource:
    source_name = "preventivi"

    def search(self, queries, request, context):
        return []
