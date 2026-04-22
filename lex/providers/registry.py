from __future__ import annotations

import os

from .deterministic_provider import DeterministicProvider
from .mock_provider import MockProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from lex.contracts import answer_contract_for


def _has_fascicolo_context(context) -> bool:
    if not isinstance(context, dict):
        return False
    structured = context.get("structured_context") or {}
    if isinstance(structured, dict) and structured.get("fascicolo"):
        return True
    return bool(context.get("fascicolo"))


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

        if workflow == "fascicolo" and _has_fascicolo_context(context):
            return self.providers["deterministic"]

        if workflow in {
            "telematico",
            "udienza",
            "atto",
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

        if workflow == "fascicolo":
            return self.providers["deterministic"]

        return self.providers["ollama"]
