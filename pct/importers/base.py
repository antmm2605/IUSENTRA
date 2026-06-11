"""Modelli base del Migration Center (import multi-gestionale, tenant-aware).

Obiettivo prodotto: uno studio non cambia gestionale se teme di perdere
fascicoli, clienti, scadenze, fatture e storico. Questo motore importa da
sorgenti eterogenee in **staging** con anteprima/dry-run: nulla viene scritto sui
dati reali finché il commit non viene approvato esplicitamente (sink iniettato).

Principio delle fonti certe: l'import non inventa dati. Ogni record di staging
conserva il riferimento alla riga sorgente e un hash del contenuto; le entità
senza chiave naturale o con campi obbligatori mancanti restano "invalid" e non
vengono mai committate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class RecordKind(str, Enum):
    CLIENTE = "cliente"
    SOGGETTO = "soggetto"
    FASCICOLO = "fascicolo"
    SCADENZA = "scadenza"
    FATTURA = "fattura"
    DOCUMENTO = "documento"


class RecordStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str
    severity: str = "error"  # "error" | "warning"


def content_hash(kind: RecordKind | str, data: dict[str, Any]) -> str:
    """Hash deterministico del contenuto (per dedup e audit)."""

    kind_value = kind.value if isinstance(kind, RecordKind) else str(kind)
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{kind_value}|{canonical}".encode("utf-8")).hexdigest()


@dataclass
class StagedRecord:
    kind: RecordKind
    source_ref: str
    data: dict[str, Any]
    natural_key: str = ""
    content_sha256: str = ""
    status: RecordStatus = RecordStatus.VALID
    issues: list[ValidationIssue] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.content_sha256:
            self.content_sha256 = content_hash(self.kind, self.data)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    def to_public(self) -> dict[str, Any]:
        """Vista sicura per l'anteprima (nessun path, nessun segreto)."""

        return {
            "kind": self.kind.value,
            "sourceRef": self.source_ref,
            "naturalKey": self.natural_key,
            "contentSha256": self.content_sha256,
            "status": self.status.value,
            "issues": [{"field": i.field, "message": i.message, "severity": i.severity} for i in self.issues],
            "fields": dict(self.data),
        }


@runtime_checkable
class ImportAdapter(Protocol):
    name: str

    def parse(self, raw: bytes, *, kind: RecordKind, mapping: dict[str, str] | None = None) -> list[StagedRecord]:
        """Trasforma una sorgente grezza in record di staging (senza scrivere nulla)."""
        ...


class ImportError_(RuntimeError):
    """Errore controllato del Migration Center."""


__all__ = [
    "RecordKind",
    "RecordStatus",
    "ValidationIssue",
    "StagedRecord",
    "ImportAdapter",
    "ImportError_",
    "content_hash",
]
