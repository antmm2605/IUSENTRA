"""
web/blueprints/export_csv.py — Export dati in CSV per commercialista/archiviazione.

URL base: /export/
Tutti gli endpoint restituiscono file .csv UTF-8 con BOM (compatibile Excel italiano).
"""
from __future__ import annotations

import csv
import io
from datetime import date

from flask import Blueprint, Response, g, redirect, url_for, current_app

from web.services.react_fascicoli_bridge import payment_summary_for_fascicolo
from web.helpers import get_agenda, get_clienti, get_fascicoli, get_fatturazione as _shared_get_fatturazione, get_scadenziario

export_csv = Blueprint("export_csv", __name__, url_prefix="/export")


def _richiedi_login(f):
    from functools import wraps
    @wraps(f)
    def w(*a, **kw):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


def _csv_response(rows: list[dict], filename: str) -> Response:
    """Restituisce una Response CSV con BOM UTF-8."""
    if not rows:
        buf = io.StringIO()
        buf.write("Nessun dato\n")
        data = "\ufeff" + buf.getvalue()
        return Response(data, mimetype="text/csv; charset=utf-8-sig",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys(), lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    data = "\ufeff" + buf.getvalue()
    return Response(data, mimetype="text/csv; charset=utf-8-sig",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ================================================================ CLIENTI

@export_csv.route("/clienti.csv")
@_richiedi_login
def clienti_csv():
    rows = []
    for c in get_clienti().tutti():
        r = getattr(c, "recapiti", None)
        rows.append({
            "ID":                c.id,
            "Tipo":              c.tipo.value if c.tipo else "",
            "Nome/Ragione soc.": c.nome_completo,
            "Codice Fiscale":    c.codice_fiscale or "",
            "Partita IVA":       getattr(c, "partita_iva", "") or "",
            "Data nascita":      c.data_nascita or "",
            "Indirizzo":         c.indirizzo or "",
            "Cellulare":         r.cellulare if r else "",
            "Telefono":          r.telefono if r else "",
            "Email":             r.email if r else "",
            "Stato":             c.stato.value if c.stato else "",
            "Consenso privacy":  "Sì" if getattr(c, "consenso_trattamento", False) else "No",
            "Data consenso":     getattr(c, "data_consenso", "") or "",
        })
    return _csv_response(rows, f"clienti_{date.today()}.csv")


# ================================================================ FASCICOLI

@export_csv.route("/fascicoli.csv")
@_richiedi_login
def fascicoli_csv():
    gc = get_clienti()
    rows = []
    for f in get_fascicoli().tutti(archiviati=True):
        cliente = gc.get(f.id_cliente) if f.id_cliente else None
        payment_summary = payment_summary_for_fascicolo(f)
        payments = payment_summary["items"]
        rows.append({
            "ID":               f.id,
            "Numero RG":        f.numero_rg or "",
            "Titolo":           f.titolo,
            "Tipo":             f.tipo.value if f.tipo else "",
            "Stato":            f.stato.value if f.stato else "",
            "Tribunale":        getattr(f, "tribunale", "") or "",
            "Cliente":          cliente.nome_completo if cliente else "",
            "Data apertura":    getattr(f, "data_apertura", "") or "",
            "Data chiusura":    getattr(f, "data_chiusura", "") or "",
            "Avvocato ref.":    getattr(f, "avvocato_referente", "") or "",
            "Descrizione":      getattr(f, "descrizione", "") or "",
            "Contributo unificato - stato": payments["contributo_unificato"]["statusLabel"],
            "Contributo unificato - importo": payments["contributo_unificato"]["importoLabel"],
            "Spese/esborsi - stato": payments["fondo_spese"]["statusLabel"],
            "Spese/esborsi - importo": payments["fondo_spese"]["importoLabel"],
            "Liquidazione giudice - stato": payments["liquidazione_giudice"]["statusLabel"],
            "Liquidazione giudice - importo": payments["liquidazione_giudice"]["importoLabel"],
            "Parcella - stato": payments["parcella"]["statusLabel"],
            "Parcella - importo": payments["parcella"]["importoLabel"],
            "Totale registrato": payment_summary["totaleRegistratoLabel"],
            "Ultimo aggiornamento economico": payment_summary["updatedAtLabel"],
            "Operatore ultimo aggiornamento": payment_summary["updatedBy"],
        })
    return _csv_response(rows, f"fascicoli_{date.today()}.csv")


# ================================================================ AGENDA

@export_csv.route("/agenda.csv")
@_richiedi_login
def agenda_csv():
    gc = get_clienti()
    rows = []
    for a in get_agenda().tutti():
        cliente = gc.get(a.id_cliente) if getattr(a, "id_cliente", None) else None
        rows.append({
            "ID":         a.id,
            "Titolo":     a.titolo,
            "Tipo":       a.tipo.value if a.tipo else "",
            "Data":       a.data_ora_dt.date().isoformat(),
            "Ora":        a.data_ora_dt.strftime("%H:%M"),
            "Luogo":      getattr(a, "luogo", "") or "",
            "Cliente":    cliente.nome_completo if cliente else "",
            "Stato":      a.stato.value if a.stato else "",
            "Descrizione": getattr(a, "descrizione", "") or "",
        })
    return _csv_response(rows, f"agenda_{date.today()}.csv")


# ================================================================ SCADENZE

@export_csv.route("/scadenze.csv")
@_richiedi_login
def scadenze_csv():
    rows = []
    for s in get_scadenziario().tutte():
        rows.append({
            "ID":           s.id,
            "Titolo":       s.titolo,
            "Scadenza":     s.scadenza.isoformat() if s.scadenza else "",
            "Priorità":     s.priorita.value if s.priorita else "",
            "Stato":        s.stato.value if s.stato else "",
            "Perentorio":   "Sì" if s.perentorio else "No",
            "ID Fascicolo": getattr(s, "id_fascicolo", "") or "",
            "Descrizione":  getattr(s, "descrizione", "") or "",
            "Note":         getattr(s, "note", "") or "",
        })
    return _csv_response(rows, f"scadenze_{date.today()}.csv")


# ================================================================ FATTURAZIONE

@export_csv.route("/fatturazione.csv")
@_richiedi_login
def fatturazione_csv():
    gf = _shared_get_fatturazione()
    gc = get_clienti()
    rows = []
    for p in gf.tutte():
        cliente = gc.get(p.id_cliente) if p.id_cliente else None
        rows.append({
            "Numero":          p.numero,
            "Data emissione":  p.data_emissione,
            "Data scadenza":   p.data_scadenza or "",
            "Cliente":         cliente.nome_completo if cliente else "",
            "CF/PIVA cliente": (cliente.codice_fiscale if cliente else "") or "",
            "Imponibile":      f"{p.imponibile:.2f}",
            "Cassa Forense":   f"{p.cassa_forense:.2f}",
            "IVA":             f"{p.iva:.2f}",
            "Bollo":           f"{p.bollo:.2f}",
            "Ritenuta":        f"{p.ritenuta:.2f}",
            "Totale":          f"{p.totale:.2f}",
            "Stato":           p.stato.value,
            "Data pagamento":  p.data_pagamento or "",
            "Metodo pagamento": p.metodo_pagamento or "",
            "Note":            p.note or "",
        })
    return _csv_response(rows, f"parcelle_{date.today()}.csv")
