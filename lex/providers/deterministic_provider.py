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


def _economic_text(question: str, title: str, summary: str) -> str:
    haystack = str(question or "").strip().lower()
    context_line = f"Contesto utile: {title}." if title else ""
    if "preventiv" in haystack:
        lines = [
            "Possiamo partire dal preventivo guidato.",
            context_line,
            "Per chiuderlo bene mi servono questi dati essenziali:",
            "- tipo di pratica o obiettivo dell'incarico;",
            "- cliente gia' censito oppure anagrafica rapida minima;",
            "- valore o scaglione, se la pratica lo richiede;",
            "- fase o attivita' da includere nel compenso;",
            "- eventuali anticipazioni, urgenze o canale online/studio.",
        ]
        if summary and summary != "Nessuna evidenza disponibile.":
            lines.append(f"Dato che ho gia': {summary}")
        lines.append("Se vuoi, dimmi subito oggetto della pratica e tipo di attivita': ti porto sul percorso corretto del preventivo.")
        return "\n".join(line for line in lines if line)
    if "tariffario" in haystack or any(token in haystack for token in ("onorario", "compenso", "scaglione")):
        lines = [
            "Per questa richiesta conviene partire dal tariffario, non da una risposta generica.",
            context_line,
            "Dimmi questi dati e ti do il percorso giusto:",
            "- natura della pratica;",
            "- valore o scaglione, se presente;",
            "- fase o attivita' da parametrizzare;",
            "- eventuale regime fiscale o compenso unico.",
        ]
        if summary and summary != "Nessuna evidenza disponibile.":
            lines.append(f"Riferimento economico disponibile: {summary}")
        lines.append("Appena li ho, posso distinguere tra calcolo tariffario, bozza preventivo o parcella.")
        return "\n".join(line for line in lines if line)
    if any(token in haystack for token in ("fattura", "parcella", "parcelle", "pagamento", "incasso", "saldo")):
        lines = [
            "Qui stiamo parlando di fatturazione o incasso, quindi il punto e' capire in quale stato economico sei.",
            context_line,
            "Verifica con me questi dati:",
            "- preventivo o conferimento di origine;",
            "- imponibile e anticipazioni;",
            "- stato fattura o parcella;",
            "- incasso atteso o gia' registrato.",
        ]
        if summary and summary != "Nessuna evidenza disponibile.":
            lines.append(f"Contesto economico disponibile: {summary}")
        lines.append("Se mi dai il riferimento economico o il cliente, ti dico subito il passo corretto.")
        return "\n".join(line for line in lines if line)
    return (
        "Percorso economico individuato.\n"
        f"{context_line}\n"
        f"Sintesi utile: {summary}\n"
        "Dimmi se vuoi lavorare su preventivo, tariffario, parcella o pagamento e ti porto sul flusso giusto."
    ).strip()


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
            text = _economic_text(q, title, summary)
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
