"""Ricordo, per processo, degli schemi SQLite già preparati.

Alcuni archivi eseguono ``CREATE TABLE IF NOT EXISTS`` (e lo script completo dello
schema) a ogni costruzione dell'oggetto, cioè a ogni richiesta: è una scrittura con
commit anche quando non cambia nulla. Nel collaudo del 21/11/2026 la pagina
«Cerca norme e sentenze» ne pagava 2 s a vuoto e, con lo scheduler al lavoro, molto
di più per l'attesa dei lock. Lo schema si riprepara se il file è stato sostituito
(identità diversa) o non esiste più.
"""
from __future__ import annotations

import threading
from pathlib import Path

_PREPARATI: set[tuple] = set()
_LOCK = threading.Lock()


def _identita(percorso: str | Path, schema: str) -> tuple | None:
    try:
        stato = Path(percorso).resolve().stat()
    except OSError:
        return None
    return (str(Path(percorso).resolve()), stato.st_dev, stato.st_ino, schema)


def gia_preparato(percorso: str | Path, schema: str = "") -> bool:
    chiave = _identita(percorso, schema)
    with _LOCK:
        return chiave is not None and chiave in _PREPARATI


def segna_preparato(percorso: str | Path, schema: str = "") -> None:
    chiave = _identita(percorso, schema)
    if chiave is not None:
        with _LOCK:
            _PREPARATI.add(chiave)
