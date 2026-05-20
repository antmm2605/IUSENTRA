"""Façade stabile per evidenze fonte procedurali.

La logica resta in `pct.procedure_knowledge_pipeline`: questo modulo espone il
nome richiesto dalla pipeline senza duplicare validazioni o repository.
"""

from __future__ import annotations

from pct.procedure_knowledge_pipeline import (
    COPYRIGHT_POLICIES,
    SOURCE_TYPES,
    ValidationReport,
    add_source_evidence,
    validate_source_evidence,
)

__all__ = [
    "COPYRIGHT_POLICIES",
    "SOURCE_TYPES",
    "ValidationReport",
    "add_source_evidence",
    "validate_source_evidence",
]
