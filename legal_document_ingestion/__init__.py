"""Legal Document Understanding, OCR forense e indicizzazione Lex governata."""

from .file_intake import LegalDocumentIngestionService, LegalDocumentIngestionError
from .repository import LegalDocumentRepository

__all__ = [
    "LegalDocumentIngestionError",
    "LegalDocumentIngestionService",
    "LegalDocumentRepository",
]
