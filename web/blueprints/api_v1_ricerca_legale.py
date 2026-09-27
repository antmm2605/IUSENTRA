"""API React delle schede della Ricerca legale (news, fonte, variazione rilevata).

Montato sotto `/api/v1/ui/ricerca-legale`; la forma dei dati sta in
`web/services/react_ricerca_legale_dettagli.py`. L'approvazione di una
variazione applica il cambiamento al motore dello studio: richiede
`admin.configura`.
"""

from __future__ import annotations

import threading

from flask import Blueprint, current_app, g, jsonify

from web.blueprints.api_v1_react import _audit_event, _request_json_object, _richiedi_auth
from web.helpers import get_legal_intelligence, get_legal_update_pipeline
from web.services import react_ricerca_legale_dettagli as dettagli

api_v1_ricerca_legale = Blueprint("api_v1_ricerca_legale", __name__)

# Un solo controllo giornaliero alla volta per archivio: scarica le fonti
# ufficiali e confronta le impronte, fuori dalla richiesta dell'avvocato.
_CONTROLLI_IN_CORSO: set[str] = set()
_LOCK_CONTROLLI = threading.Lock()


def _puo_configurare() -> bool:
    return bool(getattr(g.get("utente_corrente"), "ha_permesso", lambda _p: False)("admin.configura"))


def _motore_giornaliero():
    from web.blueprints.legal_intelligence import _daily_engine

    return _daily_engine()


def _errore_controllato(messaggio: str):
    current_app.logger.exception(messaggio)
    return jsonify(ok=False, message="Scheda non disponibile: riprova fra poco."), 500


@api_v1_ricerca_legale.get("/news/<slug>")
@_richiedi_auth
def news(slug: str):
    try:
        risultato, stato = dettagli.scheda_news(get_legal_update_pipeline().repository.get_news_by_slug(slug))
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore scheda news Ricerca legale")


@api_v1_ricerca_legale.get("/fonti/<source_id>")
@_richiedi_auth
def fonte(source_id: str):
    try:
        righe = getattr(get_legal_intelligence(), "_source_status_rows")()
        motore = _motore_giornaliero()
        risultato, stato = dettagli.scheda_fonte(source_id, righe, motore.get_source_card, motore.sources)
        if stato == 200:
            if not _puo_configurare():
                for voce in risultato["item"]["updates"]:
                    voce["approveAction"] = ""
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore scheda fonte Ricerca legale")


def _numero(update_id: str) -> int | None:
    testo = str(update_id or "").strip()
    return int(testo) if testo.isdigit() else None


@api_v1_ricerca_legale.get("/aggiornamenti/<update_id>")
@_richiedi_auth
def variazione(update_id: str):
    numero = _numero(update_id)
    if numero is None:
        return jsonify(ok=False, message="Aggiornamento non trovato."), 404
    try:
        risultato, stato = dettagli.scheda_variazione(_motore_giornaliero().get_update(numero))
        if stato == 200 and not _puo_configurare():
            risultato["item"]["approveAction"] = ""
        return jsonify(risultato), stato
    except Exception:
        return _errore_controllato("Errore scheda variazione Ricerca legale")


@api_v1_ricerca_legale.post("/aggiornamenti/<update_id>/approva")
@_richiedi_auth
def approva(update_id: str):
    if not _puo_configurare():
        return jsonify(ok=False, message="Serve il permesso di configurazione dello studio.", errors={"permission": "Operazione non autorizzata."}), 403
    _payload, errore = _request_json_object()
    if errore is not None:
        return errore
    numero = _numero(update_id)
    if numero is None:
        return jsonify(ok=False, message="Aggiornamento non trovato."), 404
    try:
        motore = _motore_giornaliero()
        voce = motore.get_update(numero)
        if not voce:
            return jsonify(ok=False, message="Aggiornamento non trovato."), 404
        if voce.get("status") != "pending_review":
            return jsonify(ok=False, message="L'aggiornamento non è in attesa di approvazione."), 409
        motore.approve_update(numero)
        _audit_event("ricerca_legale.approva_variazione", "legal_update", str(numero), "Variazione della fonte ufficiale approvata dalla scheda React.")
        return jsonify(ok=True, message="Aggiornamento approvato e registrato nel motore della Ricerca legale.", redirect_href=f"/ricerca-legale/daily/update/{numero}/diff")
    except Exception:
        return _errore_controllato("Errore approvazione variazione Ricerca legale")


@api_v1_ricerca_legale.get("/controllo-giornaliero")
@_richiedi_auth
def controllo_giornaliero():
    try:
        from web.blueprints.legal_intelligence import _daily_db_path

        percorso = str(_daily_db_path())
        cruscotto = _motore_giornaliero().dashboard_snapshot()
        with _LOCK_CONTROLLI:
            in_corso = percorso in _CONTROLLI_IN_CORSO
        return jsonify(dettagli.controllo_giornaliero(cruscotto, puo_eseguire=_puo_configurare(), in_corso=in_corso))
    except Exception:
        return _errore_controllato("Errore cruscotto controllo giornaliero")


@api_v1_ricerca_legale.post("/controllo-giornaliero/esegui")
@_richiedi_auth
def esegui_controllo_giornaliero():
    if not _puo_configurare():
        return jsonify(ok=False, message="Serve il permesso di configurazione dello studio.", errors={"permission": "Operazione non autorizzata."}), 403
    _payload, errore = _request_json_object()
    if errore is not None:
        return errore
    from legal_intelligence.engine import LegalIntelligenceDailyEngine
    from web.blueprints.legal_intelligence import _daily_db_path

    percorso = str(_daily_db_path())
    with _LOCK_CONTROLLI:
        if percorso in _CONTROLLI_IN_CORSO:
            return jsonify(ok=True, message="Il controllo è già in corso.", running=True)
        _CONTROLLI_IN_CORSO.add(percorso)
    logger = current_app.logger

    def corsa() -> None:
        try:
            LegalIntelligenceDailyEngine(percorso).run_daily_sync()
        except Exception:
            logger.exception("Controllo giornaliero delle fonti ufficiali non completato")
        finally:
            with _LOCK_CONTROLLI:
                _CONTROLLI_IN_CORSO.discard(percorso)

    threading.Thread(target=corsa, name="controllo-giornaliero-fonti", daemon=True).start()
    _audit_event("ricerca_legale.controllo_giornaliero", "legal_sources", "daily", "Controllo giornaliero delle fonti ufficiali avviato dalla Ricerca legale.")
    return jsonify(ok=True, message="Controllo avviato: le variazioni compaiono qui quando è concluso.", running=True), 202
