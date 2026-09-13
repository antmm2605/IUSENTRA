"""Ricerca dei fascicoli per nome del cliente, per le superfici React.

La regola di somiglianza vive nel dominio (`pct.ricerca_cliente_fascicolo`):
qui si legano soltanto i gestori del tenant corrente al risultato che la UI
consuma, cosi' che la stessa regola resti valida anche fuori dal web.
"""

from __future__ import annotations

from typing import Any, Callable

from pct.ricerca_cliente_fascicolo import LIMITE_PREDEFINITO, cerca_fascicoli

LUNGHEZZA_MINIMA = 2


def _clienti_per_id(gestore_clienti: Callable[[], Any]) -> dict[str, Any]:
    try:
        clienti = gestore_clienti().tutti()
    except Exception:
        return {}
    return {str(getattr(cliente, "id", "") or ""): cliente for cliente in clienti}


def cerca_fascicoli_per_cliente(
    richiesta: str,
    *,
    gestore_fascicoli: Callable[[], Any],
    gestore_clienti: Callable[[], Any],
    limite: int = LIMITE_PREDEFINITO,
) -> list[dict[str, Any]]:
    """Candidati serializzati per la UI, dal piu' sicuro al meno.

    Una richiesta troppo corta non restituisce nulla: proporre l'intero
    archivio a una lettera sarebbe rumore, non ricerca.
    """
    testo = str(richiesta or "").strip()
    if len(testo) < LUNGHEZZA_MINIMA:
        return []
    fascicoli = gestore_fascicoli().tutti(archiviati=False)
    candidati = cerca_fascicoli(
        fascicoli,
        richiesta=testo,
        clienti_per_id=_clienti_per_id(gestore_clienti),
        limite=limite,
    )
    return [candidato.come_dizionario() for candidato in candidati]
