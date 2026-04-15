"""Guardia anti allucinazione per Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class HallucinationGuard:
    def check(self, **kwargs):
        draft = kwargs.get("draft")
        if not str(getattr(draft, "text", "") or "").strip():
            return GuardVerdict(allowed=False, reasons=["Empty provider draft"], risk_level="high")
        return GuardVerdict(allowed=True)
