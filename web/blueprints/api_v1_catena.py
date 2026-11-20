"""API v1 UI del guardiano della catena del fascicolo — /api/v1/ui/...

- ``GET /fascicoli/<id>/guardiano-catena``: stato del controllo (verificato o in aggiornamento), avvisi aperti che
  dicono che cosa non torna e perché, riparazioni registrate e ultimi giri (permesso ``fascicoli.leggi``);
- ``GET /guardiano-catena``: registro dei controlli dello studio, riepilogo per tipo di incoerenza e mappa della
  catena (permesso ``fascicoli.leggi``).

Sola lettura del registro (``pct/catena/registro.py``): nessun controllo gira durante la richiesta della pagina.
Il tenant è sempre quello della richiesta.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, current_app, g, jsonify

from web.services.tenant_api_auth import api_key_valid_for_request

api_v1_catena = Blueprint("api_v1_catena", __name__, url_prefix="/api/v1/ui")
PERMESSO_LETTURA = "fascicoli.leggi"


def _richiedi_lettura(funzione: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(funzione)
    def wrapper(*args: Any, **kwargs: Any):
        if api_key_valid_for_request():
            return funzione(*args, **kwargs)
        utente = g.get("utente_corrente")
        if not utente:
            return jsonify({"ok": False, "code": "unauthorized", "errore": "Autenticazione richiesta."}), 401
        if not getattr(utente, "ha_permesso", lambda _p: False)(PERMESSO_LETTURA):
            return jsonify({"ok": False, "code": "forbidden", "errore": "Permessi insufficienti."}), 403
        return funzione(*args, **kwargs)

    return wrapper


@api_v1_catena.get("/fascicoli/<id_fasc>/guardiano-catena")
@_richiedi_lettura
def fascicolo_guardiano_catena(id_fasc: str):
    """Gli avvisi del guardiano per il fascicolo: che cosa non torna nella catena e perché."""
    try:
        from web.helpers import get_fascicoli
        from web.services.catena_guardiano_runtime import payload_fascicolo

        if get_fascicoli().get(id_fasc) is None:
            return jsonify({"ok": False, "notFound": True, "errore": "Fascicolo non trovato."}), 404
        return jsonify(payload_fascicolo(id_fasc))
    except Exception as exc:
        current_app.logger.exception("Guardiano della catena del fascicolo %s non disponibile: %s", id_fasc, exc)
        return jsonify({"ok": False, "avvisi": [], "errore": "Controllo della catena non disponibile in questo momento."}), 200


@api_v1_catena.get("/guardiano-catena")
@_richiedi_lettura
def registro_guardiano_catena():
    """Il registro dei controlli della catena di tutto lo studio."""
    try:
        from web.services.catena_guardiano_runtime import payload_studio

        return jsonify(payload_studio())
    except Exception as exc:
        current_app.logger.exception("Registro del guardiano della catena non disponibile: %s", exc)
        return jsonify({"ok": False, "errore": "Registro dei controlli non disponibile in questo momento."}), 200
