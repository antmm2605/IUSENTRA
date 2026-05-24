"""OCR legal-grade per documenti e PEC IUSENTRA."""

from .config import LegalOcrConfig
from .pipeline import LegalOcrPipeline
from .storage import LegalOcrEvidenceStore

__all__ = ["LegalOcrConfig", "LegalOcrPipeline", "LegalOcrEvidenceStore"]
