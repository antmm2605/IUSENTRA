"""Guardia placeholder sul perimetro strumenti Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class ToolScopeGuard:
    def check(self, **kwargs):
        return GuardVerdict(allowed=True)
