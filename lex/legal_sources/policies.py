"""Source-level policy checks for the Legal Source Engine."""

from __future__ import annotations

from typing import Iterable

from .models import PolicyResult
from .source_contract import LegalSourceContract


class SourcePolicy:
    """Validate that a source is safe to keep registered.

    This policy is intentionally stricter than the current implementation
    needs. It keeps every source disabled and non-networking unless a future
    integration explicitly proves the opposite with config, tests and audit.
    """

    def validate_source(self, source: LegalSourceContract) -> PolicyResult:
        result = source.validate_policy()
        metadata = source.metadata
        manuscript = source.manuscript
        source_id = metadata.source_id if metadata else ""

        if metadata and not metadata.official:
            result.add_warning("source_not_official", "La fonte non e' marcata come ufficiale.", source_id=source_id)
        if metadata and metadata.enabled_by_default:
            result.add_error("enabled_by_default_forbidden", "Le fonti legali devono restare disabilitate di default.", source_id=source_id)
        if metadata and metadata.network_allowed_by_default:
            result.add_error("network_by_default_forbidden", "La rete deve restare disabilitata di default.", source_id=source_id)
        if not getattr(source, "citation_policy", None):
            result.add_error("citation_policy_required", "La citation policy e' obbligatoria.", source_id=source_id)
        if int(getattr(source, "rate_limit_per_minute", 0) or 0) <= 0:
            result.add_error("rate_limit_required", "Il rate limit per fonte e' obbligatorio.", source_id=source_id)
        if not manuscript:
            result.add_error("manuscript_required", "Il manoscritto di ricerca e' obbligatorio.", source_id=source_id)
        else:
            if not manuscript.limitations:
                result.add_error("source_limits_required", "Il manoscritto deve documentare limiti e lacune.", source_id=source_id)
            if not manuscript.forbidden_behaviors:
                result.add_error("forbidden_behaviors_required", "Il manoscritto deve documentare i comportamenti vietati.", source_id=source_id)
        return result

    def validate_sources(self, sources: Iterable[LegalSourceContract]) -> PolicyResult:
        result = PolicyResult()
        for source in sources:
            result.merge(self.validate_source(source))
        return result


__all__ = ["SourcePolicy"]
