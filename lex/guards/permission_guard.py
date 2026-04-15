"""Guardia permessi per Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class PermissionGuard:
    def check(self, **kwargs):
        context = kwargs["context"]
        if not bool((context.get("permessi") or {}).get("can_use_lex")):
            return GuardVerdict(allowed=False, reasons=["User not allowed to use Lex"], risk_level="high")
        return GuardVerdict(allowed=True)
