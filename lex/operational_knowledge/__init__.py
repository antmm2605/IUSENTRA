"""Governed operational knowledge layer for Lex AI.

The package exposes deterministic, tenant-aware access to IUSENTRA operational
data. It is feature-flagged off by default and never performs network calls.
"""

from __future__ import annotations

from .models import OperationalAnswer, OperationalQueryContext, OperationalToolResult
from .reasoner import LexStudioReasoner
from .service import OperationalKnowledgeService
from .settings import OperationalKnowledgeSettings
from .source_registry import OperationalSourceRegistry, build_default_registry

__all__ = [
    "OperationalAnswer",
    "OperationalKnowledgeService",
    "OperationalKnowledgeSettings",
    "OperationalQueryContext",
    "OperationalSourceRegistry",
    "OperationalToolResult",
    "LexStudioReasoner",
    "build_default_registry",
]
