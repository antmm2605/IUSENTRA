"""Uso del semaforo: ``with motore_pesante("ocr", priorita=...)`` aspetta il proprio turno e rinnova l'affitto."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from pct.semaforo_motori.archivio import Semaforo

logger = logging.getLogger(__name__)

# Prima ciò che serve all'avvocato ora (documento caricato, PEC appena arrivata), poi la sequenza logica.
PRIORITA_URGENTE = 10
PRIORITA_SEQUENZA = 50  # + numero della fase notturna, per rispettarne l'ordine
PRIORITA_DIFFERIBILE = 90

_CACHE: dict[str, Semaforo] = {}
# Chi è già nel proprio turno (stesso thread) non rientra in coda: eviterebbe di aspettare sé stesso.
_IN_TURNO = threading.local()
_CACHE_LOCK = threading.Lock()


def _percorso() -> str:
    esplicito = str(os.getenv("PCT_SEMAFORO_DB", "")).strip()
    if esplicito:
        return esplicito
    radice = str(os.getenv("PCT_DATA_ROOT", "")).strip()
    return str(Path(radice) / "intelligence" / "semaforo_motori.sqlite") if radice else ""


def semaforo_predefinito() -> Semaforo | None:
    """Il semaforo condiviso del server; None se spento (PCT_SEMAFORO_MOTORI=0) o senza cartella dati."""
    if str(os.getenv("PCT_SEMAFORO_MOTORI", "1")).strip().lower() in {"0", "false", "no", "off"}:
        return None
    percorso = _percorso()
    if not percorso:
        return None
    with _CACHE_LOCK:
        if percorso not in _CACHE:
            _CACHE[percorso] = Semaforo(percorso)
        return _CACHE[percorso]


class SemaforoOccupato(TimeoutError):
    """Il turno non è arrivato entro l'attesa massima."""


@contextmanager
def motore_pesante(nome: str, *, priorita: int = PRIORITA_SEQUENZA, attesa_massima: float | None = None,
                   semaforo: Semaforo | None = None, intervallo: float = 2.0) -> Iterator[bool]:
    """Esegue il blocco quando è il proprio turno. Se il semaforo non è disponibile si lavora comunque (fail-open)."""
    sem = semaforo or semaforo_predefinito()
    if sem is None or getattr(_IN_TURNO, "attivo", False):
        yield False
        return
    titolare = f"{nome}:{uuid.uuid4().hex[:12]}"
    inizio = time.monotonic()
    try:
        while not sem.prova(titolare, nome, priorita):
            if attesa_massima is not None and time.monotonic() - inizio >= attesa_massima:
                raise SemaforoOccupato(f"{nome}: turno non arrivato entro {int(attesa_massima)} secondi.")
            time.sleep(intervallo)
    except SemaforoOccupato:
        sem.rilascia(titolare)
        raise
    except Exception as exc:  # archivio non leggibile: non si ferma il lavoro
        logger.warning("[semaforo] Non disponibile per %s: %s", nome, type(exc).__name__)
        yield False
        return
    fermo = threading.Event()

    def _rinnova() -> None:
        while not fermo.wait(max(5.0, sem.affitto / 4)):
            try:
                sem.rinnova(titolare)
            except Exception:
                pass

    rinnovo = threading.Thread(target=_rinnova, name=f"semaforo-{nome}", daemon=True)
    rinnovo.start()
    _IN_TURNO.attivo = True
    try:
        yield True
    finally:
        _IN_TURNO.attivo = False
        fermo.set()
        try:
            sem.rilascia(titolare)
        except Exception:
            logger.warning("[semaforo] Rilascio non riuscito per %s: scadrà con l'affitto.", nome)


def in_turno(nome: str, funzione, *, priorita: int = PRIORITA_URGENTE):
    """Avvolge il corpo di un thread in sfondo perché lavori solo al proprio turno del semaforo."""

    def avvolto(*args, **kwargs):
        with motore_pesante(nome, priorita=priorita):
            return funzione(*args, **kwargs)

    return avvolto
