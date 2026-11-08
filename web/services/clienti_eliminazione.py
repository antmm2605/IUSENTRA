"""Regole per eliminare la scheda di un cliente.

Un cliente con fascicoli collegati, anche archiviati, non si elimina: i dati del
rapporto professionale vanno conservati per dieci anni dalla cessazione della
prestazione (art. 31, comma 3, D.Lgs. 231/2007, testo vigente su Normattiva
consultato l'08/11/2026) e i fascicoli resterebbero senza cliente.
Se l'elenco dei fascicoli non si può leggere, l'eliminazione si blocca.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

MESSAGGIO_CLIENTE_CON_FASCICOLI = (
    "Il cliente ha fascicoli collegati, anche archiviati: la scheda va conservata "
    "per dieci anni dalla fine della prestazione (art. 31 D.Lgs. 231/2007). "
    "Riassegna i fascicoli prima di eliminarla."
)
MESSAGGIO_VERIFICA_NON_RIUSCITA = (
    "Non è stato possibile verificare i fascicoli del cliente: eliminazione non eseguita. Riprova tra poco."
)


class VerificaFascicoliNonRiuscita(RuntimeError):
    """L'elenco dei fascicoli non è leggibile: non si elimina nulla."""


def clienti_con_fascicoli(get_fascicoli: Callable[[], Any]) -> set[str]:
    """Identificativi dei clienti con almeno un fascicolo, compresi gli archiviati."""
    try:
        fascicoli = get_fascicoli().tutti(archiviati=True)
    except Exception as exc:  # fail-closed: nessuna eliminazione senza verifica
        raise VerificaFascicoliNonRiuscita(str(exc)) from exc
    return {str(getattr(f, "id_cliente", "") or "").strip() for f in fascicoli} - {""}
