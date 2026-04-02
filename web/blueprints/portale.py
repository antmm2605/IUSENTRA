"""
web/blueprints/portale.py — Portale self-service per il cliente.

URL base: /portale/<token>
Nessuna autenticazione richiesta — l'accesso è garantito dal token sicuro.
"""
from __future__ import annotations

import os
from datetime import date

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, send_file, url_for, current_app)

from web.helpers import get_clienti, get_fascicoli, get_agenda, get_scadenziario
from pct.economico_context import riepilogo_contesto_economico
from pct.legal_intelligence import costruisci_tracker_fascicoli

portale = Blueprint("portale", __name__, url_prefix="/portale")


# ---------------------------------------------------------------- helper locale

def _get_portale():
    from pct.portale import GestionePortale
    return GestionePortale(
        db_path=current_app.config.get("PORTALE_DB", "./portale/portali.json"),
        uploads_dir=current_app.config.get("PORTALE_UPLOADS", "./portale/uploads"),
    )


def _get_preventivi():
    from pct.preventivi import GestionePreventivi
    return GestionePreventivi(
        db_path=current_app.config.get("PREVENTIVI_DB", "./preventivi/preventivi.json")
    )


def _get_fatturazione():
    from pct.fatturazione import GestioneFatturazione
    return GestioneFatturazione(
        db_path=current_app.config.get("FATTURAZIONE_DB", "./fatturazione/parcelle.json")
    )


def _download_requested() -> bool:
    value = (request.args.get("download") or "").strip().lower()
    return value in {"1", "true", "yes", "download"}


def _carica_contesto(token: str):
    """Verifica token e carica portale + cliente. Abort 403/410 se non valido."""
    gp = _get_portale()
    portale_obj = gp.verifica_token(token)
    if not portale_obj:
        abort(410)  # Gone — link scaduto o revocato
    cliente = get_clienti().get(portale_obj.id_cliente)
    if not cliente:
        abort(404)
    gp.registra_accesso(portale_obj.id, request.remote_addr or "")
    return gp, portale_obj, cliente


def _fascicoli_map_cliente(id_cliente: str):
    try:
        return {
            f.id: f for f in get_fascicoli().tutti()
            if f.id_cliente == id_cliente
        }
    except Exception:
        return {}


def _documenti_economici_cliente(id_cliente: str):
    fascicoli_map = _fascicoli_map_cliente(id_cliente)

    try:
        gp_prev = _get_preventivi()
        preventivi = [
            p for p in gp_prev.tutti_preventivi()
            if p.id_cliente == id_cliente
        ]
        conferimenti = [
            c for c in gp_prev.tutti_conferimenti()
            if c.id_cliente == id_cliente
        ]
    except Exception:
        preventivi = []
        conferimenti = []

    try:
        gf = _get_fatturazione()
        parcelle = [
            p for p in gf.tutte()
            if p.id_cliente == id_cliente
        ]
    except Exception:
        parcelle = []

    preventivi = sorted(
        preventivi,
        key=lambda p: (p.data_emissione or "", p.creato_il or ""),
        reverse=True,
    )
    conferimenti = sorted(
        conferimenti,
        key=lambda c: (c.data_incarico or "", c.creato_il or ""),
        reverse=True,
    )
    parcelle = sorted(
        parcelle,
        key=lambda p: (p.data_emissione or "", p.creato_il or ""),
        reverse=True,
    )

    timeline = []
    for p in preventivi:
        fascicolo = fascicoli_map.get(p.id_fascicolo)
        timeline.append({
            "kind": "preventivo",
            "id": p.id,
            "numero": p.numero,
            "data": p.data_emissione,
            "titolo": p.oggetto,
            "stato": getattr(p.stato, "value", str(p.stato)),
            "totale": round(p.totale, 2),
            "fascicolo_label": fascicolo.titolo if fascicolo else "",
            "calc_summary": riepilogo_contesto_economico(getattr(p, "log_calcolo", None)),
        })
    for c in conferimenti:
        fascicolo = fascicoli_map.get(c.id_fascicolo)
        totale = c.compenso_pattuito or 0.0
        timeline.append({
            "kind": "conferimento",
            "id": c.id,
            "numero": c.numero,
            "data": c.data_incarico,
            "titolo": c.oggetto,
            "stato": getattr(c.stato, "value", str(c.stato)),
            "totale": round(totale, 2),
            "fascicolo_label": fascicolo.titolo if fascicolo else "",
        })
    for parcella in parcelle:
        fascicolo = fascicoli_map.get(parcella.id_fascicolo)
        timeline.append({
            "kind": "parcella",
            "id": parcella.id,
            "numero": parcella.numero,
            "data": parcella.data_emissione,
            "titolo": parcella.note or "Parcella professionale",
            "stato": getattr(parcella.stato, "value", str(parcella.stato)),
            "totale": round(parcella.totale, 2),
            "fascicolo_label": fascicolo.titolo if fascicolo else "",
            "calc_summary": riepilogo_contesto_economico(getattr(parcella, "log_calcolo", None)),
        })

    timeline.sort(key=lambda row: (row.get("data") or "", row.get("numero") or ""), reverse=True)
    return {
        "preventivi": preventivi,
        "conferimenti": conferimenti,
        "parcelle": parcelle,
        "timeline": timeline,
        "stats": {
            "preventivi": len(preventivi),
            "conferimenti": len(conferimenti),
            "parcelle": len(parcelle),
            "totale": len(timeline),
        },
    }


