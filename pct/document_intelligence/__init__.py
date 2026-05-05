"""Documenti AI collegati al fascicolo.

Il dominio e' nativo IUSENTRA: non dipende da Mike e non espone logica
filesystem ai tool Lex o alla UI.
"""

from .extraction import DocumentAITextExtractionResult
from .models import (
    DOCUMENT_AI_SOURCES,
    DOCUMENT_AI_STATUSES,
    DocumentAICitation,
    DocumentAIPageText,
    DocumentAIRecord,
    DocumentAISearchResult,
    DocumentAIText,
    DocumentAIUploadResult,
    DocumentAIVersion,
)
from .repository import DocumentAIRepository, DocumentIntelligenceRepository
from .service import DocumentAIService, DocumentIntelligenceService

__all__ = [
    "DOCUMENT_AI_SOURCES",
    "DOCUMENT_AI_STATUSES",
    "DocumentAICitation",
    "DocumentAITextExtractionResult",
    "DocumentAIPageText",
    "DocumentAIRecord",
    "DocumentAISearchResult",
    "DocumentAIService",
    "DocumentAIText",
    "DocumentAIUploadResult",
    "DocumentAIVersion",
    "DocumentAIRepository",
    "DocumentIntelligenceRepository",
    "DocumentIntelligenceService",
]
