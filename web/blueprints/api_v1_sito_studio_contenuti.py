"""API React dei contenuti del sito dello studio: servizi, professionisti, sedi, orari prenotabili.

Montato sotto `/api/v1/ui/sito-studio/contenuti`; campi e controlli in
`web/services/react_sito_studio_contenuti_bridge.py`. Come la vista storica,
serve il permesso di configurazione dello studio (`site_admin_identity_or_403`).
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from web.blueprints.api_v1_react import _request_json_object, _richiedi_auth
from web.services import react_sito_studio_contenuti_bridge as bridge
from web.services.studio_site_runtime import audit_studio_site_action, get_site_for_current_tenant, studio_site_repository

api_v1_sito_studio_contenuti = Blueprint("api_v1_sito_studio_contenuti", __name__)


def _sito() -> int:
    return int(get_site_for_current_tenant()["id"])


def _errore_controllato(messaggio: str):
    current_app.logger.exception(messaggio)
    return jsonify(ok=False, message="Operazione non riuscita: riprova fra poco."), 500


@api_v1_sito_studio_contenuti.get("/impostazioni")
@_richiedi_auth
def impostazioni():
    try:
        return jsonify(bridge.impostazioni(get_site_for_current_tenant()))
    except Exception:
        return _errore_controllato("Errore impostazioni del sito")


@api_v1_sito_studio_contenuti.post("/impostazioni")
@_richiedi_auth
def salva_impostazioni():
    site = get_site_for_current_tenant()
    payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = bridge.salva_impostazioni(studio_site_repository(), site, payload or {})
        if risultato.get("ok"):
            audit_studio_site_action("sito_studio.aggiorna_impostazioni", resource_id=str(site["id"]), details="Impostazioni del sito aggiornate dalla pagina React.")
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore salvataggio impostazioni del sito")


@api_v1_sito_studio_contenuti.post("/articoli/bozza")
@_richiedi_auth
def bozza_articolo():
    site_id = _sito()
    payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = bridge.crea_bozza_articolo(studio_site_repository(), site_id, payload or {})
        if risultato.get("ok"):
            audit_studio_site_action("sito_studio.articolo.crea", resource_id=str(risultato["item"]["id"]))
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore creazione bozza articolo")


@api_v1_sito_studio_contenuti.get("/<raccolta>")
@_richiedi_auth
def elenco(raccolta: str):
    site_id = _sito()
    try:
        risultato, stato = bridge.elenco(studio_site_repository(), site_id, raccolta)
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore elenco contenuti del sito")


@api_v1_sito_studio_contenuti.post("/<raccolta>")
@_richiedi_auth
def crea(raccolta: str):
    site_id = _sito()
    payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = bridge.salva(studio_site_repository(), site_id, raccolta, payload or {})
        if risultato.get("ok"):
            audit_studio_site_action(f"sito.{raccolta}.crea", resource_id=str(risultato["item"]["id"]))
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore salvataggio contenuto del sito")


@api_v1_sito_studio_contenuti.post("/<raccolta>/<item_id>")
@_richiedi_auth
def aggiorna(raccolta: str, item_id: str):
    site_id = _sito()
    payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = bridge.salva(studio_site_repository(), site_id, raccolta, payload or {}, item_id=item_id)
        if risultato.get("ok"):
            audit_studio_site_action(f"sito.{raccolta}.aggiorna", resource_id=item_id)
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore aggiornamento contenuto del sito")


@api_v1_sito_studio_contenuti.post("/<raccolta>/<item_id>/elimina")
@_richiedi_auth
def elimina(raccolta: str, item_id: str):
    site_id = _sito()
    _payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = bridge.elimina(studio_site_repository(), site_id, raccolta, item_id)
        if risultato.get("ok"):
            audit_studio_site_action(f"sito.{raccolta}.elimina", resource_id=item_id)
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore eliminazione contenuto del sito")
