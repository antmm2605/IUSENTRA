"""Guardia prudenziale specifica per i workflow telematici."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class TelematicoGuard:
    def check(self, **kwargs):
        workflow = kwargs.get("workflow")
        if workflow == "telematico":
            return GuardVerdict(
                allowed=True,
                warnings=["Verificare sempre canale, esito e catalogo ufficiale prima di assumere operativita"],
                risk_level="high",
            )
        return GuardVerdict(allowed=True)
