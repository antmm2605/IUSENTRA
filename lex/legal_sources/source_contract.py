"""Source contract for the native Legal Source Engine."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .models import LegalCitation, PolicyResult, SourceMetadata, SourceResearchManuscript, SourceScorecard


class LegalSourceEngineError(RuntimeError):
    """Base error for Legal Source Engine policy and runtime failures."""


class NetworkDisabledError(LegalSourceEngineError):
    """Raised when a source operation would require network access."""


class SourcePolicyError(LegalSourceEngineError):
    """Raised when a source cannot satisfy the configured source policy."""


@runtime_checkable
class LegalSourceContract(Protocol):
    metadata: SourceMetadata
    manuscript: SourceResearchManuscript
    scorecard: SourceScorecard
    citation_policy: dict[str, Any]
    rate_limit_per_minute: int

    def discover(self) -> dict[str, Any]:
        ...

    def search(self, query: str, **filters: Any) -> list[Any]:
        ...

    def fetch(self, identifier: str, **filters: Any) -> Any:
        ...

    def fetch_version(self, identifier: str, version_date: str) -> Any:
        ...

    def normalize(self, raw_document: Any) -> Any:
        ...

    def cite(self, normalized_document: Any) -> LegalCitation:
        ...

    def validate_policy(self) -> PolicyResult:
        ...

    def healthcheck(self) -> dict[str, Any]:
        ...


__all__ = [
    "LegalSourceContract",
    "LegalSourceEngineError",
    "NetworkDisabledError",
    "SourcePolicyError",
]
