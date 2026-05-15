"""Research manuscript utilities for Legal Source Engine sources."""

from __future__ import annotations

from .models import SourceResearchManuscript
from .source_contract import LegalSourceContract


def get_research_manuscript(source: LegalSourceContract) -> SourceResearchManuscript:
    return source.manuscript


def source_research_summary(source: LegalSourceContract) -> dict[str, object]:
    manuscript = source.manuscript
    return {
        "source_id": manuscript.source_id,
        "source_name": manuscript.source_name,
        "official_url": manuscript.official_url,
        "category": manuscript.category,
        "jurisdiction": manuscript.jurisdiction,
        "access_modes": list(manuscript.access_modes),
        "identifiers_supported": list(manuscript.identifiers_supported),
        "versioning_supported": bool(manuscript.versioning_supported),
        "limitations": list(manuscript.limitations),
        "forbidden_behaviors": list(manuscript.forbidden_behaviors),
    }


__all__ = ["get_research_manuscript", "source_research_summary"]
