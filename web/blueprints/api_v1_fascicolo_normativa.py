"""API React della «Normativa» del fascicolo (sola lettura).

- `GET /api/v1/ui/fascicoli/<id>/normativa`: le norme del rito, dei termini
  aperti e dei tipi di documento della pratica, dai registri ufficiali del
  software (`pct.normativa_fascicolo`).
- `GET /api/v1/ui/fascicoli/<id>/normativa/testo?urn=…&articolo=…`: il testo
  di un articolo dall'archivio Normattiva importato sul server, con versione.

Permesso `fascicoli.leggi`; il tenant è quello della richiesta, risolto dal
caricatore della pratica: un identificativo di un altro studio non esiste.
"""

from __future__ import annotations

import json
import re

from flask import Blueprint, current_app, jsonify, request

from web.blueprints.api_v1_react import (
    _api_key_valida,
    _fascicolo_singolo_loader,
    _richiedi_auth,
    _session_user_can,
    _tenant_runtime_label,
    get_scadenziario,
)
from web.services.fascicolo_normativa_runtime import NORMATIVA_CACHE, build_normativa_payload, testo_archivio

api_v1_fascicolo_normativa = Blueprint("api_v1_fascicolo_normativa", __name__)

_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


def _negato():
    if _api_key_valida() or _session_user_can("fascicoli.leggi"):
        return None
    return jsonify(ok=False, message="Non hai il permesso per consultare questo fascicolo."), 403


def _archivio_db():
    from lex.retrieval.normativa_catalog import consultation_path

    return consultation_path()


def _non_trovato():
    return jsonify(ok=False, notFound=True, message="Fascicolo non trovato."), 404


def _fascicolo_esiste(fascicolo_id: str) -> bool:
    gestore = _fascicolo_singolo_loader()()
    return gestore is not None and gestore.get(fascicolo_id) is not None


@api_v1_fascicolo_normativa.get("/fascicoli/<fascicolo_id>/normativa")
@_richiedi_auth
def normativa_fascicolo(fascicolo_id: str):
    negato = _negato()
    if negato is not None:
        return negato
    if not _ID.match(fascicolo_id):
        return _non_trovato()
    chiave = (_tenant_runtime_label(), fascicolo_id)
    in_cache = NORMATIVA_CACHE.get(chiave)
    if in_cache is not None:
        return current_app.response_class(in_cache, mimetype="application/json")
    try:
        payload = build_normativa_payload(
            fascicolo_id, carica_fascicolo=_fascicolo_singolo_loader(), scadenziario=get_scadenziario, archivio_db=_archivio_db,
        )
    except Exception:
        current_app.logger.exception("Normativa del fascicolo %s non disponibile", fascicolo_id)
        return jsonify(ok=False, message="Normativa del fascicolo non disponibile: riprova fra poco."), 503
    if payload is None:
        return _non_trovato()
    corpo = json.dumps({"ok": True, "normativa": payload}, ensure_ascii=False).encode("utf-8")
    NORMATIVA_CACHE.set(chiave, corpo)
    return current_app.response_class(corpo, mimetype="application/json")


@api_v1_fascicolo_normativa.get("/fascicoli/<fascicolo_id>/normativa/testo")
@_richiedi_auth
def normativa_fascicolo_testo(fascicolo_id: str):
    negato = _negato()
    if negato is not None:
        return negato
    if not _ID.match(fascicolo_id):
        return _non_trovato()
    try:
        if not _fascicolo_esiste(fascicolo_id):
            return _non_trovato()
        testo = testo_archivio(_archivio_db(), request.args.get("urn", ""), request.args.get("articolo", ""))
    except Exception:
        current_app.logger.exception("Testo normativo non letto per il fascicolo %s", fascicolo_id)
        return jsonify(ok=False, message="Archivio normativo non disponibile: apri il testo su Normattiva."), 503
    if testo is None:
        return jsonify(ok=False, message="Il testo non è nell'archivio del server: aprilo su Normattiva."), 404
    return jsonify(ok=True, testo=testo)
