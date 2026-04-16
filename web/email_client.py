"""
web/blueprints/api_v1.py — REST API v1

Base URL: /api/v1/

Autenticazione (una delle due):
  - Cookie di sessione web (stesso browser dell'app)
  - Header:  X-API-Key: <valore di PCT_API_KEY>

Formato risposte:
  Successo:    {"data": ..., "meta": {...}}          HTTP 2xx
  Errore:      {"errore": "...", "codice": NNN}      HTTP 4xx/5xx
  Lista:       {"data": [...], "meta": {"total": N, "page": P, "per_page": PP, "pages": T}}

CORS: abilitato per tutti gli origin (per app mobile future).
"""
from __future__ import annotations

from functools import wraps

from flask import Blueprint, g, jsonify, request, current_app
from pct import __version__ as APP_VERSION

from web.helpers import (
    get_agenda,
    get_clienti,
    get_fascicoli,
    get_scadenziario,
    get_indice,
    pagina,
)

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


# ================================================================ Auth helper

def _richiedi_auth(f):
    """Decorator: blocca la route se non autenticato (sessione o API key)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        # 1) Sessione web attiva
        if g.get("utente_corrente"):
            return f(*args, **kwargs)
        # 2) X-API-Key header
        api_key = current_app.config.get("API_KEY", "")
        if api_key and request.headers.get("X-API-Key") == api_key:
            return f(*args, **kwargs)
        return _err("Autenticazione richiesta. Usa la sessione web o l'header X-API-Key.", 401)
    return wrapper


# ================================================================ Helpers risposta

def _ok(data, *, status=200, **extra):
    """Risposta di successo con dato singolo."""
    body = {"data": data}
    body.update(extra)
    return jsonify(body), status


def _lista(items: list, page: int, per_page: int):
    """Risposta di successo con lista paginata."""
    p = pagina(items, page, per_page)
    return jsonify({"data": p["data"], "meta": p["meta"]}), 200


def _err(messaggio: str, status: int = 400):
    return jsonify({"errore": messaggio, "codice": status}), status


# ================================================================ CORS

@api_v1.after_request
def _cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response

@api_v1.route("/<path:_>", methods=["OPTIONS"])
@api_v1.route("/", methods=["OPTIONS"])
def _preflight(_=""):
    return "", 204


# ================================================================ INFO

@api_v1.route("/", methods=["GET"])
def info():
    """Informazioni generali sull'API."""
    return _ok({
        "app": current_app.config.get("STUDIO_NOME", "IUSENTRA"),
        "version": APP_VERSION,
        "autenticazione": ["session", "X-API-Key"],
        "endpoints": {
            "clienti":   "/api/v1/clienti",
            "fascicoli": "/api/v1/fascicoli",
            "agenda":    "/api/v1/agenda",
            "scadenze":  "/api/v1/scadenze",
            "dashboard": "/api/v1/dashboard",
            "cerca":     "/api/v1/cerca",
        },
    })


# ================================================================ CLIENTI

@api_v1.route("/clienti", methods=["GET"])
@_richiedi_auth
def lista_clienti():
    """
    GET /api/v1/clienti

    Query params:
      q         — ricerca testuale
      tipo      — PF | PG
      stato     — ATTIVO | INATTIVO | ...
      page      — numero pagina (default 1)
      per_page  — risultati per pagina (default 20, max 100)
    """
    gc = get_clienti()
    q = request.args.get("q", "").strip()
    tipo = request.args.get("tipo", "")
    stato = request.args.get("stato", "")

    clienti = gc.cerca(testo=q) if q else gc.tutti()

    if tipo:
        clienti = [c for c in clienti if c.tipo.value == tipo]
    if stato:
        clienti = [c for c in clienti if c.stato.value == stato]

    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    p = pagina([c.to_dict() for c in clienti], page, per_page)
    return jsonify({"data": p["data"], "meta": p["meta"]}), 200


@api_v1.route("/clienti/<id_cliente>", methods=["GET"])
@_richiedi_auth
def get_cliente(id_cliente):
    """GET /api/v1/clienti/<id>"""
    c = get_clienti().get(id_cliente)
    if not c:
        return _err("Cliente non trovato.", 404)
    return _ok(c.to_dict())


# ================================================================ FASCICOLI

@api_v1.route("/fascicoli", methods=["GET"])
@_richiedi_auth
def lista_fascicoli():
    """
    GET /api/v1/fascicoli

    Query params:
      q           — ricerca testuale
      stato       — APERTO | CHIUSO | ARCHIVIATO | ...
      tipo        — CIVILE | PENALE | ...
      archiviati  — 1 per includere archiviati
      page, per_page
    """
    gf = get_fascicoli()
    q          = request.args.get("q", "").strip()
    stato      = request.args.get("stato", "")
    tipo       = request.args.get("tipo", "")
    archiviati = request.args.get("archiviati", "0") == "1"

    fascicoli = gf.cerca(testo=q, archiviati=archiviati) if q else gf.tutti(archiviati=archiviati)

    if stato:
        fascicoli = [f for f in fascicoli if f.stato.value == stato]
    if tipo:
        fascicoli = [f for f in fascicoli if f.tipo.value == tipo]

    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    p = pagina([f.to_dict() for f in fascicoli], page, per_page)
    return jsonify({"data": p["data"], "meta": p["meta"]}), 200