def _preventivo_cliente_o_404(id_cliente: str, id_preventivo: str):
    gp_prev = _get_preventivi()
    p = gp_prev.get_preventivo(id_preventivo)
    if not p or p.id_cliente != id_cliente:
        abort(404)
    return p, gp_prev


def _conferimento_cliente_o_404(id_cliente: str, id_conferimento: str):
    gp_prev = _get_preventivi()
    c = gp_prev.get_conferimento(id_conferimento)
    if not c or c.id_cliente != id_cliente:
        abort(404)
    return c, gp_prev


def _parcella_cliente_o_404(id_cliente: str, id_parcella: str):
    gf = _get_fatturazione()
    p = gf.get(id_parcella)
    if not p or p.id_cliente != id_cliente:
        abort(404)
    return p, gf


# ================================================================ HOME

@portale.route("/<token>")
def home(token: str):
    gp, p, cliente = _carica_contesto(token)

    fascicoli = []
    appuntamenti = []
    scadenze = []
    economici = {"stats": {"preventivi": 0, "conferimenti": 0, "parcelle": 0, "totale": 0}, "timeline": []}

    if p.permessi.vedi_fascicoli:
        gf = get_fascicoli()
        fascicoli = [f for f in gf.tutti() if f.id_cliente == cliente.id]

    if p.permessi.vedi_appuntamenti:
        ag = get_agenda()
        appuntamenti = [
            a for a in ag.tutti()
            if a.id_cliente == cliente.id and a.data_ora_dt.date() >= date.today()
        ][:5]

    if p.permessi.vedi_scadenze:
        gs = get_scadenziario()
        scadenze = [
            s for s in gs.imminenti(entro_giorni=30)
            if any(f.id == s.id_fascicolo for f in fascicoli)
        ]

    if getattr(p.permessi, "vedi_economici", False):
        economici = _documenti_economici_cliente(cliente.id)

    tracker_map = costruisci_tracker_fascicoli(fascicoli)

    return render_template(
        "portale/home.html",
        token=token,
        p=p,
        cliente=cliente,
        fascicoli=fascicoli,
        tracker_map=tracker_map,
        appuntamenti=appuntamenti,
        scadenze=scadenze,
        economici=economici,
        oggi=date.today(),
        studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
    )


# ================================================================ PRIVACY

