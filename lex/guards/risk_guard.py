"""Classificazione prudenziale del rischio per Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class RiskGuard:
    def check(self, **kwargs):
        query = str(kwargs["request"].query or "").lower()
        if any(token in query for token in ("deposita", "firma", "termine", "ricorso")):
            return GuardVerdict(
                allowed=True,
                warnings=["Richiesta operativa sensibile: usare risposta prudente e verificata"],
                risk_level="high",
            )
        return GuardVerdict(allowed=True, risk_level="low")
