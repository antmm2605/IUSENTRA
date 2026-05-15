"""Native IUSENTRA Legal Source Engine for Lex AI.

The package registers source adapters, data contracts, citation policy, answer
policy, dogfood scenarios, local reports and a controlled local auto-populator.
Network access remains disabled unless a future connector explicitly opts in.
"""

from __future__ import annotations

from .answer_policy import AnswerPolicy
from .dogfood import example_dogfood_scenarios, run_dogfood_scenario, run_dogfood_scenarios
from .models import (
    DogfoodResult,
    DogfoodScenario,
    LegalAnswerDraft,
    LegalCitation,
    RetrievedLegalPassage,
    SourceMetadata,
    SourceResearchManuscript,
    SourceScorecard,
)
from .registry import LegalSourceRegistry, create_default_registry
from .retriever import LegalSourceRetriever
from .settings import LegalSourceEngineSettings
from .source_contract import LegalSourceContract, NetworkDisabledError, SourcePolicyError
from .tools import LegalSourceTools


__all__ = [
    "AnswerPolicy",
    "DogfoodResult",
    "DogfoodScenario",
    "LegalAnswerDraft",
    "LegalCitation",
    "LegalSourceContract",
    "LegalSourceEngineSettings",
    "LegalSourceRegistry",
    "LegalSourceRetriever",
    "LegalSourceTools",
    "NetworkDisabledError",
    "RetrievedLegalPassage",
    "SourceMetadata",
    "SourcePolicyError",
    "SourceResearchManuscript",
    "SourceScorecard",
    "create_default_registry",
    "example_dogfood_scenarios",
    "run_dogfood_scenario",
    "run_dogfood_scenarios",
]
