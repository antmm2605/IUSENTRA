"""Migration Center — import multi-gestionale tenant-aware (anteprima/dry-run).

Flusso: adapter.parse → staging (valida + deduplica) → commit plan (dry-run) →
commit reale solo con sink iniettato → rollback via ledger.
"""

from .base import (
    ImportAdapter,
    ImportError_,
    RecordKind,
    RecordStatus,
    StagedRecord,
    ValidationIssue,
    content_hash,
)
from .commit import CommitPlan, CommitResult, RecordSink, build_commit_plan, execute_commit
from .registry import available_adapters, get_adapter, register_adapter
from .rollback import DeleteSink, RollbackLedger, execute_rollback
from .staging import StagingArea, build_staging

__all__ = [
    "RecordKind",
    "RecordStatus",
    "StagedRecord",
    "ValidationIssue",
    "ImportAdapter",
    "ImportError_",
    "content_hash",
    "build_staging",
    "StagingArea",
    "build_commit_plan",
    "execute_commit",
    "CommitPlan",
    "CommitResult",
    "RecordSink",
    "RollbackLedger",
    "DeleteSink",
    "execute_rollback",
    "register_adapter",
    "get_adapter",
    "available_adapters",
]
