"""Safe base implementation for Legal Source Engine adapters."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import (
    LegalCitation,
    PolicyResult,
    SourceMetadata,
    SourceResearchManuscript,
    SourceScorecard,
)
from .source_contract import NetworkDisabledError


DEFAULT_FORBIDDEN_BEHAVIORS = [
    "crawling integrale del sito",
    "scraping aggressivo",
    "bypass di robots.txt, termini d'uso, autenticazione o rate limit",
    "uso di cookie, token o credenziali non configurati esplicitamente",
    "ingestione di dati cliente, tenant, fascicoli o messaggi di studio",
]


DEFAULT_CITATION_REQUIREMENTS = [
    "nome fonte",
    "categoria fonte",
    "giurisdizione",
    "tipo documento",
    "autorita quando applicabile",
    "titolo",
    "numero e data quando disponibili",
    "articolo, comma o sezione quando disponibili",
    "URL o identificativo stabile",
    "timestamp di recupero",
]


class BaseLegalSourceAdapter:
    """A non-networking adapter base.

    Subclasses define metadata, research manuscript and citation policy. The
    base class never performs live fetches. Search returns an empty list as a
    safe dry-run default, while document fetch methods raise NetworkDisabledError
    because they would require source access in future phases.
    """

    def __init__(
        self,
        *,
        metadata: SourceMetadata,
        manuscript: SourceResearchManuscript,
        scorecard: SourceScorecard,
        citation_policy: dict[str, Any],
        rate_limit_per_minute: int = 30,
    ) -> None:
        self.metadata = metadata
        self.manuscript = manuscript
        self.scorecard = scorecard
        self.citation_policy = dict(citation_policy or {})
        self.rate_limit_per_minute = int(rate_limit_per_minute or 0)

    @property
    def source_id(self) -> str:
        return self.metadata.source_id

    def discover(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "manuscript": self.manuscript.to_dict(),
            "scorecard": self.scorecard.to_dict(),
            "citation_policy": deepcopy(self.citation_policy),
            "rate_limit_per_minute": self.rate_limit_per_minute,
        }

    def search(self, query: str, **filters: Any) -> list[Any]:
        _ = query, filters
        return []

    def fetch(self, identifier: str, **filters: Any) -> Any:
        _ = filters
        raise NetworkDisabledError(
            f"Network access is disabled for source '{self.source_id}'. Cannot fetch '{identifier}'."
        )

    def fetch_version(self, identifier: str, version_date: str) -> Any:
        raise NetworkDisabledError(
            f"Network access is disabled for source '{self.source_id}'. Cannot fetch '{identifier}' at '{version_date}'."
        )

    def normalize(self, raw_document: Any) -> dict[str, Any]:
        if isinstance(raw_document, dict):
            return dict(raw_document)
        return {"raw_document": raw_document, "source_id": self.source_id}

    def cite(self, normalized_document: Any) -> LegalCitation:
        data = dict(normalized_document or {}) if isinstance(normalized_document, dict) else {}
        return LegalCitation(
            source_id=self.source_id,
            source_name=self.metadata.display_name,
            source_category=self.metadata.category,
            jurisdiction=self.metadata.jurisdiction,
            document_type=str(data.get("document_type") or data.get("tipo_documento") or ""),
            authority=str(data.get("authority") or data.get("autorita") or self.metadata.display_name),
            title=str(data.get("title") or data.get("titolo") or ""),
            number=str(data.get("number") or data.get("numero") or ""),
            date=str(data.get("date") or data.get("data") or ""),
            article=str(data.get("article") or data.get("articolo") or ""),
            paragraph=str(data.get("paragraph") or data.get("comma") or ""),
            section=str(data.get("section") or data.get("sezione") or ""),
            version_date=str(data.get("version_date") or data.get("data_versione") or ""),
            publication=str(data.get("publication") or data.get("pubblicazione") or ""),
            publication_number=str(data.get("publication_number") or data.get("numero_pubblicazione") or ""),
            urn=str(data.get("urn") or ""),
            eli=str(data.get("eli") or ""),
            celex=str(data.get("celex") or ""),
            ecli=str(data.get("ecli") or ""),
            hudoc_id=str(data.get("hudoc_id") or ""),
            url=str(data.get("url") or data.get("official_url") or ""),
            retrieved_at=str(data.get("retrieved_at") or data.get("recuperato_il") or ""),
        )

    def validate_policy(self) -> PolicyResult:
        result = PolicyResult()
        source_id = self.source_id
        if not self.metadata:
            result.add_error("missing_metadata", "La fonte non ha metadata dichiarati.", source_id=source_id)
            return result
        if not self.citation_policy:
            result.add_error("missing_citation_policy", "La fonte non ha una citation policy.", source_id=source_id)
        if self.rate_limit_per_minute <= 0:
            result.add_error("missing_rate_limit", "La fonte non ha un rate limit configurato.", source_id=source_id)
        if self.metadata.network_allowed_by_default:
            result.add_error("network_enabled_by_default", "La rete non puo essere abilitata di default.", source_id=source_id)
        if self.metadata.enabled_by_default:
            result.add_error("source_enabled_by_default", "La fonte non puo essere abilitata di default.", source_id=source_id)
        if not self.manuscript:
            result.add_error("missing_research_manuscript", "La fonte non ha manoscritto di ricerca.", source_id=source_id)
        else:
            if not self.manuscript.forbidden_behaviors:
                result.add_error("missing_forbidden_behaviors", "Il manoscritto non documenta i comportamenti vietati.", source_id=source_id)
            if not self.manuscript.limitations:
                result.add_error("missing_limitations", "Il manoscritto non documenta termini, limiti o lacune.", source_id=source_id)
        return result

    def healthcheck(self) -> dict[str, Any]:
        policy = self.validate_policy()
        return {
            "source_id": self.source_id,
            "status": "disabled",
            "enabled": False,
            "network_allowed": False,
            "policy_ok": policy.allowed,
            "errors": [error.to_dict() for error in policy.errors],
            "warnings": [warning.to_dict() for warning in policy.warnings],
        }


def source_metadata(
    *,
    source_id: str,
    display_name: str,
    category: str,
    jurisdiction: str,
    base_url: str,
    official: bool,
    priority: int,
    supports_open_data: bool = False,
    supports_search: bool = False,
    supports_fetch_by_id: bool = False,
    supports_versions: bool = False,
    requires_auth: bool = False,
) -> SourceMetadata:
    return SourceMetadata(
        source_id=source_id,
        display_name=display_name,
        category=category,
        jurisdiction=jurisdiction,
        base_url=base_url,
        official=official,
        priority=priority,
        supports_open_data=supports_open_data,
        supports_search=supports_search,
        supports_fetch_by_id=supports_fetch_by_id,
        supports_versions=supports_versions,
        requires_auth=requires_auth,
        enabled_by_default=False,
        network_allowed_by_default=False,
    )


def source_manuscript(
    *,
    metadata: SourceMetadata,
    access_modes: list[str],
    identifiers_supported: list[str],
    versioning_supported: bool,
    ingestion_strategy: list[str],
    limitations: list[str],
    notes: list[str] | None = None,
    citation_requirements: list[str] | None = None,
    forbidden_behaviors: list[str] | None = None,
) -> SourceResearchManuscript:
    return SourceResearchManuscript(
        source_id=metadata.source_id,
        source_name=metadata.display_name,
        official_url=metadata.base_url,
        category=metadata.category,
        jurisdiction=metadata.jurisdiction,
        access_modes=list(access_modes),
        identifiers_supported=list(identifiers_supported),
        versioning_supported=bool(versioning_supported),
        citation_requirements=list(citation_requirements or DEFAULT_CITATION_REQUIREMENTS),
        ingestion_strategy=list(ingestion_strategy),
        forbidden_behaviors=list(forbidden_behaviors or DEFAULT_FORBIDDEN_BEHAVIORS),
        limitations=list(limitations),
        notes=list(notes or []),
    )


def source_scorecard(
    *,
    source_id: str,
    official: bool,
    citation_quality: float = 0.45,
    identifier_stability: float = 0.45,
    versioning: float = 0.2,
    retrieval_reliability: float = 0.1,
    coverage: float = 0.2,
    updateability: float = 0.2,
    legal_risk: float = 0.45,
    implementation_completeness: float = 0.1,
    notes: list[str] | None = None,
) -> SourceScorecard:
    return SourceScorecard(
        source_id=source_id,
        officiality_score=0.8 if official else 0.3,
        citation_quality_score=float(citation_quality),
        identifier_stability_score=float(identifier_stability),
        versioning_score=float(versioning),
        retrieval_reliability_score=float(retrieval_reliability),
        coverage_score=float(coverage),
        updateability_score=float(updateability),
        legal_risk_score=float(legal_risk),
        implementation_completeness_score=float(implementation_completeness),
        enabled_recommendation=False,
        notes=list(notes or ["Scheletro conservativo: non raccomandare abilitazione finche non esistono fixture, policy e test fonte dedicati."]),
    )


def citation_policy(
    *,
    document_types: list[str],
    identifiers: list[str],
    required_fields: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "document_types": list(document_types),
        "identifiers": list(identifiers),
        "required_fields": list(required_fields or DEFAULT_CITATION_REQUIREMENTS),
        "notes": list(notes or []),
    }


__all__ = [
    "BaseLegalSourceAdapter",
    "DEFAULT_CITATION_REQUIREMENTS",
    "DEFAULT_FORBIDDEN_BEHAVIORS",
    "citation_policy",
    "source_manuscript",
    "source_metadata",
    "source_scorecard",
]
