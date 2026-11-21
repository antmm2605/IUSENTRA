"""API v1 UI della Gazzetta Ufficiale — /api/v1/ui/gazzetta-ufficiale...

- ``GET  /gazzetta-ufficiale``: atti dei sommari ufficiali con ricerca, filtri (serie, tipo di atto, sezione,
  ente emanante, intervallo di date, numero della Gazzetta), ordinamento e paginazione lato server;
- ``GET  /gazzetta-ufficiale/ultime``: le ultime 5 pubblicazioni di Serie generale e Corte costituzionale
  per la Panoramica;
- ``GET  /gazzetta-ufficiale/atti/<id>/testo``: il testo completo dell'atto salvato nell'archivio, con la fonte;
- ``POST /gazzetta-ufficiale/aggiorna``: legge subito i sommari nuovi (un giro alla volta, non più di uno
  ogni 5 minuti, tempo massimo 45 secondi).

I dati sono pubblici e uguali per tutti gli studi; basta l'autenticazione.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, current_app, g, jsonify, request

from web.services.tenant_api_auth import api_key_valid_for_request

api_v1_gazzetta = Blueprint("api_v1_gazzetta", __name__, url_prefix="/api/v1/ui")

_NON_DISPONIBILE = "La Gazzetta Ufficiale non è consultabile in questo momento. Riprova fra poco."


def _richiedi_auth(funzione: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(funzione)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or api_key_valid_for_request():
            return funzione(*args, **kwargs)
        return jsonify({"ok": False, "code": "unauthorized", "message": "Autenticazione richiesta."}), 401

    return wrapper


def _senza_cache(payload: dict[str, Any]):
    risposta = jsonify(payload)
    risposta.headers["Cache-Control"] = "no-store, max-age=0"
    return risposta


@api_v1_gazzetta.get("/gazzetta-ufficiale")
@_richiedi_auth
def gazzetta_ufficiale_elenco():
    from web.services import gazzetta_runtime as vista

    try:
        filtri = vista.filtri_richiesti(request.args)
        return _senza_cache(vista.costruisci_vista(vista.archivio_in_lettura(current_app.config), filtri))
    except Exception as exc:
        current_app.logger.exception("Gazzetta Ufficiale non disponibile: %s", exc)
        return jsonify({"ok": False, "items": [], "total": 0, "message": _NON_DISPONIBILE}), 200


@api_v1_gazzetta.get("/gazzetta-ufficiale/ultime")
@_richiedi_auth
def gazzetta_ufficiale_ultime():
    from web.services import gazzetta_runtime as vista

    try:
        return _senza_cache(vista.ultime_pubblicazioni(vista.archivio_in_lettura(current_app.config)))
    except Exception as exc:
        current_app.logger.exception("Ultime pubblicazioni della Gazzetta Ufficiale non disponibili: %s", exc)
        return jsonify({"ok": False, "items": [], "message": _NON_DISPONIBILE}), 200


@api_v1_gazzetta.get("/gazzetta-ufficiale/atti/<atto_id>/testo")
@_richiedi_auth
def gazzetta_ufficiale_testo(atto_id: str):
    from web.services import gazzetta_runtime as vista

    try:
        payload = vista.testo_dell_atto(vista.archivio_in_lettura(current_app.config), atto_id)
        return _senza_cache(payload), (404 if payload.get("notFound") else 200)
    except Exception as exc:
        current_app.logger.exception("Testo dell'atto della Gazzetta Ufficiale non disponibile: %s", exc)
        return jsonify({"ok": False, "message": _NON_DISPONIBILE}), 200


@api_v1_gazzetta.post("/gazzetta-ufficiale/aggiorna")
@_richiedi_auth
def gazzetta_ufficiale_aggiorna():
    from web.services import gazzetta_runtime as vista

    try:
        esito = vista.aggiorna_ora(current_app.config)
        if esito.get("eseguito"):
            dettaglio = esito.get("esito") or {}
            audit = (current_app.extensions.get("core_runtime", {}) or {}).get("audit")
            if callable(audit):
                audit(
                    "gazzetta_ufficiale.aggiornamento", "informazione_professionale", "gazzetta_ufficiale",
                    f"Fascicoli nuovi {dettaglio.get('fascicoli_nuovi', 0)}, atti nuovi {dettaglio.get('atti_nuovi', 0)}.",
                )
        payload = vista.costruisci_vista(vista.archivio_in_lettura(current_app.config), vista.filtri_richiesti(request.args))
        payload["refresh"] = {"done": bool(esito.get("eseguito")), "reason": str(esito.get("motivo") or "")}
        return _senza_cache(payload)
    except Exception as exc:
        current_app.logger.exception("Aggiornamento della Gazzetta Ufficiale non riuscito: %s", exc)
        return jsonify({"ok": False, "items": [], "message": "Aggiornamento della Gazzetta Ufficiale non riuscito."}), 200


__all__ = ["api_v1_gazzetta"]
