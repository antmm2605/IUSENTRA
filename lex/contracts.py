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
    rewritten_draft: str | None = None


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


def answer_contract_for(workflow: WorkflowType) -> AnswerContract:  # noqa: C901
    # ------------------------------------------------------------------ #
    # Redazione legale — lettere, diffide, PEC, atti processuali           #
    # ------------------------------------------------------------------ #
    if workflow in {
        "drafting_legal_letter", "lettera", "bozza_lettera", "atto", "bozza_atto",
        "pec_comunicazioni",
    }:
        return AnswerContract(
            workflow=workflow,
            sections=["bozza", "punti_da_adattare", "avvertenze"],
            require_citations=False,
            require_official_sources=False,
            allow_abstention=False,
            provider_hint="ollama",
            target_latency_ms=3500,
            metadata={
                "italian_only": True,
                "disclaimer_suppressed": True,
                "no_json_output": True,
                "no_english_output": True,
            },
        )

    # ------------------------------------------------------------------ #
    # Termini processuali — calcolo deterministico                          #
    # ------------------------------------------------------------------ #
    if workflow == "termini_processuali":
        return AnswerContract(
            workflow=workflow,
            sections=["scadenza_calcolata", "normativa_applicata", "avvertenze", "prossima_azione"],
            require_citations=True,
            require_official_sources=True,
            allow_abstention=False,
            provider_hint="deterministic",
            target_latency_ms=800,
            metadata={
                "italian_only": True,
                "disclaimer_suppressed": True,
                "deterministic": True,
            },
        )

    # ------------------------------------------------------------------ #
    # Deposito telematico — checklist portali                               #
    # ------------------------------------------------------------------ #
    if workflow in {"deposito_telematico", "telematico_status", "compliance"}:
        return AnswerContract(
            workflow=workflow,
            sections=["checklist", "portale", "requisiti_tecnici", "diagnosi_errori", "prossima_azione"],
            require_citations=False,
            allow_abstention=False,
            provider_hint="deterministic",
            target_latency_ms=1000,
            metadata={
                "italian_only": True,
                "disclaimer_suppressed": True,
            },
        )

    # ------------------------------------------------------------------ #
    # Feedback e diagnosi Lex                                               #
    # ------------------------------------------------------------------ #
    if workflow == "lex_feedback_diagnostico":
        return AnswerContract(
            workflow=workflow,
            sections=["comprensione", "riformulazione", "proposta_corretta"],
            require_citations=False,
            allow_abstention=False,
            provider_hint="deterministic",
            target_latency_ms=600,
            metadata={
                "italian_only": True,
                "disclaimer_suppressed": True,
            },
        )

    # ------------------------------------------------------------------ #
    # Fascicolo operativo                                                   #
    # ------------------------------------------------------------------ #
    if workflow == "fascicolo":
        return AnswerContract(
            workflow=workflow,
            sections=["quadro_pratica", "documenti_chiave", "scadenze", "prossime_azioni"],
            require_citations=True,
            allow_abstention=True,
            provider_hint="deterministic",
            target_latency_ms=2500,
            metadata={"italian_only": True},
        )

    # ------------------------------------------------------------------ #
    # Udienza                                                               #
    # ------------------------------------------------------------------ #
    if workflow == "udienza":
        return AnswerContract(
            workflow=workflow,
            sections=["risposta", "timeline", "criticita", "prossime_azioni"],
            require_citations=True,
            allow_abstention=True,
            target_latency_ms=3000,
            metadata={"italian_only": True},
        )

    # ------------------------------------------------------------------ #
    # Lookup dati cliente/studio (dati interni, no web)                    #
    # ------------------------------------------------------------------ #
    if workflow == "studio_data_lookup":
        return AnswerContract(
            workflow=workflow,
            sections=[
                "cliente_individuato",
                "dati_anagrafici",
                "recapiti",
                "fascicoli_collegati",
                "dati_mancanti",
                "prossima_azione",
            ],
            require_citations=False,
            require_official_sources=False,
            require_source_comparison=False,
            allow_abstention=False,
            provider_hint="deterministic",
            target_latency_ms=800,
            metadata={
                "italian_only": True,
                "studio_internal_only": True,
                "web_forbidden": True,
                "requires_tool": "studio_data_gateway",
                "no_json_output": True,
                "suppress_unrelated_sources": True,
            },
        )

    # ------------------------------------------------------------------ #
    # Giurisprudenza specifica (sentenza con numero)                        #
    # ------------------------------------------------------------------ #
    if workflow == "giurisprudenza_specifica":
        return AnswerContract(
            workflow=workflow,
            sections=["riferimento", "massima", "organo_giudicante", "applicazione_pratica", "fonti"],
            require_citations=True,
            require_official_sources=True,
            require_source_comparison=False,
            allow_abstention=True,
            provider_hint="ollama",
            target_latency_ms=4000,
            metadata={
                "italian_only": True,
                "strict_legal": True,
                "no_invented_references": True,
            },
        )

    # ------------------------------------------------------------------ #
    # Ricerca normativa / giurisprudenziale / prassi / fonti               #
    # ------------------------------------------------------------------ #
    if workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti", "intelligence"}:
        return AnswerContract(
            workflow=workflow,
            sections=["risposta", "base_legale", "fonti_considerate", "confronto_fonti", "limiti"],
            require_citations=True,
            require_official_sources=True,
            require_source_comparison=True,
            allow_abstention=True,
            provider_hint="ollama",
            target_latency_ms=4500,
            metadata={
                "italian_only": True,
                "strict_legal": True,
                "no_invented_references": True,
            },
        )

    # ------------------------------------------------------------------ #
    # Economico / preventivo / tariffario                                   #
    # ------------------------------------------------------------------ #
    if workflow in {"economico", "next_action", "cabina"}:
        return AnswerContract(
            workflow=workflow,
            sections=["calcolo", "dati_usati", "normativa", "prossima_azione"],
            require_citations=False,
            allow_abstention=False,
            provider_hint="deterministic",
            target_latency_ms=1200,
            metadata={
                "italian_only": True,
                "disclaimer_suppressed": True,
            },
        )

    # ------------------------------------------------------------------ #
    # Analisi documento                                                     #
    # ------------------------------------------------------------------ #
    if workflow in {"documento", "document_editor", "documento_editor"}:
        return AnswerContract(
            workflow=workflow,
            sections=["sintesi", "punti_chiave", "rischi_lacune", "obblighi", "prossime_azioni"],
            require_citations=False,
            allow_abstention=True,
            provider_hint="ollama",
            target_latency_ms=3500,
            metadata={"italian_only": True},
        )

    # ------------------------------------------------------------------ #
    # Default                                                               #
    # ------------------------------------------------------------------ #
    return AnswerContract(
        workflow=workflow,
        sections=["risposta", "fonti_considerate"],
        require_citations=False,
        allow_abstention=True,
        target_latency_ms=2500,
        metadata={"italian_only": True},
    )
