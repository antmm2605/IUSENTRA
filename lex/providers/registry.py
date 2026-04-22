from __future__ import annotations

import os

from .deterministic_provider import DeterministicProvider
from .mock_provider import MockProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from lex.contracts import answer_contract_for


class ProviderRegistry:
    def __init__(self) -> None:
        self.providers = {
            "mock": MockProvider(),
            "ollama": OllamaProvider(),
            "openai": OpenAIProvider(),
            "deterministic": DeterministicProvider(),
        }

    def pick(self, request, context, workflow, evidence):
        metadata = dict(getattr(request, "metadata", {}) or {})
        forced = str(metadata.get("force_provider") or "").strip().lower()
        if forced and forced in self.providers:
            return self.providers[forced]

        if os.getenv("LEX_PROVIDER_FORCE_MOCK", "").strip() == "1":
            return self.providers["mock"]

        contract = answer_contract_for(workflow)
        if contract.provider_hint and contract.provider_hint in self.providers:
            return self.providers[contract.provider_hint]

        if workflow in {"economico", "next_action", "cabina", "telematico_status", "compliance"}:
            return self.providers["deterministic"]

        if workflow in {
            "telematico",
            "udienza",
            "atto",
            "fascicolo",
            "normativa",
            "giurisprudenza",
            "prassi",
            "research",
            "fonti",
            "documento",
            "question_answering",
            "intelligence",
        }:
            return self.providers["ollama"]

        return self.providers["ollama"]