"""Provider hosted placeholder del bounded context Lex."""

from __future__ import annotations

from .base import BaseProvider
from lex.contracts import ProviderDraft


class OpenAIProvider(BaseProvider):
    provider_name = "openai"

    def generate(self, request, context, evidence, workflow):
        return ProviderDraft(
            text=f"Provider cloud placeholder per '{workflow}'",
            metadata={"provider": self.provider_name},
        )
