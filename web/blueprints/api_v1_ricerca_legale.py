"""API React delle schede della Ricerca legale (news, fonte, variazione rilevata).

Montato sotto `/api/v1/ui/ricerca-legale`; la forma dei dati sta in
`web/services/react_ricerca_legale_dettagli.py`. L'approvazione di una
variazione applica il cambiamento al motore dello studio: richiede
`admin.configura`.
"""

from __future__ import annotations

import sqlite3

import threading

from flask import Blueprint, current_app, g, jsonify, request

from web.blueprints.api_v1_react import _audit_event, _request_json_object, _richiedi_auth
from web.helpers import get_legal_intelligence, get_legal_update_pipeline
from web.services import react_ricerca_legale_dettagli as dettagli
from lex.tempo_ricerca import RicercaTroppoLunga

api_v1_ricerca_legale = Blueprint("api_v1_ricerca_legale", __name__)


@api_v1_ricerca_legale.before_request
def _apri_tempo_massimo():
    # Una ricerca non deve occupare un thread del server per minuti (collaudo 21/11/2026).
    from lex.tempo_ricerca import apri_per_richiesta

    apri_per_richiesta()


@api_v1_ricerca_legale.teardown_request
def _chiudi_tempo_massimo(_exc=None):
    from lex.tempo_ricerca import chiudi_per_richiesta

    chiudi_per_richiesta()


@api_v1_ricerca_legale.errorhandler(RicercaTroppoLunga)
def _ricerca_troppo_lunga(exc):
    current_app.logger.warning("Ricerca interrotta per tempo massimo: %s %s", request.path, _parametri_per_log())
    return jsonify(ok=False, message=str(exc), code="tempo_massimo"), 503


def _parametri_per_log() -> str:
    """Solo i nomi dei parametri: i termini cercati possono contenere dati dei clienti."""
    return "parametri=" + ",".join(sorted(request.args.keys())[:12])


def _archivio_non_disponibile(exc: BaseException, messaggio: str):
    from lex.tempo_ricerca import interrotta, scaduta

    if interrotta(exc) and scaduta():
        return _ricerca_troppo_lunga(RicercaTroppoLunga())
    return jsonify(ok=False, message=messaggio), 503

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
        from legal_intelligence.engine import LegalIntelligenceDailyEngine

        cruscotto = LegalIntelligenceDailyEngine.read_dashboard(percorso)
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


# Public legal texts share Normattiva's dedicated archive across studios;
# authentication and the existing legal-research permissions remain required.
def _normativa_db():
    from lex.retrieval.normativa_catalog import consultation_path

    return consultation_path()


def _permesso_normativa():
    user = g.get("utente_corrente")
    check = getattr(user, "ha_permesso", lambda _p: False)
    if not (check("ai.usa") or check("fascicoli.leggi")):
        return jsonify(ok=False, message="Non hai il permesso per consultare le fonti."), 403
    return None


# Catalogo già serializzato e compresso per revisione: 6,6 MB di JSON a ogni apertura di
# «Codici e leggi» diventano circa 0,6 MB, preparati una volta sola (collaudo 21/11/2026).
_CATALOGHI_COMPRESSI: dict = {}
# Chiavi fisse: la vista chiesta dall'utente non entra mai nella cache così com'è.
_CHIAVI_CATALOGO = frozenset({"vigenti", "storico", "tutti"})
_LOCK_CATALOGHI = threading.Lock()


