"""Accesso di Lex al fascicolo indicato nella richiesta: solo se l'utente può vederlo.

Il ``fascicolo_id`` arriva dal client e non prova nulla. Prima che Lex legga fatti, termini o documenti del
fascicolo si applica la regola dello studio (``web/services/clienti_visibilita.cliente_visibile``, la stessa di
``mediazione_fascicolo_routes``): il fascicolo è visibile se non ha cliente, oppure se il suo cliente è visibile
all'utente (permesso ``clienti.leggi`` o cartella condivisa). Fail-closed: un errore nega l'accesso.

Base: art. 32 GDPR e art. 2-quaterdecies D.Lgs. 196/2003 (accesso limitato alle persone autorizzate),
art. 13 L. 247/2012 (segreto professionale).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

_log = logging.getLogger(__name__)

NEGATO = ("**Fascicolo non accessibile**\n- Il fascicolo indicato non è visibile con il tuo profilo (cliente non "
          "condiviso o fascicolo inesistente): non leggo né riporto alcun suo dato. Chiedi al titolare dello studio "
          "la condivisione della cartella del cliente.")


def _carica_fascicolo(fascicolo_id: str) -> Any:
    from web.helpers import get_fascicoli

    return get_fascicoli().get(fascicolo_id)


def _cliente_visibile(id_cliente: str) -> bool:
    from web.services.clienti_visibilita import cliente_visibile

    return cliente_visibile(id_cliente)


def fascicolo_accessibile(fascicolo_id: Any, *, carica: Callable[[str], Any] | None = None,
                          visibile: Callable[[str], bool] | None = None) -> str:
    """L'identificativo se l'utente corrente può vedere il fascicolo, altrimenti stringa vuota."""
    fid = " ".join(str(fascicolo_id or "").split())
    if not fid:
        return ""
    try:
        fascicolo = (carica or _carica_fascicolo)(fid)
        if fascicolo is None:
            return ""
        id_cliente = str(getattr(fascicolo, "id_cliente", "") or "")
        if id_cliente and not (visibile or _cliente_visibile)(id_cliente):
            return ""
        return fid
    except Exception:
        _log.exception("Lex: controllo di accesso al fascicolo non riuscito, accesso negato")
        return ""
