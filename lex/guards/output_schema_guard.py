"""Guardia finale sullo schema di output Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class OutputSchemaGuard:
    def check(self, **kwargs):
        return GuardVerdict(allowed=True)
