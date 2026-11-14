"""Uso del semaforo: ``with motore_pesante("ocr", priorita=...)`` aspetta il proprio turno e rinnova l'affitto."""

from __future__ import annotations

import logging
import os
import sqlite3
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


class SemaforoNonDisponibile(SemaforoOccupato):
    """L'archivio del semaforo non è tornato disponibile entro l'attesa."""


@contextmanager
def motore_pesante(nome: str, *, priorita: int = PRIORITA_SEQUENZA, attesa_massima: float | None = None,
                   semaforo: Semaforo | None = None, intervallo: float = 2.0) -> Iterator[bool]:
    """Esegue il blocco con il turno confermato dal semaforo, se configurato."""
    if getattr(_IN_TURNO, "attivo", False):
        yield False
        return
    sem = semaforo
    titolare = f"{nome}:{uuid.uuid4().hex[:12]}"
    inizio = time.monotonic()
    prossimo_log = inizio
    while True:
        errore_archivio = None
        try:
            if sem is None:
                sem = semaforo_predefinito()
            if sem is not None and sem.prova(titolare, nome, priorita):
                break
        except (OSError, sqlite3.Error) as exc:
            errore_archivio = exc
            if time.monotonic() >= prossimo_log:
                logger.warning("[semaforo] Attesa archivio per %s: %s", nome, type(exc).__name__)
                prossimo_log = time.monotonic() + 60
        if sem is None and errore_archivio is None:
            yield False
            return
        trascorso = time.monotonic() - inizio
        if attesa_massima is not None and trascorso >= attesa_massima:
            try:
                if sem is not None:
                    sem.rilascia(titolare)
            except (OSError, sqlite3.Error):
                logger.warning("[semaforo] Prenotazione di %s in scadenza naturale.", nome)
            if errore_archivio is not None:
                raise SemaforoNonDisponibile(f"{nome}: archivio del semaforo indisponibile.") from errore_archivio
            raise SemaforoOccupato(f"{nome}: turno non arrivato entro {int(attesa_massima)} secondi.")
        residuo = attesa_massima - trascorso if attesa_massima is not None else intervallo
        time.sleep(min(intervallo, residuo))
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
