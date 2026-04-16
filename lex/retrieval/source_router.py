"""Scelta delle fonti di retrieval per workflow Lex."""

from __future__ import annotations

from .sources.agenda import AgendaSource
from .sources.applicazioni import ApplicazioniSource
from .sources.compliance import ComplianceSource
from .sources.documenti import DocumentiSource
from .sources.fascicoli import FascicoliSource
from .sources.giurisprudenza import GiurisprudenzaSource
from .sources.legal_intelligence import LegalIntelligenceSource
from .sources.normative import NormativeSource
from .sources.official_web import OfficialWebSource
from .sources.preventivi import PreventiviSource
from .sources.scadenziario import ScadenziarioSource
from .sources.telematico import TelematicoSource
from .sources.template_atti import TemplateAttiSource


class SourceRouter:
    def resolve(self, request, context, workflow: str):
        sources = [GiurisprudenzaSource(), LegalIntelligenceSource(), NormativeSource()]

        if request.fascicolo_id:
            sources.insert(0, FascicoliSource())
            sources.insert(1, DocumentiSource())

        if workflow == "telematico":
            sources.append(TelematicoSource())
            sources.append(ComplianceSource())

        if workflow == "udienza":
            sources.append(AgendaSource())
            sources.append(ScadenziarioSource())

        if workflow == "atto":
            sources.append(TemplateAttiSource())
            sources.append(ComplianceSource())

        if workflow == "chat":
            sources.append(PreventiviSource())
            sources.append(ApplicazioniSource())

        if OfficialWebSource.should_include(request, workflow):
            sources.append(OfficialWebSource())

        return sources