@api_v1.route("/fascicoli/<id_fasc>", methods=["GET"])
@_richiedi_auth
def get_fascicolo(id_fasc):
    """GET /api/v1/fascicoli/<id>"""
    f = get_fascicoli().get(id_fasc)
    if not f:
        return _err("Fascicolo non trovato.", 404)
    return _ok(f.to_dict())


# ================================================================ AGENDA

@api_v1.route("/agenda", methods=["GET"])
@_richiedi_auth
def lista_agenda():
    """
    GET /api/v1/agenda

    Query params:
      data_inizio — YYYY-MM-DD  (default oggi)
      data_fine   — YYYY-MM-DD  (default +30 giorni)
      tipo        — UDIENZA | CONSULTAZIONE | DEPOSITO | ...
      page, per_page
    """
    from datetime import date, timedelta

    ag = get_agenda()
    oggi = date.today()

    data_inizio_str = request.args.get("data_inizio", "")
    data_fine_str   = request.args.get("data_fine", "")
    tipo            = request.args.get("tipo", "")

    try:
        data_inizio = date.fromisoformat(data_inizio_str) if data_inizio_str else oggi
        data_fine   = date.fromisoformat(data_fine_str)   if data_fine_str   else oggi + timedelta(days=30)
    except ValueError:
        return _err("Formato data non valido. Usa YYYY-MM-DD.", 400)

    appuntamenti = [
        a for a in ag.tutti()
        if data_inizio <= a.data_ora_dt.date() <= data_fine
    ]

    if tipo:
        appuntamenti = [a for a in appuntamenti if a.tipo.value == tipo]

    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    p = pagina([a.to_dict() for a in appuntamenti], page, per_page)
    return jsonify({"data": p["data"], "meta": p["meta"]}), 200


# ================================================================ SCADENZE

@api_v1.route("/scadenze", methods=["GET"])
@_richiedi_auth
def lista_scadenze():
    """
    GET /api/v1/scadenze

    Query params:
      stato       — APERTA | COMPLETATA | SCADUTA
      priorita    — CRITICA | ALTA | MEDIA | BASSA
      perentorio  — 1 | 0
      entro_giorni — intero (es. 7 → solo scadenze entro 7 giorni)
      page, per_page
    """
    gs = get_scadenziario()
    stato        = request.args.get("stato", "")
    priorita     = request.args.get("priorita", "")
    perentorio   = request.args.get("perentorio", "")
    entro_giorni = request.args.get("entro_giorni", "")

    if entro_giorni:
        try:
            scadenze = gs.imminenti(entro_giorni=int(entro_giorni))
        except (ValueError, TypeError):
            return _err("entro_giorni deve essere un intero.", 400)
    else:
        scadenze = gs.tutte()

    if stato:
        scadenze = [s for s in scadenze if s.stato.value == stato]
    if priorita:
        scadenze = [s for s in scadenze if s.priorita.value == priorita]
    if perentorio:
        flag = perentorio == "1"
        scadenze = [s for s in scadenze if s.perentorio == flag]

    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    p = pagina([s.to_dict() for s in scadenze], page, per_page)
    return jsonify({"data": p["data"], "meta": p["meta"]}), 200


@api_v1.route("/scadenze/<id_sc>/completa", methods=["POST"])
@_richiedi_auth
def completa_scadenza_api(id_sc):
    """POST /api/v1/scadenze/<id>/completa   body JSON: {"note": "..."}"""
    gs = get_scadenziario()
    payload = request.get_json(silent=True) or {}
    note = payload.get("note", "")
    try:
        gs.completa(id_sc, note=note)
    except ValueError as e:
        return _err(str(e), 404)
    return _ok({"id": id_sc, "stato": "COMPLETATA"})


# ================================================================ DASHBOARD

@api_v1.route("/dashboard", methods=["GET"])
@_richiedi_auth
def dashboard():
    """
    GET /api/v1/dashboard

    Restituisce un riepilogo aggregato per la schermata home dell'app.
    """
    from datetime import date

    oggi = date.today()
    ag = get_agenda()
    gs = get_scadenziario()
    gc = get_clienti()
    gf = get_fascicoli()

    apps_oggi     = ag.per_giorno(oggi)
    reminder      = ag.prossimi_reminder(entro_minuti=120)
    sc_critiche   = gs.imminenti(entro_giorni=3)
    stats_sc      = gs.statistiche()
    stats_clienti = gc.statistiche()
    stats_fasc    = gf.statistiche()

    return _ok({
        "data": oggi.isoformat(),
        "appuntamenti_oggi": [a.to_dict() for a in apps_oggi],
        "reminder_imminenti": [a.to_dict() for a in reminder],
        "scadenze_critiche": [s.to_dict() for s in sc_critiche],
        "statistiche": {
            "scadenziario": stats_sc,
            "clienti":      stats_clienti,
            "fascicoli":    stats_fasc,
        },
    })


# ================================================================ CERCA

@api_v1.route("/cerca", methods=["GET"])
@_richiedi_auth
def cerca():
    """
    GET /api/v1/cerca?q=<testo>

    Ricerca full-text su fascicoli, clienti, appuntamenti, scadenze.
    Restituisce al massimo 50 risultati aggregati.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return _err("Parametro 'q' obbligatorio.", 400)
    if len(q) < 2:
        return _err("La ricerca deve contenere almeno 2 caratteri.", 400)

    try:
        risultati = get_indice().cerca(q, limit=50)
    except Exception:
        risultati = []

    return _ok(risultati, meta={"query": q, "total": len(risultati)})
