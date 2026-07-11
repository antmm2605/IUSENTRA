"""Collettori deterministici del piano del giorno.

Ogni collettore legge SOLO dati già materializzati (nessun OCR, nessuna
estrazione, nessun LLM), degrada a copertura ``unavailable`` in caso di
errore e non interrompe mai la costruzione del piano.
"""

from .base import Budget, CollectorContext, CollectorResult
from .calendar_collector import AgendaCollector, ScadenzarioCollector
from .case_collector import CasePresidioCollector
from .economic_collector import EconomicSignalCollector
from .health_collector import build_coverage_report
from .pec_collector import PecSignalCollector

__all__ = [
    "AgendaCollector",
    "Budget",
    "CasePresidioCollector",
    "CollectorContext",
    "CollectorResult",
    "EconomicSignalCollector",
    "PecSignalCollector",
    "ScadenzarioCollector",
    "build_coverage_report",
]
