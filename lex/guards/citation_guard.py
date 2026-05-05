"""Guardia citazioni per Lex."""

from __future__ import annotations

from typing import Any

from lex.contracts import GuardVerdict, answer_contract_for


def _evidence_rows(evidence: Any) -> tuple[list[Any], list[Any]]:
    if isinstance(evidence, dict):
        return list(evidence.get("items") or []), list(evidence.get("citations") or [])
    return list(getattr(evidence, "items", []) or []), list(getattr(evidence, "citations", []) or [])


def _requires_governed_citations(request: Any, workflow: str, contract) -> bool:
    return bool(
        contract.require_citations
        or contract.require_official_sources
        or getattr(request, "require_citations", False)
        or getattr(request, "require_official_sources", False)
    )


class CitationGuard:
    def check(self, **kwargs):
        request = kwargs.get("request")
        workflow = str(kwargs.get("workflow") or "chat")
        contract = answer_contract_for(workflow)  # type: ignore[arg-type]
        evidence = kwargs.get("evidence") or {}
        items, citations = _evidence_rows(evidence)
        requires_sources = _requires_governed_citations(request, workflow, contract)

        if requires_sources and not items and not citations:
            return GuardVerdict(
                allowed=False,
                warnings=["Mancano evidenze o citazioni per il workflow governato richiesto."],
                reasons=["Il contratto della risposta richiede fonti/citazioni, ma il pacchetto evidenze e' vuoto."],
                risk_level="high",
            )

        if bool(getattr(request, "require_citations", False) or getattr(request, "require_official_sources", False)) and not items:
            return GuardVerdict(
                allowed=False,
                warnings=["La richiesta impone fonti governate, ma non ci sono evidenze disponibili."],
                reasons=["require_citations/require_official_sources attivo senza EvidenceItem."],
                risk_level="high",
            )

        if not items:
            return GuardVerdict(
                allowed=True,
                warnings=["Nessuna evidenza trovata: risposta da limitare o rendere prudente."],
                risk_level="medium",
            )
        if requires_sources and not citations:
            return GuardVerdict(
                allowed=True,
                warnings=["Evidenze presenti ma citazioni non ancora strutturate: risposta da mantenere prudente."],
                reasons=["Il workflow richiede fonti/citazioni e dispone solo del pacchetto evidenze."],
                risk_level="medium",
            )
        return GuardVerdict(allowed=True)
