"""Modelli del sistema di policy fonti di Lex."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Tier(str, Enum):
    """Livelli di affidabilita' delle fonti."""

    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    UNKNOWN = "unknown"


class SourceMode(str, Enum):
    """Modalita' operative di uso delle fonti."""

    STRICT = "strict"
    BALANCED = "balanced"
    BROAD = "broad"


@dataclass(slots=True)
class SourceEvaluation:
    url: str
    domain: str
    area: str
    tier: Tier
    score: float
    reliability: str
    mode_used: str
    warnings: list[str] = field(default_factory=list)
    authority_band: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "domain": self.domain,
            "area": self.area,
            "tier": self.tier.value,
            "score": round(float(self.score), 3),
            "reliability": self.reliability,
            "mode_used": self.mode_used,
            "warnings": list(self.warnings),
            "authority_band": self.authority_band,
            "reason": self.reason,
        }


@dataclass(slots=True)
class SourcePolicySummary:
    area: str
    area_confidence: float
    mode_used: str
    total_sources: int
    tier_1_count: int
    tier_2_count: int
    tier_3_count: int
    unknown_count: int
    high_count: int
    medium_count: int
    low_count: int
    has_primary_sources: bool
    recommended_confidence: str
    reasoning: str
    warnings: list[str] = field(default_factory=list)
    block_unverified_answer: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "area": self.area,
            "area_confidence": round(float(self.area_confidence), 3),
            "mode_used": self.mode_used,
            "total_sources": int(self.total_sources),
            "tier_1_count": int(self.tier_1_count),
            "tier_2_count": int(self.tier_2_count),
            "tier_3_count": int(self.tier_3_count),
            "unknown_count": int(self.unknown_count),
            "high_count": int(self.high_count),
            "medium_count": int(self.medium_count),
            "low_count": int(self.low_count),
            "has_primary_sources": bool(self.has_primary_sources),
            "recommended_confidence": self.recommended_confidence,
            "reasoning": self.reasoning,
            "warnings": list(self.warnings),
            "block_unverified_answer": bool(self.block_unverified_answer),
        }


__all__ = [
    "SourceEvaluation",
    "SourceMode",
    "SourcePolicySummary",
    "Tier",
]
