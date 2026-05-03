from __future__ import annotations

from .sources.agenda import AgendaSource
from .sources.applicazioni import ApplicazioniSource
from .sources.compliance import ComplianceSource
from .sources.documenti import DocumentiSource
from .sources.fascicoli import FascicoliSource
from .sources.giurisprudenza import GiurisprudenzaSource
from .sources.legal_intelligence import LegalIntelligenceSource
from .sources.legal_updates import LegalUpdatesSource
from .sources.normative import NormativeSource
from .sources.official_web import OfficialWebSource
from .sources.operational import OperationalSource
from .sources.preventivi import PreventiviSource
from .sources.scadenziario import ScadenziarioSource
from .sources.telematico import TelematicoSource
from .sources.template_atti import TemplateAttiSource

_LEGAL_RESEARCH_HINTS = (
    "norma",
    "normativa",
    "legge",
    "decreto",
    "articolo",
    "art.",
    "gazzetta",
    "normattiva",
    "aggiornamenti legali",
    "aggiornamento legale",
    "sentenza",
    "giurisprudenza",
    "cassazione",
    "tariffario",
    "d.m. 55",
    "dm 55",
    "d.m. 150",
    "dm 150",
)


def _clean_spaces(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _should_include_legal_sources(request, workflow: str) -> bool:
    if workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti"}:
        return True
    if workflow not in {"economico", "cabina", "next_action"}:
        return True

    if bool(getattr(request, "require_official_sources", False)):
        return True

    metadata = dict(getattr(request, "metadata", {}) or {})
    profile = dict(metadata.get("request_profile") or {})
    if _clean_spaces(profile.get("source_mode")).lower() == "strict":
        return True

    haystack = _clean_spaces(getattr(request, "query", "") or "").lower()
    return any(token in haystack for token in _LEGAL_RESEARCH_HINTS)


class SourceRouter:
    def resolve(self, request, context, workflow: str):
        local_sources = []
        legal_sources = []
        workflow_sources = []

        if request.fascicolo_id:
            local_sources.extend([FascicoliSource(), DocumentiSource()])

        if _should_include_legal_sources(request, workflow):
            legal_sources.extend([LegalUpdatesSource(), LegalIntelligenceSource(), NormativeSource(), GiurisprudenzaSource()])

        if workflow in {"telematico", "telematico_status"}:
            workflow_sources.extend([TelematicoSource(), ComplianceSource()])
        elif workflow == "udienza":
            workflow_sources.extend([AgendaSource(), ScadenziarioSource()])
        elif workflow == "atto":
            workflow_sources.extend([TemplateAttiSource(), ComplianceSource()])
        elif workflow == "economico":
            workflow_sources.extend([PreventiviSource(), ApplicazioniSource()])
        elif workflow == "cabina":
            workflow_sources.extend([OperationalSource(), AgendaSource(), ScadenziarioSource(), ApplicazioniSource()])
        elif workflow == "compliance":
            workflow_sources.extend([ComplianceSource(), TemplateAttiSource()])
        elif workflow == "next_action":
            workflow_sources.extend([OperationalSource(), AgendaSource(), ScadenziarioSource(), ApplicazioniSource()])
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
