"""API React delle funzioni del catalogo applicazioni (ex cabina `/applicazioni`).

Montato sotto `/api/v1/ui/applicazioni`; la forma dei dati sta in
`web/services/react_applicazioni_bridge.py`. Le letture seguono la vista
storica (utente autenticato); il precompilato da una pratica richiede anche il
permesso `fascicoli.leggi`. Nessuna scrittura: i calcoli non si registrano.
"""

from __future__ import annotations

import re

from flask import Blueprint, current_app, g, jsonify, request

from pct.applicazioni_catalogo import get_applicazione
from pct.strumenti_legali import GestioneStrumentiLegali
from web.blueprints.api_v1_react import _api_key_valida, _richiedi_auth
from web.helpers import get_clienti, get_fascicoli
from web.services import react_applicazioni_bridge as bridge

api_v1_applicazioni = Blueprint("api_v1_applicazioni", __name__)

_ID_VOCE = re.compile(r"^[a-z0-9_]{1,80}$")
_ID_FASCICOLO = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _errore_controllato(messaggio: str):
    current_app.logger.exception(messaggio)
    return jsonify(ok=False, message="Funzione momentaneamente non disponibile: riprova fra poco.", rows=[], notes=[]), 200


def _voce_o_404(app_id: str):
    voce = get_applicazione(app_id) if _ID_VOCE.fullmatch(app_id or "") else None
    if voce is None:
        return None, (jsonify(ok=False, message="Funzione non trovata nel catalogo."), 404)
    return voce, None


def _puo_leggere_fascicoli() -> bool:
    if _api_key_valida():
        return True
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("fascicoli.leggi"))


def _contesto_pratica() -> tuple[dict[str, str] | None, dict[str, str], list[str]]:
    """Pratica indicata con `?id_fascicolo=`: etichetta, campi precompilati e avvisi."""

    id_fascicolo = (request.args.get("id_fascicolo") or "").strip()
    if not id_fascicolo:
        return None, {}, []
    if not _ID_FASCICOLO.fullmatch(id_fascicolo):
        return None, {}, ["Identificativo della pratica non valido."]
    if not _puo_leggere_fascicoli():
        return None, {}, ["Non hai accesso alle pratiche: i campi non sono stati precompilati."]
    from web.services.applicazioni_runtime import _studio_context

    return bridge.contesto_fascicolo(
        id_fascicolo,
        gestore_strumenti=GestioneStrumentiLegali(
            normative_db_path=current_app.config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json")
        ),
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        studio=_studio_context(),
        utente=g.get("utente_corrente"),
    )


@api_v1_applicazioni.get("/contesto-fascicolo")
@_richiedi_auth
def contesto_fascicolo():
    """Campi degli Strumenti forensi ricavati dalla pratica (`?id_fascicolo=`)."""

    try:
        fascicolo, prefill, avvisi = _contesto_pratica()
        return jsonify(ok=fascicolo is not None, fascicolo=fascicolo, prefill=prefill, warnings=avvisi)
    except Exception:  # noqa: BLE001 - errore registrato, risposta JSON controllata
        return _errore_controllato("Errore contesto pratica per gli strumenti")


@api_v1_applicazioni.get("/<app_id>")
@_richiedi_auth
def scheda(app_id: str):
    voce, errore = _voce_o_404(app_id)
    if errore is not None:
        return errore
    try:
        from web.services.react_studio_module_bridge import _catalog_entry_href

        id_fascicolo = (request.args.get("id_fascicolo") or "").strip()
        item = bridge.scheda(
            voce,
            href_catalogo=_catalog_entry_href(voce),
            id_fascicolo=id_fascicolo if _ID_FASCICOLO.fullmatch(id_fascicolo) else "",
        )
        avvisi: list[str] = []
        item["prefill"], item["fascicolo"] = {}, None
        if item["type"] == "tool":
            item["fascicolo"], item["prefill"], avvisi = _contesto_pratica()
        return jsonify(ok=True, item=item, warnings=avvisi)
    except Exception:  # noqa: BLE001 - errore registrato, risposta JSON controllata
        return _errore_controllato(f"Errore scheda applicazione {app_id}")


@api_v1_applicazioni.post("/<app_id>/esegui")
@_richiedi_auth
def esegui(app_id: str):
    voce, errore = _voce_o_404(app_id)
    if errore is not None:
        return errore
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(ok=False, message="Invia i valori del modulo in formato JSON.", rows=[], notes=[]), 400
    valori = payload.get("values") if isinstance(payload.get("values"), dict) else payload
    try:
        return jsonify(bridge.esegui(voce, valori))
    except Exception:  # noqa: BLE001 - errore registrato, risposta JSON controllata
        return _errore_controllato(f"Errore esecuzione applicazione {app_id}")
