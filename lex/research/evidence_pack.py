"""Costruzione dell'evidence pack strutturato di Lex."""

from __future__ import annotations

from lex.contracts import EvidencePack


class EvidencePackBuilder:
    def build(self, *, queries, items, citations, official_sources, trusted_sources, freshness, metadata=None):
        return EvidencePack(
            queries=list(queries or []),
            items=list(items or []),
            citations=list(citations or []),
            official_sources=list(official_sources or []),
            trusted_sources=list(trusted_sources or []),
            freshness=dict(freshness or {}),
            metadata=dict(metadata or {}),
        )