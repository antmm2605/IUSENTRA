"""
web/blueprints/statistiche.py — Dashboard statistiche avanzate.

URL base: /statistiche/
Grafici Chart.js: fatturato mensile, fascicoli per tipo, clienti per mese,
scadenze per priorità, appuntamenti per tipo.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from collections import defaultdict

from flask import Blueprint, g, jsonify, redirect, render_template, url_for, current_app

from web.helpers import get_clienti, get_fascicoli, get_agenda, get_scadenziario

statistiche = Blueprint("statistiche", __name__, url_prefix="/statistiche")


def _richiedi_login(f):
    from functools import wraps
    @wraps(f)
    def w(*a, **kw):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


# ================================================================ PAGINA PRINCIPALE

@statistiche.route("/", methods=["GET"])
@_richiedi_login
def index():
    return render_template("statistiche/index.html")


# ================================================================ API DATI

@statistiche.route("/api/fatturato-mensile")
@_richiedi_login
def api_fatturato_mensile():
    from pct.fatturazione import GestioneFatturazione, StatoParcella
    gf = GestioneFatturazione(
        db_path=current_app.config.get("FATTURAZIONE_DB", "./fatturazione/parcelle.json")
    )
    anno = date.today().year
    mensile = defaultdict(float)
    mensile_incassato = defaultdict(float)

    for p in gf.tutte():
        if not p.data_emissione.startswith(str(anno)):
            continue
        try:
            mese = int(p.data_emissione[5:7])
        except (ValueError, IndexError):
            continue
        if p.stato not in (StatoParcella.ANNULLATA,):
            mensile[mese] += p.totale
        if p.stato == StatoParcella.PAGATA:
            mensile_incassato[mese] += p.totale

    mesi = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"]
    return jsonify({
        "labels": mesi,
        "fatturato": [round(mensile.get(i+1, 0), 2) for i in range(12)],
        "incassato":  [round(mensile_incassato.get(i+1, 0), 2) for i in range(12)],
    })


@statistiche.route("/api/fascicoli-per-tipo")
@_richiedi_login
def api_fascicoli_per_tipo():
    gf = get_fascicoli()
    conteggio = defaultdict(int)
    for f in gf.tutti():
        conteggio[f.tipo.value] += 1
    return jsonify({
        "labels": list(conteggio.keys()),
        "data":   list(conteggio.values()),
    })


@statistiche.route("/api/fascicoli-per-stato")
@_richiedi_login
def api_fascicoli_per_stato():
    gf = get_fascicoli()
    conteggio = defaultdict(int)
    for f in gf.tutti(archiviati=True):
        conteggio[f.stato.value] += 1
    return jsonify({
        "labels": list(conteggio.keys()),
        "data":   list(conteggio.values()),
    })


@statistiche.route("/api/clienti-per-mese")
@_richiedi_login
def api_clienti_per_mese():
    gc = get_clienti()
    anno = date.today().year
    mensile = defaultdict(int)
    for c in gc.tutti():
        data_reg = getattr(c, "data_registrazione", None) or getattr(c, "creato_il", None) or ""
        if data_reg and data_reg.startswith(str(anno)):
            try:
                mese = int(data_reg[5:7])
                mensile[mese] += 1
            except (ValueError, IndexError):
                pass
    mesi = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"]
    return jsonify({
        "labels": mesi,
        "data":   [mensile.get(i+1, 0) for i in range(12)],
    })


@statistiche.route("/api/scadenze-per-priorita")
@_richiedi_login
def api_scadenze_per_priorita():
    gs = get_scadenziario()
    conteggio = defaultdict(int)
    for s in gs.tutte():
        conteggio[s.priorita.value] += 1
    return jsonify({
        "labels": list(conteggio.keys()),
        "data":   list(conteggio.values()),
    })


@statistiche.route("/api/appuntamenti-per-tipo")
@_richiedi_login
def api_appuntamenti_per_tipo():
    ag = get_agenda()
    anno = date.today().year
    conteggio = defaultdict(int)
    for a in ag.tutti():
        if a.data_ora_dt.year == anno:
            conteggio[a.tipo.value] += 1
    return jsonify({
        "labels": list(conteggio.keys()),
        "data":   list(conteggio.values()),
    })


@statistiche.route("/api/riepilogo")
@_richiedi_login
def api_riepilogo():
    from pct.fatturazione import GestioneFatturazione
    gc = get_clienti()
    gf = get_fascicoli()
    gs = get_scadenziario()
    ag = get_agenda()
    gfatt = GestioneFatturazione(
        db_path=current_app.config.get("FATTURAZIONE_DB", "./fatturazione/parcelle.json")
    )
    oggi = date.today()
    stats_clienti  = gc.statistiche()
    stats_fascicoli = gf.statistiche()
    stats_scadenze = gs.statistiche()
    stats_fatt     = gfatt.statistiche()
    apps_oggi = len(ag.per_giorno(oggi))
    sc_oggi   = sum(1 for s in gs.tutte() if s.scadenza == oggi)

    return jsonify({
        "clienti":    stats_clienti,
        "fascicoli":  stats_fascicoli,
        "scadenze":   stats_scadenze,
        "fatturato":  stats_fatt,
        "oggi": {
            "appuntamenti": apps_oggi,
            "scadenze":     sc_oggi,
        },
    })
