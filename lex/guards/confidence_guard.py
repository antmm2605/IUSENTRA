"""Guardia placeholder sulla confidence Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class ConfidenceGuard:
    def check(self, **kwargs):
        return GuardVerdict(allowed=True)
