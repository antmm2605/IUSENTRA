"""API React dei modelli di studio (template atti scritti dallo studio).

Scheda, creazione, modifica e compilazione: la logica sta in
`web/services/react_template_studio_bridge.py`; il PDF resta la route
`POST /template-atti/<id>/pdf`.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from web.blueprints.api_v1_react import _audit_event, _request_json_object, _richiedi_auth
from web.services import react_template_studio_bridge as bridge

api_v1_template_studio = Blueprint("api_v1_template_studio", __name__)


def _errore_controllato(messaggio: str):
    current_app.logger.exception(messaggio)
    return jsonify(ok=False, message="Operazione non riuscita: riprova fra poco."), 500


@api_v1_template_studio.get("/nuovo")
@_richiedi_auth
def modulo_nuovo():
    try:
        risultato, stato = bridge.modulo_modello()
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore modulo nuovo modello di studio")


@api_v1_template_studio.post("/nuovo")
@_richiedi_auth
def crea():
    payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = bridge.salva_modello(payload or {})
        if risultato.get("ok"):
            _audit_event("template_atti.crea", "template_atti", str((risultato.get("item") or {}).get("id") or ""), "Modello di studio creato da superficie React.")
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore creazione modello di studio")


@api_v1_template_studio.get("/<id_template>")
@_richiedi_auth
def scheda(id_template: str):
    try:
        risultato, stato = bridge.scheda_modello(id_template)
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore scheda modello di studio")


@api_v1_template_studio.get("/<id_template>/modifica")
@_richiedi_auth
def modulo_modifica(id_template: str):
    try:
        risultato, stato = bridge.modulo_modello(id_template)
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore modulo modifica modello di studio")


@api_v1_template_studio.post("/<id_template>/modifica")
@_richiedi_auth
def aggiorna(id_template: str):
    payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = bridge.salva_modello(payload or {}, id_template)
        if risultato.get("ok"):
            _audit_event("template_atti.modifica", "template_atti", id_template, "Modello di studio aggiornato da superficie React.")
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore modifica modello di studio")


@api_v1_template_studio.get("/<id_template>/usa")
@_richiedi_auth
def uso(id_template: str):
    try:
        risultato, stato = bridge.uso_modello(
            id_template,
            id_cliente=str(request.args.get("id_cliente") or "").strip(),
            id_fascicolo=str(request.args.get("id_fascicolo") or "").strip(),
        )
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore compilazione modello di studio")


@api_v1_template_studio.post("/<id_template>/genera")
@_richiedi_auth
def genera(id_template: str):
    payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = bridge.genera_testo(id_template, payload or {})
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore generazione testo modello di studio")


@api_v1_template_studio.post("/<id_template>/clona")
@_richiedi_auth
def clona(id_template: str):
    try:
        risultato, stato = bridge.clona_modello(id_template)
        if risultato.get("ok"):
            _audit_event("template_atti.clona", "template_atti", id_template, "Modello clonato da superficie React.")
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore clonazione modello di studio")


@api_v1_template_studio.post("/<id_template>/elimina")
@_richiedi_auth
def elimina(id_template: str):
    try:
        risultato, stato = bridge.elimina_modello(id_template)
        if risultato.get("ok"):
            _audit_event("template_atti.elimina", "template_atti", id_template, "Modello eliminato da superficie React.")
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore eliminazione modello di studio")
