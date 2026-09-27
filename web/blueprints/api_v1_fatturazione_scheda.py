"""API React della scheda parcella: link di pagamento ed eliminazione della bozza.

Montato sotto `/api/v1/ui/fatturazione`; la logica sta in
`web/services/react_fatturazione_scheda_azioni.py`.
"""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from web.blueprints.api_v1_react import (
    _puo_scrivere_fatturazione,
    _request_json_object,
    _richiedi_auth,
)
from web.helpers import get_fatturazione, get_pagamenti, get_utenti
from web.services import react_fatturazione_scheda_azioni as azioni

api_v1_fatturazione_scheda = Blueprint("api_v1_fatturazione_scheda", __name__)


def _negato():
    return jsonify(ok=False, message="Permesso fatturazione.scrivi richiesto.", errors={"permission": "Operazione non autorizzata."}), 403


def _errore_controllato(messaggio: str):
    current_app.logger.exception(messaggio)
    return jsonify(ok=False, message="Operazione non riuscita: riprova fra poco.", errors={}), 500


@api_v1_fatturazione_scheda.post("/<id_parcella>/link-pagamento")
@_richiedi_auth
def link_pagamento(id_parcella: str):
    if not _puo_scrivere_fatturazione():
        return _negato()
    payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = azioni.crea_link_pagamento(
            get_fatturazione=get_fatturazione,
            get_pagamenti=get_pagamenti,
            get_utenti=get_utenti,
            current_user=g.get("utente_corrente"),
            id_parcella=id_parcella,
            giorni_validita=(payload or {}).get("giorni_validita"),
            host_url=request.host_url,
            ip_address=request.remote_addr or "",
        )
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore creazione link di pagamento dalla scheda parcella")


@api_v1_fatturazione_scheda.post("/<id_parcella>/elimina")
@_richiedi_auth
def elimina(id_parcella: str):
    if not _puo_scrivere_fatturazione():
        return _negato()
    _payload, errore = _request_json_object()
    if errore is not None:
        return errore
    try:
        risultato, stato = azioni.elimina_bozza(
            get_fatturazione=get_fatturazione,
            get_utenti=get_utenti,
            current_user=g.get("utente_corrente"),
            id_parcella=id_parcella,
            ip_address=request.remote_addr or "",
        )
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore eliminazione bozza dalla scheda parcella")
