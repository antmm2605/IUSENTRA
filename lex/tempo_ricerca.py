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


class PostoNonDisponibile(RuntimeError):
    """Tutti i posti dell'esecutore (o quelli dell'utente) sono occupati: la ricerca non parte."""


class EsecutoreLimitato:
    """Ricerche lente in un esecutore con posti contati e tempo massimo dentro il lavoro.

    La scadenza è aperta nel thread che lavora: le connessioni SQLite collegate con ``applica`` si interrompono
    quando scade, quindi il posto e la connessione si liberano davvero (non resta una ricerca in sfondo).
    Se non c'è un posto libero, complessivo o per utente, la ricerca non si accoda: ``PostoNonDisponibile``.
    """

    def __init__(self, nome: str, posti: int = 2, per_utente: int = 1):
        from concurrent.futures import ThreadPoolExecutor

        self._esecutore = ThreadPoolExecutor(max_workers=posti, thread_name_prefix=nome)
        self._posti = threading.BoundedSemaphore(posti)
        self._per_utente = max(1, per_utente)
        self._utenti: dict[str, int] = {}
        self._lock = threading.Lock()

    def occupati(self) -> int:
        with self._lock:
            return sum(self._utenti.values())

    def esegui(self, lavoro, *args, secondi: float, utente: str = "", **kwargs):
        """Avvia e attende: alla scadenza annulla e solleva ``RicercaTroppoLunga``."""
        return self.attendi(self.avvia(lavoro, *args, secondi=secondi, utente=utente, **kwargs), secondi)

    @staticmethod
    def attendi(futuro, secondi: float):
        from concurrent.futures import TimeoutError as Scaduto

        try:
            return futuro.result(timeout=secondi + 0.5)
        except Scaduto as exc:
            futuro.cancel()
            raise RicercaTroppoLunga(secondi) from exc

    def avvia(self, lavoro, *args, secondi: float, utente: str = "", **kwargs):
        """Avvia senza attendere (più archivi in parallelo); il tempo massimo vale dentro il lavoro."""
        if not self._posti.acquire(blocking=False):
            raise PostoNonDisponibile("nessun posto libero")
        with self._lock:
            if self._utenti.get(utente, 0) >= self._per_utente:
                self._posti.release()
                raise PostoNonDisponibile("ricerca già in corso per questo utente")
            self._utenti[utente] = self._utenti.get(utente, 0) + 1

        def libera():
            with self._lock:
                self._utenti[utente] -= 1
                if not self._utenti[utente]:
                    del self._utenti[utente]
            self._posti.release()

        def nel_worker():
            try:
                with scadenza(secondi), traduci_interruzione():
                    return lavoro(*args, **kwargs)
            finally:
                libera()

        try:
            futuro = self._esecutore.submit(nel_worker)
        except BaseException:
            libera()
            raise
        # Un lavoro annullato prima di partire non entra in nel_worker: il posto si libera qui.
        futuro.add_done_callback(lambda f: libera() if f.cancelled() else None)
        return futuro
