"""Optional external/local sidecar integrations for Lex."""

from .local_deep_research_client import (
    LocalDeepResearchClient,
    LocalDeepResearchError,
    LocalDeepResearchPolicyError,
)

__all__ = [
    "LocalDeepResearchClient",
    "LocalDeepResearchError",
    "LocalDeepResearchPolicyError",
]