@portale.route("/<token>/privacy", methods=["GET", "POST"])
def privacy(token: str):
    gp, p, cliente = _carica_contesto(token)

    if not p.permessi.firma_privacy:
        abort(403)

    if request.method == "POST":
        consenso = request.form.get("consenso") == "1"
        if not consenso:
            return render_template(
                "portale/privacy.html",
                token=token, p=p, cliente=cliente,
                errore="Devi spuntare la casella per procedere.",
                studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
            )

        # Aggiorna il cliente
        gc = get_clienti()
        from datetime import date as _date
        gc.aggiorna(
            cliente.id,
            consenso_trattamento=True,
            data_consenso=_date.today().isoformat(),
            modalita_consenso="digitale",
        )
        # Registra sulla scheda portale
        gp.registra_firma_privacy(
            p.id,
            ip=request.remote_addr or "",
            user_agent=request.headers.get("User-Agent", ""),
        )
        return render_template(
            "portale/privacy_ok.html",
            token=token, p=p, cliente=cliente,
            studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
        )

    return render_template(
        "portale/privacy.html",
        token=token, p=p, cliente=cliente,
        errore=None,
        studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
    )


# ================================================================ DOCUMENTI

@portale.route("/<token>/documenti", methods=["GET"])
def documenti(token: str):
    gp, p, cliente = _carica_contesto(token)
    if not p.permessi.carica_documenti:
        abort(403)

    fascicoli = []
    if p.permessi.vedi_fascicoli:
        gf = get_fascicoli()
        fascicoli = [f for f in gf.tutti() if f.id_cliente == cliente.id]

    return render_template(
        "portale/documenti.html",
        token=token, p=p, cliente=cliente,
        fascicoli=fascicoli,
        max_mb=p.permessi.max_upload_mb,
        studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
    )


@portale.route("/<token>/documenti/carica", methods=["POST"])
def carica_documento(token: str):
    gp, p, cliente = _carica_contesto(token)
    if not p.permessi.carica_documenti:
        abort(403)

    files = request.files.getlist("files[]")
    id_fascicolo = request.form.get("id_fascicolo", "").strip()
    note = request.form.get("note", "").strip()
    max_bytes = p.permessi.max_upload_mb * 1024 * 1024

    if not files or all(f.filename == "" for f in files):
        return render_template(
            "portale/documenti.html",
            token=token, p=p, cliente=cliente,
            fascicoli=_fascicoli_cliente(cliente.id),
            max_mb=p.permessi.max_upload_mb,
            studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
            errore="Nessun file selezionato.",
        )

    caricati = []
    errori = []

    if id_fascicolo:
        # Allega al fascicolo specificato
        gf = get_fascicoli()
        from pct.fascicoli import TipoDocumento
        for f in files:
            if not f.filename:
                continue
            contenuto = f.read()
            if len(contenuto) > max_bytes:
                errori.append(f"{f.filename}: supera il limite di {p.permessi.max_upload_mb} MB")
                continue
            try:
                gf.aggiungi_documento(
                    id_fasc=id_fascicolo,
                    nome_file=f.filename,
                    tipo=TipoDocumento.ALTRO,
                    contenuto=contenuto,
                    note=f"Caricato dal portale cliente. {note}".strip(),
                    caricato_da=f"portale:{cliente.nome_completo}",
                )
                caricati.append(f.filename)
            except Exception as e:
                errori.append(f"{f.filename}: {e}")
    else:
        # Salva nella cartella upload portale (inbox per l'avvocato)
        upload_dir = gp.upload_dir(cliente.id)
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for f in files:
            if not f.filename:
                continue
            contenuto = f.read()
            if len(contenuto) > max_bytes:
                errori.append(f"{f.filename}: supera il limite di {p.permessi.max_upload_mb} MB")
                continue
            safe_name = f"{ts}_{os.path.basename(f.filename)}"
            dest = os.path.join(upload_dir, safe_name)
            with open(dest, "wb") as out:
                out.write(contenuto)
            caricati.append(f.filename)

    return render_template(
        "portale/documenti_ok.html",
        token=token, p=p, cliente=cliente,
        caricati=caricati, errori=errori,
        studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
    )


# ================================================================ ECONOMICI

@portale.route("/<token>/economici", methods=["GET"])
def economici(token: str):
    gp, p, cliente = _carica_contesto(token)
    if not getattr(p.permessi, "vedi_economici", False):
        abort(403)

    dati = _documenti_economici_cliente(cliente.id)
    return render_template(
        "portale/economici.html",
        token=token,
        p=p,
        cliente=cliente,
        preventivi=dati["preventivi"],
        conferimenti=dati["conferimenti"],
        parcelle=dati["parcelle"],
        timeline=dati["timeline"],
        stats=dati["stats"],
        oggi=date.today(),
        studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
    )


