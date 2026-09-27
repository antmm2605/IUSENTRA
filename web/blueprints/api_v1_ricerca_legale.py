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


# ---------------------------------------------------------------- operazioni sulle fonti
#
# Monitoraggio delle fonti, allineamento delle tabelle normative e registro degli
# organismi di mediazione: le azioni della pagina storica `/ricerca-legale` (i cui
# moduli puntavano a `/legal-intelligence/...`, che risponde con un rinvio 301: il
# browser ripeteva la richiesta in GET e otteneva 405). Girano in sfondo come il
# controllo giornaliero; l'esito resta nel cruscotto e nei registri.

_OPERAZIONI = {
    "monitoraggio": ("run_monitor_cycle", {}, "Monitoraggio delle fonti"),
    "tabelle-normative": ("sync_normative_tables", {}, "Allineamento delle tabelle normative"),
    "registro-mediazione": ("sync_normative_tables", {"source_ids": ["registro_mediazione"]}, "Aggiornamento del registro degli organismi di mediazione"),
}


def _avvia_operazione(chiave: str):
    if not _puo_configurare():
        return jsonify(ok=False, message="Serve il permesso di configurazione dello studio.", errors={"permission": "Operazione non autorizzata."}), 403
    _payload, errore = _request_json_object()
    if errore is not None:
        return errore
    metodo, argomenti, etichetta = _OPERAZIONI[chiave]
    motore = get_legal_intelligence()
    segno = f"{chiave}:{getattr(motore, 'db_path', '')}"
    with _LOCK_CONTROLLI:
        if segno in _CONTROLLI_IN_CORSO:
            return jsonify(ok=True, message=f"{etichetta}: già in corso.", running=True)
        _CONTROLLI_IN_CORSO.add(segno)
    app = current_app._get_current_object()

    def corsa() -> None:
        try:
            with app.app_context():
                getattr(motore, metodo)(**argomenti)
        except Exception:
            app.logger.exception("%s non completato", etichetta)
        finally:
            with _LOCK_CONTROLLI:
                _CONTROLLI_IN_CORSO.discard(segno)

    threading.Thread(target=corsa, name=f"ricerca-legale-{chiave}", daemon=True).start()
    _audit_event(f"ricerca_legale.{chiave.replace('-', '_')}", "legal_sources", chiave, f"{etichetta} avviato dalla Ricerca legale.")
    return jsonify(ok=True, message=f"{etichetta} avviato: l'esito compare nel cruscotto quando è concluso.", running=True), 202


@api_v1_ricerca_legale.post("/monitoraggio/esegui")
@_richiedi_auth
def esegui_monitoraggio():
    return _avvia_operazione("monitoraggio")


@api_v1_ricerca_legale.post("/tabelle-normative/sincronizza")
@_richiedi_auth
def sincronizza_tabelle_normative():
    return _avvia_operazione("tabelle-normative")


@api_v1_ricerca_legale.post("/mediazione/sincronizza")
@_richiedi_auth
def sincronizza_registro_mediazione():
    return _avvia_operazione("registro-mediazione")


@api_v1_ricerca_legale.post("/mediazione/importa")
@_richiedi_auth
def importa_registro_mediazione():
    """Importa la pagina ufficiale del registro (file HTML o sorgente incollato)."""
    from flask import request

    if not _puo_configurare():
        return jsonify(ok=False, message="Serve il permesso di configurazione dello studio.", errors={"permission": "Operazione non autorizzata."}), 403
    upload = request.files.get("snapshot_file")
    contenuto: str | bytes = request.form.get("html_content", "")
    nome = ""
    if upload and upload.filename:
        nome = upload.filename
        contenuto = upload.read()
    if not contenuto:
        return jsonify(ok=False, message="Carica un file HTML del registro oppure incolla il sorgente HTML della pagina ufficiale.", errors={"snapshot_file": "File mancante."}), 400
    try:
        report = get_legal_intelligence().import_registro_mediazione_snapshot(contenuto, filename=nome)
    except Exception:
        current_app.logger.exception("Importazione del registro della mediazione non riuscita")
        return jsonify(ok=False, message="Importazione non riuscita: verifica che il file sia la pagina ufficiale del registro."), 400
    _audit_event("ricerca_legale.import_registro_mediazione", "legal_sources", "registro_mediazione", "Pagina ufficiale del registro degli organismi di mediazione importata.")
    return jsonify(ok=True, message=f"Pagina ufficiale importata: {report.get('rows', 0)} organismi disponibili nel gestionale.", rows=report.get("rows", 0))
