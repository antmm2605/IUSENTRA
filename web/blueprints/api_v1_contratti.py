"""API React del catalogo contratti dello studio.

Base normativa: art. 1322 c.c. e disciplina generale artt. 1321-1469 c.c.;
le norme speciali sono dichiarate voce per voce in ``pct/contratti/dati``.
Le rotte sono di sola consultazione e valutazione: nessun dato dello studio
viene scritto; i punti di valutazione restano all'avvocato.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from pct.contratti import carica_catalogo, famiglia, regole_comuni, valuta
from web.blueprints.api_v1_react import _richiedi_auth

api_v1_contratti = Blueprint("api_v1_contratti", __name__)


@api_v1_contratti.get("/catalogo")
@_richiedi_auth
def catalogo():
    try:
        return jsonify({"ok": True, **carica_catalogo(), "regole_comuni": regole_comuni()})
    except Exception:
        current_app.logger.exception("Errore catalogo contratti")
        return jsonify(ok=False, message="Catalogo contratti non disponibile."), 500


@api_v1_contratti.get("/famiglie/<contratto_id>")
@_richiedi_auth
def dettaglio(contratto_id: str):
    try:
        return jsonify({"ok": True, "contratto": famiglia(contratto_id[:80]).come_dict()})
    except LookupError as exc:
        return jsonify(ok=False, message=str(exc)), 404


@api_v1_contratti.post("/famiglie/<contratto_id>/valutazione")
@_richiedi_auth
def valutazione(contratto_id: str):
    dati = request.get_json(silent=True)
    fatti = dati.get("fatti", {}) if isinstance(dati, dict) else {}
    if not isinstance(fatti, dict):
        return jsonify(ok=False, message="I fatti devono essere un oggetto."), 400
    try:
        return jsonify({"ok": True, **valuta(contratto_id[:80], fatti)})
    except LookupError as exc:
        return jsonify(ok=False, message=str(exc)), 404
