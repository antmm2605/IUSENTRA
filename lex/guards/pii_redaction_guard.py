"""Guardia placeholder per redazione PII in Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class PIIRedactionGuard:
    def check(self, **kwargs):
        return GuardVerdict(allowed=True)
