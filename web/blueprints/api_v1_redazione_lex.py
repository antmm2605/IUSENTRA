"""API React: Lex scrive le parti narrative dell'atto nella redazione guidata.

Montato sotto ``/api/v1/ui/redazione-atti/lex``. Permessi: ``ai.usa`` e ``fascicoli.leggi``. Solo provider locali.
Restituisce blocchi, revisione indipendente e stato della consegna; l'inserimento nei campi lo decide l'avvocato.
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify

from web.blueprints.api_v1_react import _audit_event, _request_json_object, _richiedi_auth

api_v1_redazione_lex = Blueprint("api_v1_redazione_lex", __name__)


@api_v1_redazione_lex.post("/blocchi")
@_richiedi_auth
def redazione_lex_blocchi():
    utente = g.get("utente_corrente")
    ha = getattr(utente, "ha_permesso", lambda _p: False)
    if not (ha("ai.usa") and ha("fascicoli.leggi")):
        return jsonify(ok=False, errore="Serve il permesso di usare Lex e di leggere i fascicoli."), 403
    try:
        from lex.gateway.service import LexGateway
        from pct.compilatore_atti import campi_modello
        from web.blueprints.api_v1_react import _redazione_carica_fascicolo_cliente
        from web.blueprints.api_v1_ricerca_legale import _normativa_db
        from web.services import redazione_lex_runtime as runtime
        from web.services.schede_compilazione_runtime import compilazione_per_modello

        dati, errore_corpo = _request_json_object()
        if errore_corpo is not None:
            return errore_corpo
        model_code = str(dati.get("modelCode") or "").strip()
        oggetto = str(dati.get("oggetto") or "").strip()
        if len(oggetto) > 16000:
            return jsonify(ok=False, errore="Richiesta troppo lunga: riducila prima di riprovare."), 400
        valori = dati.get("valori") if isinstance(dati.get("valori"), dict) else {}
        if not oggetto:
            return jsonify(ok=False, errore="Scrivi la richiesta: cosa deve ottenere l'atto per l'assistito."), 200
        fascicolo, cliente, errore = _redazione_carica_fascicolo_cliente(str(dati.get("idFascicolo") or ""),
                                                                         str(dati.get("idCliente") or ""))
        if errore:
            return jsonify(ok=False, errore=errore), 200
        risolta = compilazione_per_modello(model_code, valori, fascicolo)
        if not risolta or not risolta.get("scrive_lex"):
            return jsonify(ok=False, errore="Per questo modello non c'e' una scheda con parti da far scrivere a Lex."), 200
        gateway = LexGateway()
        provider = runtime.provider_locale(gateway)
        if not provider:
            return jsonify(ok=False, errore="Nessun modello AI locale attivo: abilita llama.cpp o Ollama sul server."), 200
        campi = [str(c.get("name") if isinstance(c, dict) else c) for c in (campi_modello(model_code) or [])]
        from web.blueprints.api_v1_schede_fonti import _studio_db
        esito = runtime.stesura(model_code=model_code, risolta=risolta, fascicolo=fascicolo, cliente=cliente,
                                oggetto=oggetto, ruolo_assistito=str(dati.get("ruoloAssistito") or ""),
                                biblioteca=_normativa_db(),
                                chiama_modello=runtime.chiamata_gateway(gateway, str(getattr(utente, "id", "")), provider),
                                campi_modello=campi, studio_db=_studio_db())
        _audit_event("redazione_lex.blocchi", "modello_atto", model_code, "Bozza locale generata; nessun inserimento automatico.")
        return jsonify(ok=True, **esito), 200
    except Exception as exc:
        from flask import current_app

        current_app.logger.exception("Stesura Lex non riuscita: %s", exc)
        return jsonify(ok=False, errore="Lex non ha potuto scrivere le parti dell'atto: riprova o compila a mano."), 200
