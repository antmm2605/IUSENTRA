"""Contratto comune dei collettori del piano del giorno."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..clock import Clock, system_clock
from ..models import OperationalSignal, SourceCoverage


@dataclass(frozen=True)
class Budget:
    """Limiti di lavorazione: un arretrato grande si smaltisce in più run."""

    max_items_per_source: int = 500
    max_fascicoli: int = 60
    max_seconds: float = 60.0


@dataclass
class CollectorContext:
    """Dipendenze già costruite dal runtime tenant-aware.

    I collettori restano puri rispetto a Flask: ricevono store di dominio e
    provider come dipendenze, mai path o configurazioni globali.
    """

    tenant_id: str
    clock: Clock = field(default_factory=system_clock)
    planning_date: date | None = None
    budget: Budget = field(default_factory=Budget)
    agenda_store: Any = None
    scadenziario_store: Any = None
    fascicoli_store: Any = None
    pec_repository: Any = None
    preventivi_store: Any = None
    fatturazione_store: Any = None
    # provider che restituisce, per ogni fascicolo, le azioni di presidio già
    # calcolate: iterable di dict {"fascicolo": {...}, "actions": [...]}
    presidio_provider: Callable[[CollectorContext], Iterable[dict[str, Any]]] | None = None
    watermarks: dict[str, dict[str, Any]] = field(default_factory=dict)
    # None = scansione completa; set di fascicolo_id = refresh incrementale
    dirty_fascicoli: set[str] | None = None


@dataclass
class CollectorResult:
    source_type: str
    signals: list[OperationalSignal] = field(default_factory=list)
    coverage: SourceCoverage | None = None
    fixed_agenda: list[dict[str, Any]] = field(default_factory=list)
    watermark: str = ""
    truncated: bool = False


def unavailable_result(source_type: str, note: str) -> CollectorResult:
    """Esito degradato: la fonte non è raggiungibile, il piano lo dichiara."""
    return CollectorResult(
        source_type=source_type,
        coverage=SourceCoverage(source_type=source_type, status="unavailable", note=note),
    )


__all__ = ["Budget", "CollectorContext", "CollectorResult", "unavailable_result"]
