"""Apprendimento linguistico-giuridico di Lex (deterministico, fail-closed).

Bounded context "learning": analizza testi legali e produce osservazioni
strutturate (citazioni, termini, profilo linguistico) senza LLM e senza rete.
Riusa l'estrattore di produzione `pct.legal_reference_extractor` e la policy
fonti `lex.research.source_policy`; non duplica nessun motore esistente.
"""

from lex.learning.citation_extractor import extract_citations
from lex.learning.legal_language_analyzer import analyze_language, extract_term_observations
from lex.learning.models import (
    LearningSignal,
    LegalCitation,
    LegalLanguageProfile,
    LegalSourceSample,
    LegalTermObservation,
    SourceReadingResult,
    stable_id_from,
)

__all__ = [
    "LearningSignal",
    "LegalCitation",
    "LegalLanguageProfile",
    "LegalSourceSample",
    "LegalTermObservation",
    "SourceReadingResult",
    "analyze_language",
    "extract_citations",
    "extract_term_observations",
    "stable_id_from",
]
