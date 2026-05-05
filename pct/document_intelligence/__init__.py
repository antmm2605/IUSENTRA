"""Documenti AI collegati al fascicolo.

Il dominio e' nativo IUSENTRA: non dipende da Mike e non espone logica
filesystem ai tool Lex o alla UI.
"""

from .models import (
    DOCUMENT_AI_SOURCES,
    DOCUMENT_AI_STATUSES,
    DocumentAICitation,
    DocumentAIPageText,
    DocumentAIRecord,
    DocumentAISearchResult,
    DocumentAIText,
    DocumentAIVersion,
)
from .repository import DocumentAIRepository
from .service import DocumentAIService

__all__ = [
    "DOCUMENT_AI_SOURCES",
    "DOCUMENT_AI_STATUSES",
    "DocumentAICitation",
    "DocumentAIPageText",
    "DocumentAIRecord",
    "DocumentAISearchResult",
    "DocumentAIService",
    "DocumentAIText",
    "DocumentAIVersion",
    "DocumentAIRepository",
]
