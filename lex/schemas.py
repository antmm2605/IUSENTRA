"""Schemi applicativi di Lex."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LexRequest:
    pratica_id: str = ""
    message: str = ""
    mode: str = "general"
    conversation_id: str = ""
    fascicolo_id: str = ""
    messages: list[dict[str, object]] = field(default_factory=list)
    attachments: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class LexSource:
    source_type: str
    source_id: str
    title: str
    excerpt: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "type": self.source_type,
            "id": self.source_id,
            "title": self.title,
            "excerpt": self.excerpt,
            "score": float(self.score),
        }
        payload.update(self.metadata)
        return payload


@dataclass(slots=True)
class LexGroundingResult:
    grounded: bool
    enough_sources: bool
    confidence: float
    warnings: list[str] = field(default_factory=list)
    confidence_label: str = ""
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "grounded": bool(self.grounded),
            "enough_sources": bool(self.enough_sources),
            "confidence": float(self.confidence),
            "warnings": list(self.warnings),
            "confidence_label": str(self.confidence_label),
            "reasoning": str(self.reasoning),
        }
