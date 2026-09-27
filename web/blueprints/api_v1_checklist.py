"""API React della checklist degli atti e del percorso guidato di raccolta documenti.

Montato sotto `/api/v1/ui/checklist`; la forma dei dati sta in
`web/services/react_checklist_atti_bridge.py`. I documenti si caricano con la
via comune `/fascicoli/<id>/documenti/carica`; qui si leggono lo stato dei
passi, i passi facoltativi saltati (nella sessione, come nella vista storica)
e il testo dell'indice.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from web.blueprints.api_v1_react import _audit_event, _request_json_object, _richiedi_auth
from web.helpers import get_fascicoli
from web.services import react_checklist_atti_bridge as bridge

api_v1_checklist = Blueprint("api_v1_checklist", __name__)


def _errore_controllato(messaggio: str):
    current_app.logger.exception(messaggio)
    return jsonify(ok=False, message="Checklist non disponibile: riprova fra poco."), 500


def _saltati(id_fasc: str, id_modello: str) -> list[int]:
    valori = session.get(bridge.CHIAVE_SALTATI.format(fascicolo=id_fasc, modello=id_modello), [])
    return [int(v) for v in valori if str(v).isdigit()]


@api_v1_checklist.get("")
@_richiedi_auth
def catalogo():
    try:
        return jsonify(bridge.catalogo(area=(request.args.get("area") or "").strip(), q=(request.args.get("q") or "").strip()))
    except Exception:
        return _errore_controllato("Errore catalogo checklist atti")


@api_v1_checklist.get("/<id_modello>")
@_richiedi_auth
def scheda(id_modello: str):
    try:
        id_fasc = (request.args.get("id_fasc") or "").strip()
        fascicolo = get_fascicoli().get(id_fasc) if id_fasc else None
        risultato, stato = bridge.scheda(
            id_modello,
            fascicolo=fascicolo,
            parte=(request.args.get("parte") or "").strip(),
            rg=(request.args.get("rg") or "").strip(),
            data=(request.args.get("data") or "").strip(),
        )
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore scheda checklist atto")


@api_v1_checklist.get("/percorso/<id_fasc>/<id_modello>")
@_richiedi_auth
def percorso(id_fasc: str, id_modello: str):
    try:
        risultato, stato = bridge.percorso(get_fascicoli().get(id_fasc), id_modello, _saltati(id_fasc, id_modello))
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore percorso guidato del fascicolo")


@api_v1_checklist.post("/percorso/<id_fasc>/<id_modello>/salta")
@_richiedi_auth
def salta(id_fasc: str, id_modello: str):
    payload, errore = _request_json_object()
    if errore is not None:
        return errore
    from pct.checklist_atti import get_template

    template = get_template(id_modello)
    try:
        numero = int((payload or {}).get("numero"))
    except (TypeError, ValueError):
        numero = -1
    richiesto = next((d for d in (template.documenti if template else []) if d.numero == numero), None)
    if richiesto is None:
        return jsonify(ok=False, message="Passo non trovato."), 404
    if richiesto.obbligatorio:
        return jsonify(ok=False, message="Un documento obbligatorio non si salta."), 409
    chiave = bridge.CHIAVE_SALTATI.format(fascicolo=id_fasc, modello=id_modello)
    saltati = _saltati(id_fasc, id_modello)
    if numero not in saltati:
        saltati.append(numero)
    session[chiave] = saltati
    risultato, stato = bridge.percorso(get_fascicoli().get(id_fasc), id_modello, saltati)
    return jsonify({**risultato, "message": f"«{richiesto.descrizione}» non verrà allegato."}), stato


@api_v1_checklist.post("/percorso/<id_fasc>/<id_modello>/indice")
@_richiedi_auth
def indice(id_fasc: str, id_modello: str):
    _payload, errore = _request_json_object()
    if errore is not None:
        return errore
    from pct.checklist_atti import get_template

    fascicolo = get_fascicoli().get(id_fasc)
    template = get_template(id_modello)
    if fascicolo is None or template is None:
        return jsonify(ok=False, message="Fascicolo o modello non trovato."), 404
    try:
        testo = bridge.testo_indice(fascicolo, template, _saltati(id_fasc, id_modello))
        _audit_event("fascicoli.wizard.indice", "fascicolo", id_fasc, f"Indice dei documenti del modello {id_modello} preparato.")
        return jsonify(
            ok=True,
            fileName=f"00_Indice_{template.id}.txt",
            text=testo,
            note=f"[wizard:{template.id}:indice] Indice generato automaticamente",
            uploadAction=f"/fascicoli/{id_fasc}/documenti/carica",
        )
    except Exception:
        return _errore_controllato("Errore indice del percorso guidato")
