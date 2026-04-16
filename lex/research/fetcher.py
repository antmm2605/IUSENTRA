"""Fetcher interno del pacchetto di ricerca Lex."""

from __future__ import annotations


class ResearchFetcher:
    def collect(self, items):
        return list(items or [])