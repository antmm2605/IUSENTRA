"""Rilevazione minima di prompt injection per Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class PromptInjectionGuard:
    def check(self, **kwargs):
        query = str(kwargs["request"].query or "").lower()
        suspicious = ("ignore previous", "system prompt", "developer instructions")
        if any(token in query for token in suspicious):
            return GuardVerdict(
                allowed=True,
                warnings=["Tentativo di manipolazione prompt rilevato; applicata modalita prudente"],
                risk_level="high",
            )
        return GuardVerdict(allowed=True)
