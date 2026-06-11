"""Area di staging del Migration Center: parse → valida → deduplica → riepilogo.

Tutto resta in memoria/staging: nessuna scrittura sui dati reali. È il cuore
dell'anteprima/dry-run che permette allo studio di vedere cosa entrerebbe prima
di approvare il commit.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from .base import RecordKind, RecordStatus, StagedRecord
from .dedup import mark_duplicates
from .registry import get_adapter
from .validators import apply_validation


@dataclass
class StagingArea:
    kind: RecordKind
    records: list[StagedRecord] = field(default_factory=list)

    def valid_records(self) -> list[StagedRecord]:
        return [r for r in self.records if r.status == RecordStatus.VALID]

    def invalid_records(self) -> list[StagedRecord]:
        return [r for r in self.records if r.status == RecordStatus.INVALID]

    def duplicate_records(self) -> list[StagedRecord]:
        return [r for r in self.records if r.status == RecordStatus.DUPLICATE]

    def summary(self) -> dict[str, Any]:
        by_status = Counter(r.status.value for r in self.records)
        return {
            "kind": self.kind.value,
            "total": len(self.records),
            "valid": by_status.get("valid", 0),
            "invalid": by_status.get("invalid", 0),
            "duplicate": by_status.get("duplicate", 0),
        }

    def preview(self, *, limit: int = 50) -> dict[str, Any]:
        """Anteprima sicura (nessun path, nessun segreto), limitata per UI."""

        return {
            "summary": self.summary(),
            "records": [r.to_public() for r in self.records[: max(0, limit)]],
            "truncated": len(self.records) > max(0, limit),
        }


def build_staging(
    adapter_name: str,
    raw: bytes,
    *,
    kind: RecordKind,
    mapping: dict[str, str] | None = None,
    existing_keys: Iterable[str] = (),
) -> StagingArea:
    """Costruisce lo staging completo: parse, validazione e deduplica."""

    adapter = get_adapter(adapter_name)
    records = adapter.parse(raw, kind=kind, mapping=mapping)
    apply_validation(records)
    mark_duplicates(records, existing_keys)
    # Dopo la deduplica i validi potrebbero essere diventati duplicati: rivalido
    # solo lo stato coerente senza riportare i duplicati a valid.
    return StagingArea(kind=kind, records=records)


__all__ = ["StagingArea", "build_staging"]
