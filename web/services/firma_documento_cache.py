"""Esito del controllo di firma dei documenti del fascicolo, riusato finché il file non cambia.

Verifica del 31/10/2026 (V21): la scheda «Documenti» leggeva, decifrava e analizzava la firma di ogni
documento a ogni apertura (6,5-8 secondi con circa 30 documenti), anche senza nessuna modifica. È la
rilettura per abitudine che il registro delle letture vieta (art. 3 D.M. 44/2011, art. 20 CAD: integrità
del documento). La chiave è il file (percorso, data di modifica in nanosecondi, dimensione) e i nomi
mostrati: se il documento cambia, cambia la chiave e il controllo si rifà.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from typing import Any, Callable

_MASSIMO = 20000
_ESITI: "OrderedDict[tuple, dict[str, Any]]" = OrderedDict()
_LOCK = threading.Lock()


def chiave_file(percorso: str, nomi: tuple[str, ...]) -> tuple | None:
    try:
        stato = os.stat(percorso)
    except OSError:
        return None
    return (str(percorso), stato.st_mtime_ns, stato.st_size, nomi)


def esito_firma(percorso: str, nomi: tuple[str, ...], calcola: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """L'esito memorizzato per lo stesso file non modificato, altrimenti calcolato e memorizzato."""
    chiave = chiave_file(percorso, nomi)
    if chiave is None:
        return calcola()
    with _LOCK:
        trovato = _ESITI.get(chiave)
        if trovato is not None:
            _ESITI.move_to_end(chiave)
            return dict(trovato)
    esito = calcola()
    with _LOCK:
        _ESITI[chiave] = dict(esito)
        while len(_ESITI) > _MASSIMO:
            _ESITI.popitem(last=False)
    return esito


def svuota() -> None:
    with _LOCK:
        _ESITI.clear()


__all__ = ["chiave_file", "esito_firma", "svuota"]
