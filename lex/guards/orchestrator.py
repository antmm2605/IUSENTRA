from __future__ import annotations

from lex.contracts import GuardVerdict

from .citation_guard import CitationGuard
from .evidence_relevance_guard import EvidenceRelevanceGuard
from .hallucination_guard import HallucinationGuard
from .italian_language_guard import ItalianLanguageGuard
from .legal_answer_quality_guard import LegalAnswerQualityGuard
from .legal_reference_guard import LegalReferenceGuard
from .output_schema_guard import OutputSchemaGuard
from .permission_guard import PermissionGuard
from .privacy_guard import PrivacyGuard
from .risk_guard import RiskGuard
from .telematico_guard import TelematicoGuard
from .tenant_guard import TenantGuard


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class GuardOrchestrator:
    def __init__(self) -> None:
        self.pre_guards = [TenantGuard(), PermissionGuard(), PrivacyGuard(), RiskGuard()]
        self.post_guards = [
            ItalianLanguageGuard(),
            EvidenceRelevanceGuard(),
            CitationGuard(),
            LegalReferenceGuard(),
            HallucinationGuard(),
            LegalAnswerQualityGuard(),
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
        rewritten_draft: str | None = None

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
            if _RISK_ORDER.get(str(verdict.risk_level or "low"), 0) > _RISK_ORDER.get(risk_level, 0):
                risk_level = str(verdict.risk_level or risk_level)
            if verdict.rewritten_draft is not None:
                rewritten_draft = verdict.rewritten_draft
            if not verdict.allowed:
                return GuardVerdict(
                    allowed=False,
                    warnings=warnings,
                    reasons=reasons,
                    risk_level=risk_level,
                    rewritten_draft=rewritten_draft,
                )

        return GuardVerdict(
            allowed=True,
            warnings=warnings,
            reasons=reasons,
            risk_level=risk_level,
            rewritten_draft=rewritten_draft,
        )
