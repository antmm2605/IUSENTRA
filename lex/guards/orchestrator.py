"""Orchestrazione dei guard rail del bounded context Lex."""

from __future__ import annotations

from lex.contracts import GuardVerdict

from .citation_guard import CitationGuard
from .hallucination_guard import HallucinationGuard
from .output_schema_guard import OutputSchemaGuard
from .permission_guard import PermissionGuard
from .privacy_guard import PrivacyGuard
from .risk_guard import RiskGuard
from .telematico_guard import TelematicoGuard
from .tenant_guard import TenantGuard


class GuardOrchestrator:
    def __init__(self) -> None:
        self.pre_guards = [TenantGuard(), PermissionGuard(), PrivacyGuard(), RiskGuard()]
        self.post_guards = [
            CitationGuard(),
            HallucinationGuard(),
            TelematicoGuard(),
            OutputSchemaGuard(),
        ]

    def run_pre(self, request, context, workflow):
        warnings: list[str] = []
        reasons: list[str] = []

        for guard in self.pre_guards:
            verdict = guard.check(request=request, context=context, workflow=workflow)
            warnings.extend(verdict.warnings)
            reasons.extend(verdict.reasons)
            if not verdict.allowed:
                return verdict

        return GuardVerdict(allowed=True, warnings=warnings, reasons=reasons)

    def run_post(self, request, context, workflow, evidence, draft):
        warnings: list[str] = []
        reasons: list[str] = []
        risk_level = "low"

        for guard in self.post_guards:
            verdict = guard.check(
                request=request,
                context=context,
                workflow=workflow,
                evidence=evidence,
                draft=draft,
            )
            warnings.extend(verdict.warnings)
            reasons.extend(verdict.reasons)
            risk_level = verdict.risk_level or risk_level
            if not verdict.allowed:
                return verdict

        return GuardVerdict(
            allowed=True,
            warnings=warnings,
            reasons=reasons,
            risk_level=risk_level,
        )
