"""Motore giornaliero Legal Intelligence per fonti ufficiali."""

from .engine import LegalIntelligenceDailyEngine
from .sources import DEFAULT_LEGAL_SOURCES, LegalSource

__all__ = ["DEFAULT_LEGAL_SOURCES", "LegalIntelligenceDailyEngine", "LegalSource"]
