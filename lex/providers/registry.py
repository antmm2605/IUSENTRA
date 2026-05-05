from __future__ import annotations

import os

from .deterministic_provider import DeterministicProvider
from .mock_provider import MockProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from lex.contracts import answer_contract_for


_DETERMINISTIC_WORKFLOWS = {"economico", "next_action", "cabina", "telematico_status", "compliance"}
_STRICT_LEGAL_WORKFLOWS = {"normativa", "giurisprudenza", "prassi", "research", "fonti"}


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
        if forced == "mock" and (os.getenv("LEX_PROVIDER_FORCE_MOCK", "").strip() == "1" or os.getenv("PYTEST_CURRENT_TEST")):
            return self.providers[forced]
        if forced in {"ollama", "deterministic"} and forced in self.providers:
            return self.providers[forced]
        if forced == "openai" and _external_provider_allowed():
            return self.providers["openai"]

        if os.getenv("LEX_PROVIDER_FORCE_MOCK", "").strip() == "1":
            return self.providers["mock"]

        if workflow in _DETERMINISTIC_WORKFLOWS:
            return self.providers["deterministic"]

        contract = answer_contract_for(workflow)
        if contract.provider_hint and contract.provider_hint in self.providers:
            return self.providers[contract.provider_hint]

        if workflow == "fascicolo" and _has_fascicolo_context(context):
            return self.providers["deterministic"]

        if workflow in _STRICT_LEGAL_WORKFLOWS:
            return self.providers["ollama"]

        if workflow in {"telematico", "udienza", "atto", "documento", "question_answering", "intelligence"}:
            return self.providers["ollama"]

        if workflow == "fascicolo":
            return self.providers["deterministic"]

        return self.providers["ollama"]


def _external_provider_allowed() -> bool:
    return os.getenv("LEX_EXTERNAL_ALLOWED", "").strip().lower() in {"1", "true", "yes", "si", "on"}
