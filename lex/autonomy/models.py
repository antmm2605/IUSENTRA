"""Modelli del ciclo autonomo di Lex (lacune, domande, proposte, configurazione).

`ImprovementProposal.requires_human_review` è SEMPRE True per costruzione:
il ciclo propone, non applica mai. `CycleConfig` nasce solo da
`lex.autonomy.safety.validate_cycle_config` (fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lex.learning.models import stable_id_from

UNKNOWN_CONCEPT_KINDS: tuple[str, ...] = (
    "norma_non_letta",
    "termine_sconosciuto",
    "area_scoperta",
    "fonte_debole",
    "concetto_isolato",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


@dataclass(slots=True)
class UnknownConcept:
    """Lacuna rilevata dal gap detector (cosa Lex non sa ancora)."""

    concept: str
    kind: str
    area: str = ""
    reason: str = ""
    priority: float = 0.5
    confidence: float = 0.7
    evidence: list[str] = field(default_factory=list)
    suggested_queries: list[str] = field(default_factory=list)

    def stable_id(self) -> str:
        return stable_id_from({"concept": self.concept.casefold(), "kind": self.kind, "area": self.area})

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept": self.concept,
            "kind": self.kind,
            "area": self.area,
            "reason": self.reason,
            "priority": round(float(self.priority), 3),
            "confidence": round(float(self.confidence), 2),
            "evidence": list(self.evidence),
            "suggested_queries": list(self.suggested_queries),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> UnknownConcept:
        return cls(
            concept=_clean(payload.get("concept")),
            kind=_clean(payload.get("kind")) or "termine_sconosciuto",
            area=_clean(payload.get("area")),
            reason=_clean(payload.get("reason")),
            priority=float(payload.get("priority") or 0.5),
            confidence=float(payload.get("confidence") or 0.7),
            evidence=[_clean(item) for item in payload.get("evidence") or [] if _clean(item)],
            suggested_queries=[_clean(item) for item in payload.get("suggested_queries") or [] if _clean(item)],
        )


@dataclass(slots=True)
class ResearchQuestion:
    """Domanda di ricerca derivata da una lacuna (deterministica, senza PII)."""

    question: str
    area: str = ""
    kind: str = ""
    priority: float = 0.5
    target_citation: str = ""
    target_term: str = ""
    required_source_types: list[str] = field(default_factory=list)
    query_candidates: list[str] = field(default_factory=list)
    reason: str = ""
    origin_concept_id: str = ""

    def stable_id(self) -> str:
        return stable_id_from({"question": self.question.casefold(), "area": self.area})

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "area": self.area,
            "kind": self.kind,
            "priority": round(float(self.priority), 3),
            "target_citation": self.target_citation,
            "target_term": self.target_term,
            "required_source_types": list(self.required_source_types),
            "query_candidates": list(self.query_candidates),
            "reason": self.reason,
            "origin_concept_id": self.origin_concept_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ResearchQuestion:
        return cls(
            question=_clean(payload.get("question")),
            area=_clean(payload.get("area")),
            kind=_clean(payload.get("kind")),
            priority=float(payload.get("priority") or 0.5),
            target_citation=_clean(payload.get("target_citation")),
            target_term=_clean(payload.get("target_term")),
            required_source_types=[_clean(item) for item in payload.get("required_source_types") or [] if _clean(item)],
            query_candidates=[_clean(item) for item in payload.get("query_candidates") or [] if _clean(item)],
            reason=_clean(payload.get("reason")),
            origin_concept_id=_clean(payload.get("origin_concept_id")),
        )


@dataclass(slots=True)
class ImprovementProposal:
    """Proposta di miglioramento verificabile: MAI applicata automaticamente."""

    kind: str
    title: str
    description: str
    target_module: str = ""
    confidence: float = 0.7
    evidence: list[str] = field(default_factory=list)
    suggested_tests: list[str] = field(default_factory=list)
    requires_human_review: bool = True

    def __post_init__(self) -> None:
        # Invariante di sicurezza: nessuna proposta è mai auto-applicabile.
        self.requires_human_review = True

    def stable_id(self) -> str:
        return stable_id_from({"kind": self.kind, "title": self.title.casefold()})

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "target_module": self.target_module,
            "confidence": round(float(self.confidence), 2),
            "evidence": list(self.evidence),
            "suggested_tests": list(self.suggested_tests),
            "requires_human_review": True,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ImprovementProposal:
        return cls(
            kind=_clean(payload.get("kind")),
            title=_clean(payload.get("title")),
            description=_clean(payload.get("description")),
            target_module=_clean(payload.get("target_module")),
            confidence=float(payload.get("confidence") or 0.7),
            evidence=[_clean(item) for item in payload.get("evidence") or [] if _clean(item)],
            suggested_tests=[_clean(item) for item in payload.get("suggested_tests") or [] if _clean(item)],
        )


@dataclass(slots=True)
class CycleConfig:
    """Configurazione VALIDATA del ciclo (creata solo da validate_cycle_config)."""

    mode: str = "offline"  # offline | web
    allow_web: bool = False
    max_cycles: int = 2
    max_queries: int = 10
    max_sources: int = 6
    max_runtime_seconds: int = 300
    max_questions_per_cycle: int = 5
    max_queries_per_question: int = 3
    min_sources_per_area: int = 2
    require_official_sources: bool = True
    source_mode: str = "strict"
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    min_interval_seconds: float = 2.0
    timeout_seconds: int = 20
    max_bytes: int = 2_000_000
    respect_robots: bool = True
    memory_dir: str = ""
    dry_run: bool = False
    offline_results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "allow_web": self.allow_web,
            "max_cycles": self.max_cycles,
            "max_queries": self.max_queries,
            "max_sources": self.max_sources,
            "max_runtime_seconds": self.max_runtime_seconds,
            "max_questions_per_cycle": self.max_questions_per_cycle,
            "max_queries_per_question": self.max_queries_per_question,
            "min_sources_per_area": self.min_sources_per_area,
            "require_official_sources": self.require_official_sources,
            "source_mode": self.source_mode,
            "allowlist": list(self.allowlist),
            "denylist": list(self.denylist),
            "min_interval_seconds": self.min_interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "max_bytes": self.max_bytes,
            "respect_robots": self.respect_robots,
            "memory_dir": self.memory_dir,
            "dry_run": self.dry_run,
            "offline_results_queries": len(self.offline_results),
        }


@dataclass(slots=True)
class LearningCycleResult:
    """Esito complessivo di una esecuzione del ciclo autonomo."""

    mode: str
    cycles_run: int = 0
    questions_generated: int = 0
    queries_executed: int = 0
    sources_fetched: int = 0
    sources_rejected: int = 0
    new_terms: int = 0
    new_citations: int = 0
    new_readings: int = 0
    new_unknown_concepts: int = 0
    proposals_count: int = 0
    signals: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    started_at: str = ""
    finished_at: str = ""
    memory_dir: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "cycles_run": self.cycles_run,
            "questions_generated": self.questions_generated,
            "queries_executed": self.queries_executed,
            "sources_fetched": self.sources_fetched,
            "sources_rejected": self.sources_rejected,
            "new_terms": self.new_terms,
            "new_citations": self.new_citations,
            "new_readings": self.new_readings,
            "new_unknown_concepts": self.new_unknown_concepts,
            "proposals_count": self.proposals_count,
            "signals": [dict(item) for item in self.signals],
            "stop_reason": self.stop_reason,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "memory_dir": self.memory_dir,
            "errors": list(self.errors),
        }


__all__ = [
    "UNKNOWN_CONCEPT_KINDS",
    "CycleConfig",
    "ImprovementProposal",
    "LearningCycleResult",
    "ResearchQuestion",
    "UnknownConcept",
]
