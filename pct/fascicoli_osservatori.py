"""Un solo punto da cui i motori di lettura sanno che i documenti di un fascicolo sono cambiati.

Ogni metodo dell'archivio dei fascicoli che aggiunge, sostituisce, rimuove, ripristina, elimina o copia un
documento (anche nella fusione dei doppioni) avvisa gli osservatori registrati. Il registro delle letture è
l'osservatore principale: allinea l'inventario e fa leggere ai motori solo ciò che è nuovo o cambiato,
qualunque sia la via che ha toccato il documento (caricamento, import massivo, editor, firma, PagoPA, CTU…).

Il dominio non conosce Flask: gli osservatori li registra il wiring web. Un osservatore che fallisce non
blocca mai il salvataggio del documento.

Base normativa: art. 3 D.M. 44/2011 e art. 20 CAD (integrità e tracciabilità dei documenti informatici).
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

Osservatore = Callable[[str, str], None]
_osservatori: list[Osservatore] = []


def registra_osservatore(osservatore: Osservatore) -> None:
    if osservatore not in _osservatori:
        _osservatori.append(osservatore)


def rimuovi_osservatore(osservatore: Osservatore) -> None:
    if osservatore in _osservatori:
        _osservatori.remove(osservatore)


def notifica_documenti_cambiati(fascicolo_id: str, evento: str) -> None:
    fascicolo_id = str(fascicolo_id or "").strip()
    if not fascicolo_id:
        return
    for osservatore in list(_osservatori):
        try:
            osservatore(fascicolo_id, evento)
        except Exception as exc:  # il salvataggio del documento resta valido
            logger.warning("Osservatore dei documenti non riuscito per il fascicolo %s (%s): %s", fascicolo_id, evento, exc)


def _id_fascicolo(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    primo = kwargs.get("id_fasc", kwargs.get("primary", args[0] if args else ""))
    return str(primo if isinstance(primo, str) else getattr(primo, "id", "") or "")


def documenti_cambiati(evento: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decora un metodo dell'archivio dei fascicoli: dopo il salvataggio riuscito avvisa gli osservatori."""

    def decoratore(metodo: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(metodo)
        def avvolto(self: Any, *args: Any, **kwargs: Any) -> Any:
            esito = metodo(self, *args, **kwargs)
            notifica_documenti_cambiati(_id_fascicolo(args, kwargs), evento)
            return esito

        return avvolto

    return decoratore


__all__ = ["documenti_cambiati", "notifica_documenti_cambiati", "registra_osservatore", "rimuovi_osservatore"]
