"""Contratti applicativi del bounded context Lex."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import IntentType, RiskLevel, SourceType, WorkflowType


@dataclass(slots=True)
class LexRequest:
    tenant_id: str
    user_id: str
    session_id: str
    query: str
    intent: IntentType = "ask_lex"
    fascicolo_id: str | None = None
    document_id: str | None = None
    workflow_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Citation:
    source_type: SourceType | str
    source_id: str
    title: str
    excerpt: str
    confidence: float = 0.0
    authority: str = ""
    url: str | None = None


@dataclass(slots=True)
class EvidenceItem:
    source_type: SourceType | str
    source_id: str
    title: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievalPlan:
    workflow: WorkflowType
    queries: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = "low"


@dataclass(slots=True)
class GuardVerdict:
    allowed: bool
    warnings: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    risk_level: RiskLevel = "low"


@dataclass(slots=True)
class ProviderDraft:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LexResponse:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    risk_level: RiskLevel = "low"
    metadata: dict[str, Any] = field(default_factory=dict)