@portale.route("/<token>/preventivi/<id_preventivo>/pdf", methods=["GET"])
def pdf_preventivo(token: str, id_preventivo: str):
    _, p, cliente = _carica_contesto(token)
    if not getattr(p.permessi, "vedi_economici", False):
        abort(403)

    preventivo, _ = _preventivo_cliente_o_404(cliente.id, id_preventivo)
    fascicolo = get_fascicoli().get(preventivo.id_fascicolo) if preventivo.id_fascicolo else None
    from web.blueprints.preventivi import _genera_pdf_preventivo

    buf = _genera_pdf_preventivo(preventivo, cliente, fascicolo, current_app.config)
    nome_file = f"preventivo_{preventivo.numero.replace('/', '-')}.pdf"
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=_download_requested(),
        download_name=nome_file,
    )


@portale.route("/<token>/conferimenti/<id_conferimento>/pdf", methods=["GET"])
def pdf_conferimento(token: str, id_conferimento: str):
    _, p, cliente = _carica_contesto(token)
    if not getattr(p.permessi, "vedi_economici", False):
        abort(403)

    conferimento, gp_prev = _conferimento_cliente_o_404(cliente.id, id_conferimento)
    fascicolo = get_fascicoli().get(conferimento.id_fascicolo) if conferimento.id_fascicolo else None
    preventivo = gp_prev.get_preventivo(conferimento.id_preventivo) if conferimento.id_preventivo else None
    from web.blueprints.preventivi import _genera_pdf_conferimento

    buf = _genera_pdf_conferimento(conferimento, cliente, fascicolo, preventivo, current_app.config)
    nome_file = f"conferimento_{conferimento.numero.replace('/', '-')}.pdf"
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=_download_requested(),
        download_name=nome_file,
    )


@portale.route("/<token>/parcelle/<id_parcella>/pdf", methods=["GET"])
def pdf_parcella(token: str, id_parcella: str):
    _, p, cliente = _carica_contesto(token)
    if not getattr(p.permessi, "vedi_economici", False):
        abort(403)

    parcella, _ = _parcella_cliente_o_404(cliente.id, id_parcella)
    fascicolo = get_fascicoli().get(parcella.id_fascicolo) if parcella.id_fascicolo else None
    from web.blueprints.fatturazione import _genera_pdf

    buf = _genera_pdf(parcella, cliente, fascicolo, current_app.config)
    nome_file = f"parcella_{parcella.numero.replace('/', '-')}.pdf"
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=_download_requested(),
        download_name=nome_file,
    )


# ================================================================ ANAGRAFICA

@portale.route("/<token>/anagrafica", methods=["GET", "POST"])
def anagrafica(token: str):
    gp, p, cliente = _carica_contesto(token)
    if not p.permessi.vedi_anagrafica:
        abort(403)

    errore = None
    successo = False

    if request.method == "POST":
        if not p.permessi.modifica_anagrafica:
            abort(403)
        f = request.form
        aggiornamenti = {}
        # Solo campi non sensibili modificabili dal cliente
        if f.get("cellulare") is not None:
            from pct.clienti import Recapiti
            rec = cliente.recapiti or Recapiti()
            rec.cellulare = f.get("cellulare", "").strip()
            rec.telefono  = f.get("telefono", "").strip()
            rec.email     = f.get("email", "").strip()
            aggiornamenti["recapiti"] = rec
        get_clienti().aggiorna(cliente.id, **aggiornamenti)
        # Ricarica
        cliente = get_clienti().get(cliente.id)
        successo = True

    return render_template(
        "portale/anagrafica.html",
        token=token, p=p, cliente=cliente,
        errore=errore, successo=successo,
        studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
    )


# ================================================================ 410 GONE

@portale.app_errorhandler(410)
def link_scaduto(e):
    return render_template(
        "portale/scaduto.html",
        studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
    ), 410


# ---------------------------------------------------------------- helper

def _fascicoli_cliente(id_cliente: str):
    try:
        return [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]
    except Exception:
        return []
