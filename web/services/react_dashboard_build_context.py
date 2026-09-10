"""Contesto di una singola costruzione della Panoramica React.

Durante il calcolo del quadro operativo gli stessi archivi dello studio
(agenda, scadenziario, fascicoli, clienti, fatturazione, preventivi, caselle)
venivano riaperti più volte: ogni ``get_*()`` costruisce un gestore che rilegge
l'archivio. Qui ogni gestore viene aperto una sola volta per costruzione e i
tempi delle sorgenti vengono misurati, così una Panoramica lenta dichiara quale
archivio la rallenta invece di restare un mistero.

Fuori da ``contesto_costruzione_panoramica()`` le funzioni sono trasparenti:
``gestore_panoramica(factory)`` chiama semplicemente ``factory()``.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Iterator, TypeVar

T = TypeVar("T")

# Soglia oltre la quale il log applicativo registra il dettaglio dei tempi.
SOGLIA_LOG_SECONDI = 3.0


@dataclass
class CostruzionePanoramica:
    gestori: dict[Any, Any] = field(default_factory=dict)
    tempi: dict[str, float] = field(default_factory=dict)
    avvio: float = field(default_factory=perf_counter)

    def durata(self) -> float:
        return perf_counter() - self.avvio

    def riepilogo(self) -> dict[str, Any]:
        sorgenti = {label: round(seconds, 3) for label, seconds in sorted(self.tempi.items(), key=lambda item: -item[1])}
        return {"seconds": round(self.durata(), 3), "sources": sorgenti}


_COSTRUZIONE: ContextVar[CostruzionePanoramica | None] = ContextVar("_COSTRUZIONE_PANORAMICA", default=None)


@contextmanager
def contesto_costruzione_panoramica() -> Iterator[CostruzionePanoramica]:
    """Attiva memoizzazione dei gestori e misura dei tempi per il blocco corrente."""

    costruzione = CostruzionePanoramica()
    token = _COSTRUZIONE.set(costruzione)
    try:
        yield costruzione
    finally:
        _COSTRUZIONE.reset(token)


def gestore_panoramica(factory: Callable[[], T]) -> T:
    """Apre il gestore una sola volta per costruzione; trasparente fuori contesto."""

    costruzione = _COSTRUZIONE.get()
    if costruzione is None:
        return factory()
    if factory not in costruzione.gestori:
        costruzione.gestori[factory] = factory()
    return costruzione.gestori[factory]


def fabbrica_panoramica(factory: Callable[[], T]) -> Callable[[], T]:
    """Versione memoizzata di una factory da passare ai bridge (``get_x=...``)."""

    return lambda: gestore_panoramica(factory)


def misura_sorgente(label: str, func: Callable[[], T]) -> T:
    """Esegue ``func`` sommando il tempo impiegato sotto ``label``."""

    costruzione = _COSTRUZIONE.get()
    if costruzione is None:
        return func()
    start = perf_counter()
    try:
        return func()
    finally:
        costruzione.tempi[label] = costruzione.tempi.get(label, 0.0) + (perf_counter() - start)


def server_timing_header(riepilogo: dict[str, Any] | None) -> str:
    """Header ``Server-Timing`` leggibile negli strumenti del browser."""

    if not isinstance(riepilogo, dict):
        return ""
    parts = [f"panoramica;dur={float(riepilogo.get('seconds') or 0.0) * 1000:.0f}"]
    for label, seconds in list((riepilogo.get("sources") or {}).items())[:12]:
        safe_label = "".join(char if char.isalnum() or char in "_-" else "_" for char in str(label))[:40] or "sorgente"
        parts.append(f"{safe_label};dur={float(seconds or 0.0) * 1000:.0f}")
    return ", ".join(parts)
