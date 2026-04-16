"""Servizio centrale di insight per Lex."""

from __future__ import annotations

from .compliance import ComplianceInsights
from .economic import EconomicInsights
from .hearings import HearingInsights
from .operational import OperationalInsights


class LexInsightsService:
    def __init__(self) -> None:
        self.operational = OperationalInsights()
        self.economic = EconomicInsights()
        self.compliance = ComplianceInsights()
        self.hearings = HearingInsights()

    def build(self, *, request, workflow: str, module_packs, evidence_pack: dict, economic_facts):
        return [
            *self.operational.build(request=request, workflow=workflow, module_packs=module_packs),
            *self.economic.build(request=request, workflow=workflow, economic_facts=economic_facts),
            *self.compliance.build(request=request, workflow=workflow, module_packs=module_packs, evidence_pack=evidence_pack),
            *self.hearings.build(request=request, workflow=workflow, module_packs=module_packs),
        ]