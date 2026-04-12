"""
web/blueprints/statistiche.py — Dashboard statistiche avanzate.

URL base: /statistiche/
Grafici Chart.js: fatturato mensile, fascicoli per tipo/stato, clienti per mese,
scadenze per priorità, appuntamenti per tipo, trend depositi, produttività.
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


def _get_fatturazione():
    from pct.fatturazione import GestioneFatturazione
    return GestioneFatturazione(
        db_path=current_app.config.get("FATTURAZIONE_DB", "./fatturazione/parcelle.json")
    )


# ================================================================ PAGINA PRINCIPALE

@statistiche.route("/", methods=["GET"])
@_richiedi_login
def index():
    return render_template("statistiche/index.html", oggi=date.today())


# ================================================================ API DATI — tutte con try/except

@statistiche.route("/api/fatturato-mensile")
@_richiedi_login
def api_fatturato_mensile():
    try:
        from pct.fatturazione import StatoParcella
        gf = _get_fatturazione()
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

        mesi = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
                "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
        return jsonify({
            "labels": mesi,
            "fatturato": [round(mensile.get(i + 1, 0), 2) for i in range(12)],
            "incassato": [round(mensile_incassato.get(i + 1, 0), 2) for i in range(12)],
        })
    except Exception as e:
        current_app.logger.exception("Errore api_fatturato_mensile: %s", e)
        mesi = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
                "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
        return jsonify({"labels": mesi, "fatturato": [0]*12, "incassato": [0]*12})


@statistiche.route("/api/fascicoli-per-tipo")
@_richiedi_login
def api_fascicoli_per_tipo():
    try:
        gf = get_fascicoli()
        conteggio = defaultdict(int)
        for f in gf.tutti():
            conteggio[f.tipo.value] += 1
        return jsonify({"labels": list(conteggio.keys()),
                        "data": list(conteggio.values())})
    except Exception as e:
        current_app.logger.exception("Errore api_fascicoli_per_tipo: %s", e)
        return jsonify({"labels": [], "data": []})


@statistiche.route("/api/fascicoli-per-stato")
@_richiedi_login
def api_fascicoli_per_stato():
    try:
        gf = get_fascicoli()
        conteggio = defaultdict(int)
        for f in gf.tutti(archiviati=True):
            conteggio[f.stato.value] += 1
        return jsonify({"labels": list(conteggio.keys()),
                        "data": list(conteggio.values())})
    except Exception as e:
        current_app.logger.exception("Errore api_fascicoli_per_stato: %s", e)
        return jsonify({"labels": [], "data": []})


@statistiche.route("/api/clienti-per-mese")
@_richiedi_login
def api_clienti_per_mese():
    try:
        gc = get_clienti()
        anno = date.today().year
        mensile = defaultdict(int)
        for c in gc.tutti():
            data_reg = (getattr(c, "data_registrazione", None)
                        or getattr(c, "creato_il", None) or "")
            if data_reg and data_reg.startswith(str(anno)):
                try:
                    mese = int(data_reg[5:7])
                    mensile[mese] += 1
                except (ValueError, IndexError):
                    pass
        mesi = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
                "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
        return jsonify({"labels": mesi,
                        "data": [mensile.get(i + 1, 0) for i in range(12)]})
    except Exception as e:
        current_app.logger.exception("Errore api_clienti_per_mese: %s", e)
        mesi = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
                "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
        return jsonify({"labels": mesi, "data": [0]*12})


@statistiche.route("/api/scadenze-per-priorita")
@_richiedi_login
def api_scadenze_per_priorita():
    try:
        gs = get_scadenziario()
        conteggio = defaultdict(int)
        for s in gs.tutte():
            conteggio[s.priorita.value] += 1
        return jsonify({"labels": list(conteggio.keys()),
                        "data": list(conteggio.values())})
    except Exception as e:
        current_app.logger.exception("Errore api_scadenze_per_priorita: %s", e)
        return jsonify({"labels": [], "data": []})


@statistiche.route("/api/appuntamenti-per-tipo")
@_richiedi_login
def api_appuntamenti_per_tipo():
    try:
        ag = get_agenda()
        anno = date.today().year
        conteggio = defaultdict(int)
        for a in ag.tutti():
            if a.data_ora_dt.year == anno:
                conteggio[a.tipo.value] += 1
        return jsonify({"labels": list(conteggio.keys()),
                        "data": list(conteggio.values())})
    except Exception as e:
        current_app.logger.exception("Errore api_appuntamenti_per_tipo: %s", e)
        return jsonify({"labels": [], "data": []})


@statistiche.route("/api/riepilogo")
@_richiedi_login
def api_riepilogo():
    try:
        gc = get_clienti()
        gf = get_fascicoli()
        gs = get_scadenziario()
        ag = get_agenda()
        gfatt = _get_fatturazione()
        oggi = date.today()
        stats_clienti = gc.statistiche()
        stats_fascicoli = gf.statistiche()
        stats_scadenze = gs.statistiche()
        stats_fatt = gfatt.statistiche()
        apps_oggi = len(ag.per_giorno(oggi))
        sc_oggi = sum(1 for s in gs.tutte() if s.scadenza == oggi)

        return jsonify({
            "clienti": stats_clienti,
            "fascicoli": stats_fascicoli,
            "scadenze": stats_scadenze,
            "fatturato": stats_fatt,
            "oggi": {"appuntamenti": apps_oggi, "scadenze": sc_oggi},
        })
    except Exception as e:
        current_app.logger.exception("Errore api_riepilogo: %s", e)
        return jsonify({
            "clienti": {"totale": 0},
            "fascicoli": {"totale": 0, "attivi": 0, "aperti": 0},
            "scadenze": {"totale": 0, "critiche": 0, "scadute": 0, "aperte": 0},
            "fatturato": {"fatturato_lordo": 0, "da_incassare": 0, "incassato": 0},
            "oggi": {"appuntamenti": 0, "scadenze": 0},
        })


@statistiche.route("/api/depositi-trend")
@_richiedi_login
def api_depositi_trend():
    """Trend depositi PCT per mese (anno corrente)."""
    try:
        gf = get_fascicoli()
        anno = date.today().year
        depositi_mese = defaultdict(int)
        accettati_mese = defaultdict(int)
        rifiutati_mese = defaultdict(int)

        for f in gf.tutti():
            for att in getattr(f, "attivita", []) or []:
                data_att = att.get("data", "") if isinstance(att, dict) else getattr(att, "data", "")
                tipo_att = att.get("tipo", "") if isinstance(att, dict) else getattr(att, "tipo", "")
                if not data_att or not data_att.startswith(str(anno)):
                    continue
                try:
                    mese = int(data_att[5:7])
                except (ValueError, IndexError):
                    continue
                tipo_lower = str(tipo_att).lower()
                if "deposito" in tipo_lower or "deposita" in tipo_lower:
                    depositi_mese[mese] += 1
                if "accettat" in tipo_lower:
                    accettati_mese[mese] += 1
                if "rifiutat" in tipo_lower:
                    rifiutati_mese[mese] += 1

        mesi = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
                "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
        return jsonify({
            "labels": mesi,
            "depositi": [depositi_mese.get(i + 1, 0) for i in range(12)],
            "accettati": [accettati_mese.get(i + 1, 0) for i in range(12)],
            "rifiutati": [rifiutati_mese.get(i + 1, 0) for i in range(12)],
        })
    except Exception as e:
        current_app.logger.exception("Errore api_depositi_trend: %s", e)
        mesi = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
                "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
        return jsonify({"labels": mesi, "depositi": [0]*12,
                        "accettati": [0]*12, "rifiutati": [0]*12})


@statistiche.route("/api/produttivita")
@_richiedi_login
def api_produttivita():
    """KPI di produttività: durata media fascicoli, tasso chiusura, scadenze rispettate."""
    try:
        gf = get_fascicoli()
        gs = get_scadenziario()
        oggi = date.today()

        fascicoli = gf.tutti(archiviati=True)
        totale_fasc = len(fascicoli)
        chiusi = 0
        durate = []
        for f in fascicoli:
            data_ap = getattr(f, "data_apertura", None) or getattr(f, "creato_il", None)
            stato_v = f.stato.value.upper() if hasattr(f.stato, "value") else str(f.stato).upper()
            if stato_v in ("CHIUSO", "DEFINITO", "ARCHIVIATO"):
                chiusi += 1
                data_ch = getattr(f, "data_chiusura", None) or getattr(f, "aggiornato_il", None)
                if data_ap and data_ch:
                    try:
                        d1 = datetime.fromisoformat(str(data_ap)[:10])
                        d2 = datetime.fromisoformat(str(data_ch)[:10])
                        durate.append((d2 - d1).days)
                    except (ValueError, TypeError):
                        pass

        scadenze = list(gs.tutte())
        sc_totale = len(scadenze)
        sc_completate = 0
        sc_rispettate = 0
        sc_scadute = 0
        for s in scadenze:
            completata = getattr(s, "completata", False)
            if completata:
                sc_completate += 1
                data_comp = getattr(s, "data_completamento", None)
                if data_comp and s.scadenza:
                    try:
                        d_comp = datetime.fromisoformat(str(data_comp)[:10]).date()
                        d_scad = s.scadenza if isinstance(s.scadenza, date) else datetime.fromisoformat(str(s.scadenza)[:10]).date()
                        if d_comp <= d_scad:
                            sc_rispettate += 1
                    except (ValueError, TypeError):
                        sc_rispettate += 1
                else:
                    sc_rispettate += 1
            else:
                scad = s.scadenza if isinstance(s.scadenza, date) else None
                if scad and scad < oggi:
                    sc_scadute += 1

        durata_media = round(sum(durate) / len(durate)) if durate else 0
        tasso_chiusura = round(chiusi / totale_fasc * 100) if totale_fasc else 0
        tasso_scadenze = round(sc_rispettate / sc_completate * 100) if sc_completate else 0

        return jsonify({
            "durata_media_gg": durata_media,
            "tasso_chiusura_pct": tasso_chiusura,
            "fascicoli_chiusi": chiusi,
            "fascicoli_totali": totale_fasc,
            "tasso_scadenze_rispettate_pct": tasso_scadenze,
            "scadenze_completate": sc_completate,
            "scadenze_totali": sc_totale,
            "scadenze_scadute": sc_scadute,
        })
    except Exception as e:
        current_app.logger.exception("Errore api_produttivita: %s", e)
        return jsonify({
            "durata_media_gg": 0, "tasso_chiusura_pct": 0,
            "fascicoli_chiusi": 0, "fascicoli_totali": 0,
            "tasso_scadenze_rispettate_pct": 0,
            "scadenze_completate": 0, "scadenze_totali": 0,
            "scadenze_scadute": 0,
        })