def _catalogo_compresso(chiave, sorgente, costruisci, impronta=None):
    """`sorgente` è la lista del catalogo salvato (resta nella voce, così il suo id non si riusa);
    `impronta` descrive le altre parti della risposta (archivio verificato)."""
    import gzip
    import json

    if chiave not in _CHIAVI_CATALOGO:
        raise ValueError("Vista del catalogo non ammessa")
    with _LOCK_CATALOGHI:
        voce = _CATALOGHI_COMPRESSI.get(chiave)
    if voce is None or voce[2] is not sorgente or voce[3] != impronta:
        testo = json.dumps(costruisci(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        voce = (testo, gzip.compress(testo, compresslevel=5), sorgente, impronta)
        with _LOCK_CATALOGHI:
            _CATALOGHI_COMPRESSI[chiave] = voce
    testo, compresso = voce[0], voce[1]
    risposta = current_app.response_class(mimetype="application/json")
    if "gzip" in (request.headers.get("Accept-Encoding") or "").lower():
        risposta.set_data(compresso)
        risposta.headers["Content-Encoding"] = "gzip"
    else:
        risposta.set_data(testo)
    risposta.headers["Vary"] = "Accept-Encoding"
    return risposta


@api_v1_ricerca_legale.get("/normativa/atti")
@_richiedi_auth
def normativa_atti():
    denied = _permesso_normativa()
    if denied is not None:
        return denied
    from lex.normativa.consultazione import catalogo
    try:
        from lex.normativa.cerdef_biblioteca import (
            ID_BASE, STORICO_ORIGINALE_BASE, VIGENTE_BASE, alias_originali_storici, fonti_catalogo, riscontro_vigente,
        )
        from lex.normativa.cerdef_catalogo_salvato import catalogo_cerdef_salvato, elenco_leggero

        vista = request.args.get("vista")
        data_dir = current_app.config["DATA_DIR"]
        if vista == "vigenti":
            if fonti_catalogo(VIGENTE_BASE) is None:
                return jsonify(ok=False, message="L’archivio con riscontri di vigenza non è configurato."), 503
            atti = catalogo_cerdef_salvato(data_dir, (VIGENTE_BASE,))
            if atti is not None:
                return _catalogo_compresso("vigenti", atti, lambda: {
                    "ok": True, "items": elenco_leggero(atti), "riscontro": riscontro_vigente(len(atti))})
        else:
            basi = (ID_BASE, 2 * ID_BASE)
            sostituzioni = {}
            if vista == "storico":
                basi += (STORICO_ORIGINALE_BASE,)
            collegati = catalogo_cerdef_salvato(data_dir, basi)
            if collegati is not None:
                atti = catalogo(_normativa_db()) + collegati
                if vista == "storico":
                    sostituzioni = alias_originali_storici()
                    atti = [atto for atto in atti if atto["id"] not in sostituzioni]
                stato = _normativa_db().stat()
                return _catalogo_compresso("storico" if vista == "storico" else "tutti", collegati, lambda: {"ok": True, "items": elenco_leggero(atti)},
                                           impronta=(str(_normativa_db()), stato.st_size, stato.st_mtime_ns,
                                                     tuple(sorted(sostituzioni)) if vista == "storico" else ()))
        return jsonify(ok=False, message="Il catalogo delle fonti si sta aggiornando."), 503, {"Retry-After": "5"}
    except (FileNotFoundError, OSError, sqlite3.Error) as exc:
        return _archivio_non_disponibile(exc, "L'archivio dei codici e delle leggi non è ancora disponibile.")


@api_v1_ricerca_legale.get("/normativa/articoli")
@_richiedi_auth
def normativa_articoli():
    denied = _permesso_normativa()
    if denied is not None:
        return denied
    from lex.normativa.consultazione import articoli
    try:
        act = int(request.args.get("act") or 0)
        offset = max(0, int(request.args.get("offset") or 0))
        from lex.normativa.cerdef_biblioteca import is_linked, linked_articles
        if request.args.get("vista") == "vigenti":
            result = linked_articles(act, query=request.args.get("q", ""),
                                     article=request.args.get("article", ""), offset=offset, vigente=True,
                                     category=request.args.get("category", ""))
            return jsonify(ok=True, **result)
        if request.args.get("vista") == "storico" and not act:
            from lex.normativa.cerdef_biblioteca import ricerca_storica
            result = ricerca_storica(_normativa_db(), query=request.args.get("q", ""),
                                      article=request.args.get("article", ""), category=request.args.get("category", ""),
                                      offset=offset)
            return jsonify(ok=True, **result)
        if act and request.args.get("vista") == "storico":
            from lex.normativa.cerdef_biblioteca import alias_originali_storici
            sostituzioni = alias_originali_storici()
            act = sostituzioni.get(act, act)
        if is_linked(act):
            result = linked_articles(act, query=request.args.get("q", ""), article=request.args.get("article", ""), offset=offset)
            return jsonify(ok=True, **result)
        # «materia» (ripetibile) limita la ricerca alle materie della pratica: pannello Normativa del fascicolo.
        materie = tuple(m.strip()[:80] for m in request.args.getlist("materia")[:6] if m.strip())
        result = articoli(_normativa_db(), act=act, query=request.args.get("q", ""),
            article=request.args.get("article", ""), category=request.args.get("category", ""), offset=offset,
            includi_archivio_generale=True, materie=materie)
        return jsonify(ok=True, **result)
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400
    except (FileNotFoundError, OSError, sqlite3.Error) as exc:
        return _archivio_non_disponibile(exc, "Archivio non disponibile. Riprova fra poco.")


@api_v1_ricerca_legale.get("/normativa/articoli/<int:article_id>")
@_richiedi_auth
def normativa_articolo(article_id):
    denied = _permesso_normativa()
    if denied is not None:
        return denied
    from lex.normativa.consultazione import dettaglio
    try:
        from lex.normativa.cerdef_biblioteca import is_linked, linked_article
        item = linked_article(article_id) if is_linked(article_id) else dettaglio(
            _normativa_db(), article_id, includi_archivio_generale=True)
        if item is None:
            return jsonify(ok=False, message="Articolo non trovato nell'archivio."), 404
        return jsonify(ok=True, item=item)
    except (FileNotFoundError, OSError, sqlite3.Error) as exc:
        return _archivio_non_disponibile(exc, "Testo non disponibile. Riprova fra poco.")


@api_v1_ricerca_legale.get("/normativa/visualizza")
@_richiedi_auth
def normativa_visualizza():
    """Documento puntuale nel lettore nativo, senza incorporare siti esterni."""
    denied = _permesso_normativa()
    if denied is not None:
        return denied
    from flask import make_response
    from web.services.normative_article_reader import ArticoloCambiato, documento_html, risolvi
    try:
        from lex.normativa.cerdef_biblioteca import is_linked, linked_archive, linked_article
        ident = int(request.args.get("id") or 0)
        database = _normativa_db()
        linked = None
        if is_linked(ident):
            linked = linked_article(ident)
            if linked is None:
                raise LookupError("Articolo collegato non disponibile.")
            database, base = linked_archive(ident)
            ident -= base
        item = risolvi(database, ident=ident,
                       atto=request.args.get("atto", ""), articolo=request.args.get("articolo", ""),
                       url=request.args.get("url", ""), sha=request.args.get("sha", ""))
        if linked is not None:
            item.update(number=linked["number"], title=linked["title"])
        response = make_response(documento_html(item))
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except ArticoloCambiato as exc:
        return jsonify(ok=False, message=str(exc)), 409
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400
    except LookupError as exc:
        return jsonify(ok=False, message=str(exc)), 404
    except (OSError, sqlite3.Error):
        return jsonify(ok=False, message="Archivio non disponibile. Riprova fra poco."), 503
