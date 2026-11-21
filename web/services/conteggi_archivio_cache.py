"""Conteggi degli archivi di sentenze calcolati fuori dalla richiesta.

Contare 426.000 pronunce della Cassazione o raggruppare per fonte il corpus dello studio richiede la lettura di
gigabyte: con il disco occupato dall'acquisizione notturna si arrivava a 90-350 secondi e la pagina «Archivio
sentenze per corte» restava ferma su «Caricamento». Qui il conteggio si calcola in un thread separato, si conserva
in memoria e si rinnova quando il file dell'archivio cambia: la richiesta aspetta al massimo pochi istanti e,
se il dato non è ancora pronto, riceve l'ultimo valore noto oppure ``None`` (conteggio in corso, mai «zero»).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable

_LOCK = threading.Lock()
_CACHE: dict[str, dict[str, Any]] = {}
_IN_CORSO: dict[str, threading.Thread] = {}
_ERRORI: dict[str, BaseException] = {}
# Dopo questo tempo un conteggio si ricalcola comunque (l'archivio può cambiare senza variare mtime e dimensione).
DURATA_SECONDI = 900.0
ATTESA_SECONDI = 0.5


def _firma(percorso: str | os.PathLike[str] | None) -> tuple[Any, ...]:
    if not percorso:
        return ()
    firma: list[Any] = []
    for suffisso in ("", "-wal"):
        try:
            stato = os.stat(f"{percorso}{suffisso}")
        except OSError:
            firma.append(None)
        else:
            firma.append((stato.st_mtime_ns, stato.st_size))
    return tuple(firma)


def _calcola(chiave: str, firma: tuple[Any, ...], calcola: Callable[[], Any]) -> None:
    try:
        valore = calcola()
    except Exception as exc:  # l'errore torna al chiamante: un archivio illeggibile non è «conteggio in corso»
        with _LOCK:
            _ERRORI[chiave] = exc
            _IN_CORSO.pop(chiave, None)
        return
    with _LOCK:
        _CACHE[chiave] = {"valore": valore, "firma": firma, "quando": time.monotonic()}
        _ERRORI.pop(chiave, None)
        _IN_CORSO.pop(chiave, None)


def conteggio_memorizzato(chiave: str, percorso: str | os.PathLike[str] | None, calcola: Callable[[], Any], *,
                          durata: float | None = None, attesa: float | None = None) -> Any:
    """Valore di ``calcola()`` per ``chiave``; non blocca la richiesta oltre ``attesa`` secondi."""

    durata = DURATA_SECONDI if durata is None else durata
    attesa = ATTESA_SECONDI if attesa is None else attesa
    firma = _firma(percorso)
    with _LOCK:
        voce = _CACHE.get(chiave)
        if voce is not None and voce["firma"] == firma and time.monotonic() - voce["quando"] < durata:
            return voce["valore"]
        thread = _IN_CORSO.get(chiave)
        if thread is None or not thread.is_alive():
            thread = threading.Thread(target=_calcola, args=(chiave, firma, calcola),
                                      name=f"conteggio-archivio-{chiave[:40]}", daemon=True)
            _IN_CORSO[chiave] = thread
            thread.start()
    thread.join(attesa)
    with _LOCK:
        voce = _CACHE.get(chiave)
        if voce is not None:
            return voce["valore"]
        errore = None if thread.is_alive() else _ERRORI.pop(chiave, None)
    if errore is not None:
        raise errore
    return None


def svuota() -> None:
    """Solo per i test."""
    with _LOCK:
        _CACHE.clear()
        _IN_CORSO.clear()
        _ERRORI.clear()
