"""Guardia tenant per Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict


class TenantGuard:
    def check(self, **kwargs):
        request = kwargs["request"]
        if not str(request.tenant_id or "").strip():
            return GuardVerdict(allowed=False, reasons=["Missing tenant_id"], risk_level="high")
        return GuardVerdict(allowed=True)
