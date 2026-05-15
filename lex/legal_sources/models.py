"""Core data models for the IUSENTRA Legal Source Engine.

The models in this package are deliberately passive: they describe sources,
citations, retrieved passages, dry-run scenarios and scorecards without
performing IO, network access or tenant data reads.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


@dataclass(slots=True)
class LegalCitation:
    source_id: str = ""
    source_name: str = ""
    source_category: str = ""
    jurisdiction: str = ""
    document_type: str = ""
    authority: str = ""
    title: str = ""
    number: str = ""
    date: str = ""
    article: str = ""
    paragraph: str = ""
    section: str = ""
    version_date: str = ""
    publication: str = ""
    publication_number: str = ""
    urn: str = ""
    eli: str = ""
    celex: str = ""
    ecli: str = ""
    hudoc_id: str = ""
    url: str = ""
    retrieved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_sufficient(self) -> bool:
        stable_identifier = any(_clean(value) for value in (self.urn, self.eli, self.celex, self.ecli, self.hudoc_id))
        has_locator = any(_clean(value) for value in (self.title, self.number, self.url)) or stable_identifier
        has_date = any(_clean(value) for value in (self.date, self.version_date, self.retrieved_at))
        return bool(
            _clean(self.source_id)
            and _clean(self.source_name)
            and _clean(self.document_type)
            and has_locator
            and has_date
        )


@dataclass(slots=True)
class RetrievedLegalPassage:
    text: str
    citation: LegalCitation
    score: float = 0.0
    retrieval_method: str = ""
    source_priority: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_valid_citation(self) -> bool:
        return bool(self.citation and self.citation.is_sufficient())

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "citation": self.citation.to_dict(),
            "score": float(self.score),
            "retrieval_method": self.retrieval_method,
            "source_priority": int(self.source_priority),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class LegalAnswerDraft:
    question: str
    answer: str
    passages: list[RetrievedLegalPassage] = field(default_factory=list)
    citations: list[LegalCitation] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def has_citations(self) -> bool:
        explicit = any(citation.is_sufficient() for citation in self.citations)
        passage_backed = any(passage.has_valid_citation() for passage in self.passages)
        return explicit or passage_backed


@dataclass(slots=True)
class SourceMetadata:
    source_id: str
    display_name: str
    category: str
    jurisdiction: str
    base_url: str
    official: bool
    priority: int
    supports_open_data: bool = False
    supports_search: bool = False
    supports_fetch_by_id: bool = False
    supports_versions: bool = False
    requires_auth: bool = False
    enabled_by_default: bool = False
    network_allowed_by_default: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceResearchManuscript:
    source_id: str
    source_name: str
    official_url: str
    category: str
    jurisdiction: str
    access_modes: list[str] = field(default_factory=list)
    identifiers_supported: list[str] = field(default_factory=list)
    versioning_supported: bool = False
    citation_requirements: list[str] = field(default_factory=list)
    ingestion_strategy: list[str] = field(default_factory=list)
    forbidden_behaviors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceScorecard:
    source_id: str
    officiality_score: float = 0.2
    citation_quality_score: float = 0.2
    identifier_stability_score: float = 0.2
    versioning_score: float = 0.1
    retrieval_reliability_score: float = 0.1
    coverage_score: float = 0.1
    updateability_score: float = 0.1
    legal_risk_score: float = 0.5
    implementation_completeness_score: float = 0.0
    enabled_recommendation: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DogfoodScenario:
    scenario_id: str
    question: str
    expected_source_types: list[str] = field(default_factory=list)
    required_citation_fields: list[str] = field(default_factory=list)
    fixture_passages: list[RetrievedLegalPassage] = field(default_factory=list)
    should_answer: bool = False
    expected_refusal_reason: str = ""


@dataclass(slots=True)
class DogfoodResult:
    scenario_id: str
    passed: bool
    answer_allowed: bool
    citations_valid: bool
    policy_errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicyError:
    code: str
    message: str
    severity: str = "error"
    source_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicyResult:
    allowed: bool = True
    errors: list[PolicyError] = field(default_factory=list)
    warnings: list[PolicyError] = field(default_factory=list)

    def add_error(self, code: str, message: str, *, source_id: str = "") -> None:
        self.allowed = False
        self.errors.append(PolicyError(code=code, message=message, severity="error", source_id=source_id))

    def add_warning(self, code: str, message: str, *, source_id: str = "") -> None:
        self.warnings.append(PolicyError(code=code, message=message, severity="warning", source_id=source_id))

    def merge(self, other: "PolicyResult") -> None:
        if not other.allowed:
            self.allowed = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": bool(self.allowed),
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }


@dataclass(slots=True)
class NormalizedLegalDocument:
    document_id: str
    source_id: str
    title: str
    document_type: str
    text: str = ""
    citation: LegalCitation | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_id": self.source_id,
            "title": self.title,
            "document_type": self.document_type,
            "text": self.text,
            "citation": self.citation.to_dict() if self.citation else None,
            "metadata": dict(self.metadata),
        }


__all__ = [
    "DogfoodResult",
    "DogfoodScenario",
    "LegalAnswerDraft",
    "LegalCitation",
    "NormalizedLegalDocument",
    "PolicyError",
    "PolicyResult",
    "RetrievedLegalPassage",
    "SourceMetadata",
    "SourceResearchManuscript",
    "SourceScorecard",
]
