"""Fatti dell'archivio precaricati per una richiesta che scorre molti fascicoli.

L'elenco dei fascicoli costruisce una riga per fascicolo e ogni riga chiede
all'archivio delle letture gli importi e le esenzioni del proprio fascicolo:
con 300 fascicoli erano 600 interrogazioni, ognuna con l'apertura del
registro. Qui si legge una volta sola, per tutti i fascicoli e le categorie
dichiarate, e `fatti_fascicolo` risponde dalla memoria della richiesta.

La memoria vive solo dentro il blocco `precaricati(...)`: fuori da lì ogni
chiamata torna a leggere l'archivio, così una scrittura successiva non può
essere nascosta da un dato vecchio. Se la lettura cumulativa fallisce si
torna alle letture per fascicolo, con lo stesso esito di prima.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

from flask import g, has_request_context

logger = logging.getLogger(__name__)
_CHIAVE = "_archivio_fatti_precaricati"


def _testo(valore: Any) -> str:
    return str(valore or "").strip()


@contextmanager
def precaricati(fascicoli: Iterable[Any], categorie: Iterable[str]) -> Iterator[None]:
    """Dentro il blocco, i fatti delle categorie indicate arrivano dalla lettura cumulativa."""
    if not has_request_context():
        yield
        return
    precedente = getattr(g, _CHIAVE, None)
    try:
        from pct.archivio_letture import fatti_canonici
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        ids = [_testo(getattr(f, "id", "")) for f in fascicoli]
        grezzi = registro_corrente().fatti_per_fascicoli(tenant_corrente(), ids, categorie)
        setattr(g, _CHIAVE, {chiave: fatti_canonici(fatti) for chiave, fatti in grezzi.items()})
    except Exception:
        logger.warning("Precarico dei fatti non riuscito: letture per fascicolo", exc_info=True)
        setattr(g, _CHIAVE, precedente)
    try:
        yield
    finally:
        setattr(g, _CHIAVE, precedente)


def fatti_precaricati(fascicolo_id: str, filtri: dict[str, Any], canonico: bool) -> list[Any] | None:
    """I fatti già in memoria per questa domanda, oppure None se va letto l'archivio."""
    if not canonico or set(filtri) != {"categoria"} or not has_request_context():
        return None
    memoria = getattr(g, _CHIAVE, None)
    if not memoria:
        return None
    fatti = memoria.get((_testo(fascicolo_id), _testo(filtri.get("categoria"))))
    return None if fatti is None else list(fatti)


__all__ = ["fatti_precaricati", "precaricati"]
