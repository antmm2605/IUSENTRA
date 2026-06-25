"""Struttura IUSENTRA per Unlimited-OCR self-hosted.

Il codice qui non vende né copia il runtime Baidu: replica la logica operativa
utile della repo (configurazione, immagini/PDF, client OpenAI-compatible,
batch e benchmark) con adapter governati per IUSENTRA.
"""

from .batch import UnlimitedOcrBatchResult, UnlimitedOcrJob, run_batch
from .client import UnlimitedOcrClient
from .config import UnlimitedOcrSettings
from .qa import answer_questions_from_text, default_legal_questions

__all__ = [
    "UnlimitedOcrBatchResult",
    "UnlimitedOcrClient",
    "UnlimitedOcrJob",
    "UnlimitedOcrSettings",
    "answer_questions_from_text",
    "default_legal_questions",
    "run_batch",
]
