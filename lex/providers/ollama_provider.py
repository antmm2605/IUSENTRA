"""Provider applicativo Ollama posseduto da Lex."""

from __future__ import annotations

from .base import BaseProvider
from lex.contracts import ProviderDraft


class OllamaProvider(BaseProvider):
    provider_name = "ollama"

    def generate(self, request, context, evidence, workflow):
        items = list((evidence or {}).get("items") or [])
        context_text = "\n".join(item.content for item in items[:5]).strip()
        if not context_text:
            context_text = "Nessuna evidenza disponibile."
        text = (
            f"Risposta generata da Ollama per workflow '{workflow}'.\n\n"
            f"Domanda: {request.query}\n\n"
            f"Contesto:\n{context_text}"
        )
        return ProviderDraft(text=text, metadata={"provider": self.provider_name})
