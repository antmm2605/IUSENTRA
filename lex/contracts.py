"""Contratti applicativi del bounded context Lex."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import (
    FactKind,
    InsightType,
    IntentType,
    ModuleType,
    PackStatus,
    RiskLevel,
    SourceType,
    WorkflowType,
)


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
class LexEvent:
    module: ModuleType | str
    event_type: str
    entity_id: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    has_errors: bool = False


@dataclass(slots=True)
class LexFact:
    module: ModuleType | str
    fact_type: str
    value: Any
    kind: FactKind = "fatto_certo"
    entity_id: str = ""
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ContextRequest:
    module: ModuleType | str
    workflow: WorkflowType
    query: str
    fascicolo_id: str = ""
    document_id: str = ""
    requested_sections: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModuleResultPack:
    module: ModuleType | str
    status: PackStatus = "ok"
    context_request: ContextRequest | None = None
    facts: list[LexFact] = field(default_factory=list)
    events: list[LexEvent] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InsightItem:
    insight_type: InsightType | str
    title: str
    detail: str
    module: ModuleType | str = "cabina"
    severity: RiskLevel = "low"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidencePack:
    queries: list[str] = field(default_factory=list)
    items: list[EvidenceItem] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    official_sources: list[str] = field(default_factory=list)
    trusted_sources: list[str] = field(default_factory=list)
    freshness: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkingMemorySnapshot:
    session_facts: list[LexFact] = field(default_factory=list)
    case_facts: list[LexFact] = field(default_factory=list)
    timeline: list[LexEvent] = field(default_factory=list)
    profiles: dict[str, Any] = field(default_factory=dict)
    economic_facts: list[LexFact] = field(default_factory=list)
    research_index: list[str] = field(default_factory=list)
    module_packs: list[ModuleResultPack] = field(default_factory=list)


@dataclass(slots=True)
class LexResponse:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    risk_level: RiskLevel = "low"
    metadata: dict[str, Any] = field(default_factory=dict)