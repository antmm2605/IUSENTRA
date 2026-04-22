from __future__ import annotations

from typing import Any

from .base import BaseProvider
from lex.contracts import ProviderDraft


def _as_items(evidence: Any) -> list[Any]:
    if isinstance(evidence, dict):
        return list(evidence.get("items") or [])
    return list(getattr(evidence, "items", None) or [])


def _shorten(value: str, limit: int = 220) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


class DeterministicProvider(BaseProvider):
    provider_name = "deterministic"

    def generate(self, request, context, evidence, workflow):
        items = _as_items(evidence)
        preview = items[0] if items else None
        title = getattr(preview, "title", "") if preview is not None else ""
        content = getattr(preview, "content", "") if preview is not None else ""
        summary = _shorten(content or "Nessuna evidenza disponibile.")
        q = str(getattr(request, "query", "") or "").strip()

        if workflow in {"next_action", "cabina"}:
            text = (
                "Quadro operativo sintetico\n"
                f"- Richiesta: {q or 'non specificata'}\n"
                f"- Evidenza principale: {title or 'non disponibile'}\n"
                f"- Sintesi: {summary}\n"
                "- Azione suggerita: aprire il modulo contestuale e verificare le criticita prima di proseguire."
            )
        elif workflow in {"economico"}:
            text = (
                "Esito economico governato\n"
                f"- Richiesta: {q or 'non specificata'}\n"
                f"- Dato principale: {title or 'non disponibile'}\n"
                f"- Sintesi utilizzata: {summary}\n"
                "- Azione suggerita: validare i dati in preventivi/tariffario/fatture prima della conferma finale."
            )
        elif workflow in {"telematico_status", "compliance"}:
            text = (
                "Esito operativo governato\n"
                f"- Richiesta: {q or 'non specificata'}\n"
                f"- Evidenza principale: {title or 'non disponibile'}\n"
                f"- Osservazione: {summary}\n"
                "- Azione suggerita: eseguire il controllo tecnico o la verifica del fascicolo prima del passo successivo."
            )
        else:
            text = (
                f"Risposta deterministica per workflow '{workflow}'.\n"
                f"Evidenza principale: {title or 'non disponibile'}\n"
                f"Sintesi: {summary}"
            )

        return ProviderDraft(
            text=text,
            metadata={
                "provider": self.provider_name,
                "workflow": workflow,
                "evidence_count": len(items),
                "mode": "fast-path",
            },
        )
