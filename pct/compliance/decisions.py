"""Registro decisioni di conformità: append-only con hash-chain firmata.

Ogni decisione rilevante (waiver di conflitto, esito adeguata verifica, scelta
GDPR) è registrata in modo immutabile e verificabile: catena di hash che lega
ogni voce alla precedente, così una manomissione successiva è rilevabile.
Riusa le primitive probatorie già in uso nella pipeline OCR.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal_document_ingestion.evidence_hash import canonical_json, chain_hash


class ComplianceDecisionLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _last_hash(self) -> str:
        entries = self._entries()
        return str(entries[-1].get("chain_hash") or "") if entries else ""

    def record_decision(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        kind: str,                 # "conflict_waiver" | "kyc_outcome" | "gdpr" | ...
        subject_ref: str,          # cliente/pratica di riferimento
        decision: str,             # "approvato" | "rifiutato" | "rinviato" ...
        rationale: str,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        previous = self._last_hash()
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenant_id": str(tenant_id),
            "actor_id": str(actor_id),
            "kind": str(kind),
            "subject_ref": str(subject_ref),
            "decision": str(decision),
            "rationale": str(rationale),
            "evidence": dict(evidence or {}),
            "previous_hash": previous,
        }
        entry["chain_hash"] = chain_hash(previous, entry)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(entry) + "\n")
        return entry

    def list_decisions(self, *, tenant_id: str | None = None) -> list[dict[str, Any]]:
        entries = self._entries()
        if tenant_id is None:
            return entries
        return [e for e in entries if str(e.get("tenant_id")) == str(tenant_id)]

    def verify_chain(self) -> bool:
        """Ricalcola la catena: True se integra, False se manomessa/spezzata."""

        previous = ""
        for entry in self._entries():
            stored = str(entry.get("chain_hash") or "")
            recomputed = chain_hash(previous, {k: v for k, v in entry.items() if k != "chain_hash"})
            if stored != recomputed or str(entry.get("previous_hash") or "") != previous:
                return False
            previous = stored
        return True


__all__ = ["ComplianceDecisionLog"]
