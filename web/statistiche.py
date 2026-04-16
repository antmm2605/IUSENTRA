"""
web/blueprints/portale.py — Portale self-service per il cliente.

URL base: /portale/<token>
Nessuna autenticazione richiesta — l'accesso è garantito dal token sicuro.
"""
from __future__ import annotations

import os
from datetime import date

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for, current_app)

from web.helpers import get_clienti, get_fascicoli, get_agenda, get_scadenziario

portale = Blueprint("portale", __name__, url_prefix="/portale")


# ---------------------------------------------------------------- helper locale

def _get_portale():
    from pct.portale import GestionePortale
    return GestionePortale(
        db_path=current_app.config.get("PORTALE_DB", "./portale/portali.json"),
        uploads_dir=current_app.config.get("PORTALE_UPLOADS", "./portale/uploads"),
    )


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


# ================================================================ HOME

@portale.route("/<token>")
def home(token: str):
    gp, p, cliente = _carica_contesto(token)

    fascicoli = []
    appuntamenti = []
    scadenze = []

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

    return render_template(
        "portale/home.html",
        token=token,
        p=p,
        cliente=cliente,
        fascicoli=fascicoli,
        appuntamenti=appuntamenti,
        scadenze=scadenze,
        oggi=date.today(),
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
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
                studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
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
            studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
        )

    return render_template(
        "portale/privacy.html",
        token=token, p=p, cliente=cliente,
        errore=None,
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
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
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
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
            studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
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
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
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
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
    )


# ================================================================ 410 GONE

@portale.app_errorhandler(410)
def link_scaduto(e):
    return render_template(
        "portale/scaduto.html",
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
    ), 410


# ---------------------------------------------------------------- helper

def _fascicoli_cliente(id_cliente: str):
    try:
        return [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]
    except Exception:
        return []
