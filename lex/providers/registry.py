"""Scelta del provider applicativo per i workflow Lex."""

from __future__ import annotations

from .mock_provider import MockProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self.providers = {
            "mock": MockProvider(),
            "ollama": OllamaProvider(),
            "openai": OpenAIProvider(),
        }

    def pick(self, request, context, workflow, evidence):
        if workflow in {"telematico", "udienza", "atto", "fascicolo"}:
            return self.providers["ollama"]
        return self.providers["mock"]
