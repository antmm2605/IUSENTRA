"""Rollback del Migration Center: ledger delle creazioni e piano di annullamento.

Ogni run che scrive registra le entità create; il rollback ne ricava il piano di
cancellazione (ordine inverso) ed è eseguibile tramite lo stesso sink. In dry-run
il ledger resta vuoto: non c'è nulla da annullare.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DeleteSink(Protocol):
    def delete(self, kind: str, record_id: str) -> bool:
        ...


@dataclass
class RollbackLedger:
    created: list[dict[str, str]] = field(default_factory=list)

    def record_created(self, kind: str, record_id: str) -> None:
        self.created.append({"kind": str(kind), "id": str(record_id)})

    def build_rollback_plan(self) -> list[dict[str, str]]:
        # Ordine inverso rispetto alla creazione (dipendenze).
        return list(reversed(self.created))

    def to_public(self) -> dict[str, Any]:
        return {"created": len(self.created), "rollbackAvailable": bool(self.created)}


def execute_rollback(ledger: RollbackLedger, sink: DeleteSink) -> dict[str, Any]:
    deleted = 0
    failed: list[dict[str, str]] = []
    for entry in ledger.build_rollback_plan():
        try:
            if sink.delete(entry["kind"], entry["id"]):
                deleted += 1
            else:
                failed.append(entry)
        except Exception:
            failed.append(entry)
    return {"deleted": deleted, "failed": failed, "complete": not failed}


__all__ = ["DeleteSink", "RollbackLedger", "execute_rollback"]
