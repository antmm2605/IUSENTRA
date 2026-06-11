"""Piano di commit del Migration Center.

Default SICURO: dry-run. Il piano elenca cosa verrebbe creato e cosa saltato (con
motivo), senza scrivere nulla. La scrittura reale avviene solo passando un
``RecordSink`` esplicito e ``dry_run=False``: in questa fase nessun sink reale è
collegato ai repository, così l'import resta in sola anteprima finché non si
approva. Ogni creazione viene annotata nel RollbackLedger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .base import ImportError_, RecordStatus, StagedRecord
from .rollback import RollbackLedger
from .staging import StagingArea


@runtime_checkable
class RecordSink(Protocol):
    """Scrittore reale verso i repository (iniettato; tenant-aware lato chiamante)."""

    def create(self, record: StagedRecord) -> str:
        """Crea il record e ritorna l'id creato."""
        ...


@dataclass
class CommitPlan:
    creates: list[StagedRecord] = field(default_factory=list)
    skips: list[tuple[StagedRecord, str]] = field(default_factory=list)

    def to_public(self) -> dict[str, Any]:
        return {
            "willCreate": len(self.creates),
            "willSkip": len(self.skips),
            "skipReasons": _count_reasons(self.skips),
            "creates": [r.to_public() for r in self.creates[:50]],
        }


@dataclass
class CommitResult:
    dry_run: bool
    plan: CommitPlan
    created_ids: list[dict[str, str]] = field(default_factory=list)
    ledger: RollbackLedger | None = None

    def to_public(self) -> dict[str, Any]:
        return {
            "dryRun": self.dry_run,
            "plan": self.plan.to_public(),
            "created": len(self.created_ids),
        }


def _count_reasons(skips: list[tuple[StagedRecord, str]]) -> dict[str, int]:
    reasons: dict[str, int] = {}
    for _, reason in skips:
        reasons[reason] = reasons.get(reason, 0) + 1
    return reasons


def build_commit_plan(staging: StagingArea) -> CommitPlan:
    plan = CommitPlan()
    for record in staging.records:
        if record.status == RecordStatus.VALID:
            plan.creates.append(record)
        elif record.status == RecordStatus.DUPLICATE:
            plan.skips.append((record, "duplicate"))
        else:
            plan.skips.append((record, "invalid"))
    return plan


def execute_commit(staging: StagingArea, sink: RecordSink | None = None, *, dry_run: bool = True) -> CommitResult:
    """Esegue (o simula) il commit.

    - ``dry_run=True`` (default) o ``sink`` assente → solo piano, nessuna scrittura.
    - ``dry_run=False`` con ``sink`` → crea i record validi e annota il rollback.
    """

    plan = build_commit_plan(staging)
    if dry_run or sink is None:
        return CommitResult(dry_run=True, plan=plan)

    if not isinstance(sink, RecordSink):
        raise ImportError_("Sink di commit non valido: serve un RecordSink con metodo create().")

    ledger = RollbackLedger()
    created_ids: list[dict[str, str]] = []
    for record in plan.creates:
        new_id = str(sink.create(record))
        ledger.record_created(record.kind.value, new_id)
        created_ids.append({"kind": record.kind.value, "id": new_id})
    return CommitResult(dry_run=False, plan=plan, created_ids=created_ids, ledger=ledger)


__all__ = ["RecordSink", "CommitPlan", "CommitResult", "build_commit_plan", "execute_commit"]
