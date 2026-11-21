"""Tempo massimo delle ricerche nelle fonti.

Una ricerca che scorre un archivio intero non deve tenere occupato un thread
del server per minuti: con un solo worker e quattro thread, quattro ricerche
lente bastano a fermare tutto il programma (collaudo del 21/11/2026, 8080
fermo dalle 09:33 alle 10:23).

Il limite vale per thread. La richiesta HTTP lo apre con ``scadenza`` e ogni
connessione SQLite delle fonti lo applica con ``applica``: SQLite controlla
il tempo durante l'esecuzione e interrompe la query appena scade. Chi gestisce
la richiesta riceve ``RicercaTroppoLunga`` con un messaggio da mostrare
all'avvocato così com'è.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager

_STATO = threading.local()
# Ogni quante istruzioni della macchina virtuale SQLite si controlla il tempo.
_PASSO = 20_000


def secondi_predefiniti() -> float:
    try:
        valore = float(os.getenv("IUSENTRA_TEMPO_MASSIMO_RICERCA", "20"))
    except ValueError:
        valore = 20.0
    return max(1.0, min(valore, 110.0))


class RicercaTroppoLunga(RuntimeError):
    # Non deriva da OSError/TimeoutError: i gestori «archivio non disponibile» non devono inghiottirla.
    """La ricerca ha superato il tempo massimo ed è stata interrotta."""

    def __init__(self, secondi: float | None = None, messaggio: str | None = None):
        secondi = round(secondi or secondi_predefiniti())
        super().__init__(messaggio or (
            f"La ricerca ha superato il tempo massimo di {secondi} secondi ed è stata interrotta. "
            "Restringi la ricerca: scegli il codice o la legge, oppure indica il numero dell’articolo."
        ))
        self.secondi = secondi


def scadenza_attiva() -> float | None:
    return getattr(_STATO, "fine", None)


@contextmanager
def scadenza(secondi: float | None = None):
    """Apre il tempo massimo per il thread corrente (annidabile: vale il più stretto)."""
    secondi = secondi_predefiniti() if secondi is None else float(secondi)
    precedente = scadenza_attiva()
    precedenti_secondi = getattr(_STATO, "secondi", None)
    fine = time.monotonic() + secondi
    _STATO.fine = fine if precedente is None else min(precedente, fine)
    _STATO.secondi = secondi if precedente is None or fine < precedente else precedenti_secondi
    try:
        yield
    finally:
        _STATO.fine = precedente
        _STATO.secondi = precedenti_secondi
        if precedente is None:
            _ferma_timer()


def scaduta() -> bool:
    fine = scadenza_attiva()
    return fine is not None and time.monotonic() > fine


def controlla() -> None:
    """Punto di controllo per i cicli in Python (fuori da SQLite)."""
    if scaduta():
        raise RicercaTroppoLunga(getattr(_STATO, "secondi", None))


def applica(connessione: sqlite3.Connection) -> sqlite3.Connection:
    """Collega la connessione al tempo massimo del thread che la usa.

    Il gestore di avanzamento non basta da solo: dentro una MATCH FTS5 o in
    attesa del disco SQLite esegue poche istruzioni e il controllo arriva tardi
    (116 s invece di 30 nel collaudo). Un timer chiama anche ``interrupt()``
    alla scadenza, che SQLite rispetta in ogni punto.
    """
    connessione.set_progress_handler(lambda: 1 if scaduta() else 0, _PASSO)
    fine = scadenza_attiva()
    if fine is not None:
        def interrompi():
            try:
                connessione.interrupt()
            except sqlite3.ProgrammingError:  # connessione già chiusa: niente da interrompere
                pass
        timer = threading.Timer(max(0.0, fine - time.monotonic()), interrompi)
        timer.daemon = True
        timer.start()
        _timer_attivi().append(timer)
    return connessione


def _timer_attivi() -> list:
    timer = getattr(_STATO, "timer", None)
    if timer is None:
        timer = _STATO.timer = []
    return timer


def _ferma_timer() -> None:
    for timer in _timer_attivi():
        timer.cancel()
    _STATO.timer = []


def interrotta(errore: BaseException) -> bool:
    return isinstance(errore, sqlite3.OperationalError) and "interrupt" in str(errore).lower()


@contextmanager
def traduci_interruzione():
    """Trasforma l'interruzione di SQLite nell'errore chiaro per l'avvocato."""
    try:
        yield
    except sqlite3.OperationalError as errore:
        if interrotta(errore) and scaduta():
            raise RicercaTroppoLunga(getattr(_STATO, "secondi", None)) from errore
        raise


def apri_per_richiesta(secondi: float | None = None) -> None:
    """Per gli hook di Flask (before_request): il limite vale fino a ``chiudi_per_richiesta``."""
    _STATO.fine = time.monotonic() + (secondi_predefiniti() if secondi is None else float(secondi))
    _STATO.secondi = secondi_predefiniti() if secondi is None else float(secondi)


def chiudi_per_richiesta() -> None:
    _ferma_timer()
    _STATO.fine = None
    _STATO.secondi = None
