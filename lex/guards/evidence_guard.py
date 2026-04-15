"""Guardia placeholder sulle evidenze Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class EvidenceGuard:
    def check(self, **kwargs):
        return GuardVerdict(allowed=True)
