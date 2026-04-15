"""Guardia citazioni per Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class CitationGuard:
    def check(self, **kwargs):
        evidence = kwargs.get("evidence") or {}
        items = list(evidence.get("items") or [])
        if not items:
            return GuardVerdict(
                allowed=True,
                warnings=["Nessuna evidenza trovata: risposta da limitare o rendere prudente"],
                risk_level="medium",
            )
        return GuardVerdict(allowed=True)
