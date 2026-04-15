"""Provider deterministico per test e fallback del bounded context Lex."""

from __future__ import annotations

from .base import BaseProvider
from lex.contracts import ProviderDraft


class MockProvider(BaseProvider):
    provider_name = "mock"

    def generate(self, request, context, evidence, workflow):
        items = list((evidence or {}).get("items") or [])
        preview = items[0].content if items else "Nessuna evidenza disponibile."
        return ProviderDraft(
            text=f"Bozza Lex per workflow '{workflow}'. Evidenza principale: {preview}",
            metadata={"provider": self.provider_name},
        )
