from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import (
    FactKind,
    InsightType,
    IntentType,
    ModuleType,
    PackStatus,
    ProviderType,
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
    allow_external_research: bool = True
    require_citations: bool = False
    require_official_sources: bool = False
    max_latency_ms: int | None = None


@dataclass(slots=True)
class Citation:
    source_type: SourceType | str
    source_id: str
    title: str
    excerpt: str
    confidence: float = 0.0
    authority: str = ""
    url: str | None = None
    trust_class: str = ""
    source_level: int = 0
    verified_reference: bool = False
    published_at: str | None = None
    freshness_score: float = 0.0
    page_no: int | None = None
    section_path: str = ""
    chunk_index: int | None = None


@dataclass(slots=True)
class EvidenceItem:
    source_type: SourceType | str
    source_id: str
    title: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    trust_class: str = ""
    source_level: int = 0
    trust_score: float = 0.0
    freshness_score: float = 0.0
    context_fit_score: float = 0.0
    consensus_score: float = 0.0
    verified_reference: bool = False
    authority: str = ""
    published_at: str | None = None
    official_url: str | None = None


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
class AnswerContract:
    workflow: WorkflowType
    sections: list[str] = field(default_factory=list)
    require_citations: bool = False
    require_official_sources: bool = False
    require_source_comparison: bool = False
    allow_abstention: bool = True
    provider_hint: ProviderType | None = None
    target_latency_ms: int | None = None
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
    aggregate_trust_score: float = 0.0
    aggregate_freshness_score: float = 0.0
    aggregate_context_fit_score: float = 0.0
    aggregate_consensus_score: float = 0.0
    compared_sources: list[dict[str, Any]] = field(default_factory=list)
    conflicting_items: list[str] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    needs_human_review: bool = False
    sufficient: bool = False


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
    legal_basis: list[str] = field(default_factory=list)
    considered_sources: list[str] = field(default_factory=list)
    compared_sources: list[dict[str, Any]] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    answer_mode: str = "grounded"
    evidence_summary: dict[str, Any] = field(default_factory=dict)


def answer_contract_for(workflow: WorkflowType) -> AnswerContract:
    if workflow == "fascicolo":
        return AnswerContract(
            workflow=workflow,
            sections=["risposta", "fonti_considerate", "prossime_azioni"],
            require_citations=True,
            allow_abstention=True,
            target_latency_ms=2500,
        )
    if workflow == "udienza":
        return AnswerContract(
            workflow=workflow,
            sections=["risposta", "timeline", "criticita", "prossime_azioni"],
            require_citations=True,
            allow_abstention=True,
            target_latency_ms=3000,
        )
    if workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti"}:
        return AnswerContract(
            workflow=workflow,
            sections=["risposta", "base_legale", "fonti_considerate", "confronto_fonti", "limiti"],
            require_citations=True,
            require_official_sources=True,
            require_source_comparison=True,
            allow_abstention=True,
            provider_hint="ollama",
            target_latency_ms=4500,
        )
    if workflow in {"economico", "next_action", "cabina", "telematico_status", "compliance"}:
        return AnswerContract(
            workflow=workflow,
            sections=["risposta", "dati_usati", "prossima_azione"],
            require_citations=False,
            allow_abstention=False,
            provider_hint="deterministic",
            target_latency_ms=1200,
        )
    return AnswerContract(
        workflow=workflow,
        sections=["risposta", "fonti_considerate"],
        require_citations=False,
        allow_abstention=True,
        target_latency_ms=2500,
    )
