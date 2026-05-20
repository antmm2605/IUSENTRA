"""Façade stabile per knowledge card procedurali originali.

La logica resta in `pct.procedure_knowledge_pipeline` per evitare un sistema
parallelo di schede, fonti e review.
"""

from __future__ import annotations

from pct.procedure_knowledge_pipeline import (
    REQUIRED_CARD_SECTIONS,
    approve_knowledge_card,
    build_original_knowledge_card,
    publish_knowledge_card,
    save_knowledge_card,
    submit_knowledge_card_for_review,
)

__all__ = [
    "REQUIRED_CARD_SECTIONS",
    "approve_knowledge_card",
    "build_original_knowledge_card",
    "publish_knowledge_card",
    "save_knowledge_card",
    "submit_knowledge_card_for_review",
]
