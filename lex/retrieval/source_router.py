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
        local_sources = []
        legal_sources = []
        workflow_sources = []

        if request.fascicolo_id:
            local_sources.extend([FascicoliSource(), DocumentiSource()])

        legal_sources.extend([LegalIntelligenceSource(), NormativeSource(), GiurisprudenzaSource()])

        if workflow in {"telematico", "telematico_status"}:
            workflow_sources.extend([TelematicoSource(), ComplianceSource()])
        elif workflow == "udienza":
            workflow_sources.extend([AgendaSource(), ScadenziarioSource()])
        elif workflow == "atto":
            workflow_sources.extend([TemplateAttiSource(), ComplianceSource()])
        elif workflow == "economico":
            workflow_sources.extend([PreventiviSource(), ApplicazioniSource()])
        elif workflow == "cabina":
            workflow_sources.extend([AgendaSource(), ScadenziarioSource(), ApplicazioniSource()])
        elif workflow == "compliance":
            workflow_sources.extend([ComplianceSource(), TemplateAttiSource()])
        elif workflow in {"documento", "fascicolo"} and not request.fascicolo_id:
            workflow_sources.extend([DocumentiSource()])

        ordered = [*local_sources, *workflow_sources, *legal_sources]

        if OfficialWebSource.should_include(request, workflow):
            ordered.append(OfficialWebSource())

        seen = set()
        unique = []
        for source in ordered:
            key = source.__class__.__name__
            if key in seen:
                continue
            unique.append(source)
            seen.add(key)
        return unique