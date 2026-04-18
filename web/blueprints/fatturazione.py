"""
web/blueprints/fatturazione.py — Gestione parcelle / fatturazione.

URL base: /fatturazione/
Richiede autenticazione tramite g.utente_corrente (gestita da app.py).
"""
from __future__ import annotations

import io
import json
from datetime import date, timedelta

from flask import (Blueprint, abort, flash, g, redirect,
                   render_template, request, send_file, url_for, current_app)

from web.helpers import get_clienti, get_fascicoli, get_fatturazione as _shared_get_fatturazione, get_preventivi as _shared_get_preventivi
from pct.economico_context import (
    carica_log_calcolo,
    dump_log_calcolo,
    riepilogo_contesto_economico,
    sincronizza_contesto_economico,
)

fatturazione = Blueprint("fatturazione", __name__, url_prefix="/fatturazione")


# ---------------------------------------------------------------- helpers

def _get_gf():
    return _shared_get_fatturazione()


def _get_gp():
    return _shared_get_preventivi()


def _richiedi_login(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def _float_prefill(value, default=0.0):
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _voci_prefill_da_preventivo(preventivo) -> list[dict]:
    return [
        {
            "descrizione": voce.descrizione,
            "quantita": "1",
            "prezzo_unitario": f"{float(voce.importo):.2f}",
        }
        for voce in getattr(preventivo, "voci", []) or []
        if getattr(voce, "descrizione", "").strip()
    ]


def _contesto_parcella_da_preventivo(preventivo) -> str:
    data = sincronizza_contesto_economico(getattr(preventivo, "log_calcolo", None))
    data["source"] = "parcella_da_preventivo"
    data["source_label"] = "Parcella derivata da preventivo"
    data["documento_origine"] = {
        "tipo": "preventivo",
        "id": preventivo.id,
        "numero": preventivo.numero,
    }
    data.setdefault("oggetto", preventivo.oggetto)
    data.setdefault("id_pratica", preventivo.id_pratica)
    data.setdefault("area_pratica", preventivo.area_pratica)
    data.setdefault("tipo_compenso", preventivo.tipo_compenso)
    data.setdefault("tipo_procedimento", preventivo.tipo_procedimento)
    data.setdefault("valore_controversia", preventivo.valore_controversia)
    data.setdefault("complessita", preventivo.complessita)
    return dump_log_calcolo(data)


def _prefill_base():
    return {
        "origine": request.args.get("origine", "").strip(),
        "descrizione": request.args.get("descrizione", "").strip(),
        "quantita": request.args.get("quantita", "1").strip() or "1",
        "importo": request.args.get("importo", "").strip(),
        "note": request.args.get("note", "").strip(),
        "applica_cassa": request.args.get("applica_cassa", "1") != "0",
        "applica_iva": request.args.get("applica_iva", "1") != "0",
        "applica_ritenuta": request.args.get("applica_ritenuta", "0") == "1",
        "applica_bollo": request.args.get("applica_bollo", "0") == "1",
        "id_preventivo": request.args.get("id_preventivo", "").strip(),
        "id_pratica": request.args.get("id_pratica", "").strip(),
        "area_pratica": request.args.get("area_pratica", "").strip(),
        "tipo_compenso": request.args.get("tipo_compenso", "").strip(),
        "tipo_procedimento": request.args.get("tipo_procedimento", "").strip(),
        "valore_controversia": request.args.get("valore_controversia", "").strip(),
        "complessita": request.args.get("complessita", "").strip(),
        "log_calcolo": request.args.get("log_calcolo", "").strip(),
    }


# ================================================================ LISTA

@fatturazione.route("/", methods=["GET"])
@_richiedi_login
def lista():
    gf = _get_gf()
    gf.aggiorna_scadute()

    anno = int(request.args.get("anno", date.today().year))
    stato_filtro = request.args.get("stato", "")
    cliente_filtro = request.args.get("id_cliente", "")
    q = request.args.get("q", "").strip()

    parcelle = gf.tutte()
    parcelle = [p for p in parcelle if p.data_emissione.startswith(str(anno))]

    if stato_filtro:
        parcelle = [p for p in parcelle if p.stato.value == stato_filtro]
    if cliente_filtro:
        parcelle = [p for p in parcelle if p.id_cliente == cliente_filtro]

    # Ricerca testuale per numero o cliente
    if q:
        clienti_map_tmp = {c.id: c for c in get_clienti().tutti()}
        ql = q.lower()
        parcelle = [p for p in parcelle
                    if ql in p.numero.lower()
                    or ql in (clienti_map_tmp.get(p.id_cliente, None) and clienti_map_tmp[p.id_cliente].nome_completo or "").lower()]

    stats = gf.statistiche(anno)
    clienti_map = {c.id: c for c in get_clienti().tutti()}

    anni_disponibili = sorted({
        int(p.data_emissione[:4]) for p in gf.tutte()
    } | {date.today().year}, reverse=True)

    return render_template(
        "fatturazione/lista.html",
        parcelle=parcelle,
        stats=stats,
        clienti_map=clienti_map,
        anno=anno,
        anni_disponibili=anni_disponibili,
        stato_filtro=stato_filtro,
        cliente_filtro=cliente_filtro,
        q=q,
    )


# ================================================================ NUOVA PARCELLA

@fatturazione.route("/nuova", methods=["GET", "POST"])
@fatturazione.route("/nuova/<id_cliente>", methods=["GET", "POST"])
@_richiedi_login
def nuova(id_cliente: str = ""):
    gc = get_clienti()
    gf_parc = _get_gf()
    gp_prev = _get_gp()

    if request.method == "POST":
        from pct.fatturazione import VoceParcella, StatoParcella
        f = request.form

        id_cliente = f.get("id_cliente", "").strip()
        if not id_cliente:
            flash("Seleziona un cliente.", "danger")
            return redirect(request.url)

        # Raccogli voci
        descrizioni = f.getlist("voce_descr[]")
        quantita    = f.getlist("voce_qty[]")
        prezzi      = f.getlist("voce_prezzo[]")
        voci = []
        for desc, qty, prezzo in zip(descrizioni, quantita, prezzi):
            desc = desc.strip()
            if not desc:
                continue
            try:
                voci.append(VoceParcella(
                    descrizione=desc,
                    quantita=float(qty or 1),
                    prezzo_unitario=float(prezzo or 0),
                ))
            except (ValueError, TypeError):
                pass

        if not voci:
            flash("Aggiungi almeno una voce.", "danger")
            return redirect(request.url)

        # Dati studio da config
        cfg = current_app.config
        scade_il = f.get("data_scadenza", "").strip() or None
        note = f.get("note", "").strip()
        origine = f.get("origine", "").strip()
        id_preventivo = f.get("id_preventivo", "").strip() or None
        log_calcolo = f.get("log_calcolo", "").strip() or None
        if id_preventivo and not log_calcolo:
            preventivo = gp_prev.get_preventivo(id_preventivo)
            if preventivo:
                log_calcolo = _contesto_parcella_da_preventivo(preventivo)
        p = gf_parc.crea(
            id_cliente=id_cliente,
            voci=voci,
            creato_da=g.utente_corrente.username if g.utente_corrente else "",
            id_fascicolo=f.get("id_fascicolo", "").strip() or None,
            data_emissione=f.get("data_emissione") or date.today().isoformat(),
            data_scadenza=scade_il,
            applica_iva=bool(f.get("applica_iva")),
            applica_cassa=bool(f.get("applica_cassa")),
            applica_ritenuta=bool(f.get("applica_ritenuta")),
            applica_bollo=bool(f.get("applica_bollo")),
            note=note,
            origine=origine,
            id_preventivo=id_preventivo,
            id_pratica=f.get("id_pratica", "").strip(),
            area_pratica=f.get("area_pratica", "").strip(),
            tipo_compenso=f.get("tipo_compenso", "").strip(),
            tipo_procedimento=f.get("tipo_procedimento", "").strip(),
            valore_controversia=_float_prefill(f.get("valore_controversia"), 0.0),
            complessita=f.get("complessita", "").strip(),
            log_calcolo=log_calcolo,
            studio_piva=cfg.get("STUDIO_PIVA", ""),
            studio_cf=cfg.get("STUDIO_CF", ""),
            studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
            studio_iban=cfg.get("STUDIO_IBAN", ""),
        )
        flash(f"Parcella {p.numero} creata.", "success")
        from_cliente = f.get("from_cliente", "")
        if from_cliente:
            from flask import url_for as _url_for
            return redirect(_url_for("cartella_cliente", id_cliente=from_cliente))
        return redirect(url_for("fatturazione.dettaglio", id_parcella=p.id))

    # GET
    from_cliente_get = request.args.get("from_cliente", "")
    id_cliente_query = request.args.get("id_cliente", "").strip()
    if not id_cliente and id_cliente_query:
        id_cliente = id_cliente_query
    id_fascicolo_pre = request.args.get("id_fascicolo", "").strip()
    fascicolo_pre = get_fascicoli().get(id_fascicolo_pre) if id_fascicolo_pre else None
    id_preventivo = request.args.get("id_preventivo", "").strip()
    preventivo_pre = gp_prev.get_preventivo(id_preventivo) if id_preventivo else None
    if preventivo_pre:
        id_cliente = preventivo_pre.id_cliente or id_cliente
        if preventivo_pre.id_fascicolo and not id_fascicolo_pre:
            id_fascicolo_pre = preventivo_pre.id_fascicolo
            fascicolo_pre = get_fascicoli().get(id_fascicolo_pre)
    if fascicolo_pre and not id_cliente:
        id_cliente = fascicolo_pre.id_cliente or ""
    clienti = gc.tutti()
    cliente_sel = gc.get(id_cliente) if id_cliente else None
    fascicoli = []
    if cliente_sel:
        fascicoli = [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]
    prefill = _prefill_base()
    if preventivo_pre:
        prefill.update(
            {
                "origine": prefill["origine"] or "preventivo",
                "id_preventivo": preventivo_pre.id,
                "id_pratica": preventivo_pre.id_pratica,
                "area_pratica": preventivo_pre.area_pratica,
                "tipo_compenso": preventivo_pre.tipo_compenso,
                "tipo_procedimento": preventivo_pre.tipo_procedimento,
                "valore_controversia": f"{preventivo_pre.valore_controversia:.2f}" if preventivo_pre.valore_controversia else "",
                "complessita": preventivo_pre.complessita,
                "note": prefill["note"] or preventivo_pre.note or "",
                "applica_cassa": preventivo_pre.applica_cassa,
                "applica_iva": preventivo_pre.applica_iva,
                "log_calcolo": prefill["log_calcolo"] or _contesto_parcella_da_preventivo(preventivo_pre),
            }
        )
    raw_voci_json = (request.args.get("voci_json", "") or "").strip()
    voci_prefill = []
    if raw_voci_json:
        try:
            parsed = json.loads(raw_voci_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = []
        if isinstance(parsed, list):
            for row in parsed:
                if not isinstance(row, dict):
                    continue
                descrizione = (row.get("descrizione") or "").strip()
                if not descrizione:
                    continue
                try:
                    quantita = float(row.get("quantita", 1) or 1)
                except (ValueError, TypeError):
                    quantita = 1.0
                try:
                    prezzo = float(row.get("prezzo_unitario", row.get("importo", 0)) or 0)
                except (ValueError, TypeError):
                    prezzo = 0.0
                voci_prefill.append(
                    {
                        "descrizione": descrizione,
                        "quantita": f"{quantita:g}",
                        "prezzo_unitario": f"{prezzo:.2f}",
                    }
                )
    elif preventivo_pre:
        voci_prefill = _voci_prefill_da_preventivo(preventivo_pre)
    if not voci_prefill:
        voci_prefill = [
            {
                "descrizione": prefill["descrizione"],
                "quantita": prefill["quantita"] or "1",
                "prezzo_unitario": prefill["importo"],
            }
        ]
    prefill["voci"] = voci_prefill
    if prefill.get("log_calcolo"):
        prefill["log_calcolo"] = dump_log_calcolo(sincronizza_contesto_economico(prefill.get("log_calcolo")))
    prefill["calc_summary"] = riepilogo_contesto_economico(prefill.get("log_calcolo"))

    return render_template(
        "fatturazione/form.html",
        clienti=clienti,
        cliente_sel=cliente_sel,
        fascicoli=fascicoli,
        id_fascicolo_pre=id_fascicolo_pre,
        fascicolo_pre=fascicolo_pre,
        preventivo_pre=preventivo_pre,
        prefill=prefill,
        oggi=date.today(),
        scadenza_default=(date.today() + timedelta(days=30)).isoformat(),
        from_cliente=from_cliente_get,
    )


@fatturazione.route("/da-preventivo/<id_preventivo>", methods=["GET"])
@_richiedi_login
def da_preventivo(id_preventivo: str):
    preventivo = _get_gp().get_preventivo(id_preventivo)
    if not preventivo:
        abort(404)
    params = {"id_preventivo": preventivo.id, "origine": "preventivo"}
    if preventivo.id_cliente:
        params["id_cliente"] = preventivo.id_cliente
    if preventivo.id_fascicolo:
        params["id_fascicolo"] = preventivo.id_fascicolo
    return redirect(url_for("fatturazione.nuova", **params))


# ================================================================ DETTAGLIO

@fatturazione.route("/<id_parcella>", methods=["GET"])
@_richiedi_login
def dettaglio(id_parcella: str):
    gf = _get_gf()
    p = gf.get(id_parcella)
    if not p:
        abort(404)
    cliente = get_clienti().get(p.id_cliente)
    fascicolo = get_fascicoli().get(p.id_fascicolo) if p.id_fascicolo else None
    preventivo = _get_gp().get_preventivo(p.id_preventivo) if p.id_preventivo else None
    return render_template(
        "fatturazione/dettaglio.html",
        p=p,
        cliente=cliente,
        fascicolo=fascicolo,
        preventivo=preventivo,
        calc_summary=riepilogo_contesto_economico(p.log_calcolo),
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
    )


# ================================================================ CAMBIA STATO

@fatturazione.route("/<id_parcella>/stato", methods=["POST"])
@_richiedi_login
def cambia_stato(id_parcella: str):
    from pct.fatturazione import StatoParcella
    gf = _get_gf()
    p = gf.get(id_parcella)
    if not p:
        abort(404)
    stato_str = request.form.get("stato", "")
    try:
        nuovo_stato = StatoParcella(stato_str)
    except ValueError:
        flash("Stato non valido.", "danger")
        return redirect(url_for("fatturazione.dettaglio", id_parcella=id_parcella))
    metodo = request.form.get("metodo_pagamento", "").strip() or None
    data_pag = request.form.get("data_pagamento", "").strip() or None
    gf.cambia_stato(id_parcella, nuovo_stato, data_pagamento=data_pag, metodo_pagamento=metodo)
    flash(f"Stato aggiornato: {nuovo_stato.value}.", "success")
    return redirect(url_for("fatturazione.dettaglio", id_parcella=id_parcella))


# ================================================================ ELIMINA

@fatturazione.route("/<id_parcella>/elimina", methods=["POST"])
@_richiedi_login
def elimina(id_parcella: str):
    gf = _get_gf()
    p = gf.get(id_parcella)
    if not p:
        abort(404)
    gf.elimina(id_parcella)
    flash("Parcella eliminata.", "success")
    return redirect(url_for("fatturazione.lista"))


# ================================================================ PDF

@fatturazione.route("/<id_parcella>/pdf", methods=["GET"])
@_richiedi_login
def pdf(id_parcella: str):
    gf = _get_gf()
    p = gf.get(id_parcella)
    if not p:
        abort(404)
    cliente = get_clienti().get(p.id_cliente)
    fascicolo = get_fascicoli().get(p.id_fascicolo) if p.id_fascicolo else None
    buf = _genera_pdf(p, cliente, fascicolo, current_app.config)
    nome_file = f"parcella_{p.numero.replace('/', '-')}.pdf"
    download = (request.args.get("download") or "").strip().lower() in {"1", "true", "yes", "download"}
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=download, download_name=nome_file)


# ================================================================ XML FatturaPA

@fatturazione.route("/<id_parcella>/xml", methods=["GET"])
@_richiedi_login
def xml_fattura_pa(id_parcella: str):
    """Genera e scarica il file XML FatturaPA 1.2 per la parcella."""
    from pct.fattura_pa import genera_xml_fattura_pa, nome_file_fattura_pa
    gf = _get_gf()
    p = gf.get(id_parcella)
    if not p:
        abort(404)
    cliente = get_clienti().get(p.id_cliente)
    cfg = current_app.config
    studio_nome = cfg.get("STUDIO_NOME", "Studio Legale")
    studio_piva = p.studio_piva or cfg.get("STUDIO_PIVA", "")
    studio_cf   = p.studio_cf   or cfg.get("STUDIO_CF", "")
    studio_ind  = p.studio_indirizzo or cfg.get("STUDIO_INDIRIZZO", "")
    pec_cl = ""
    if cliente and getattr(cliente, "recapiti", None):
        pec_cl = getattr(cliente.recapiti, "pec", "")
    xml_bytes = genera_xml_fattura_pa(
        parcella=p,
        cliente=cliente,
        studio_nome=studio_nome,
        studio_piva=studio_piva,
        studio_cf=studio_cf,
        studio_indirizzo=studio_ind,
        pec_destinatario=pec_cl,
    )
    nome = nome_file_fattura_pa(studio_piva, p.numero)
    return send_file(
        io.BytesIO(xml_bytes),
        mimetype="application/xml",
        as_attachment=True,
        download_name=nome,
    )


# ================================================================ FASCICOLI per cliente (AJAX)

@fatturazione.route("/ajax/fascicoli/<id_cliente>")
@_richiedi_login
def ajax_fascicoli(id_cliente: str):
    from flask import jsonify
    fascicoli = [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]
    return jsonify([{"id": f.id, "titolo": f.titolo,
                     "numero_rg": f.numero_rg or ""} for f in fascicoli])


# ================================================================ Generazione PDF

def _genera_pdf(p, cliente, fascicolo, config) -> io.BytesIO:
    """Genera PDF professionale con ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    except ImportError:
        # Fallback: testo semplice
        buf = io.BytesIO()
        buf.write(f"Parcella {p.numero}\nTotale: € {p.totale:.2f}".encode())
        buf.seek(0)
        return buf

    PRIMARY   = colors.HexColor("#1a3a5c")
    ACCENT    = colors.HexColor("#c8972b")
    LIGHT_BG  = colors.HexColor("#f4f6fa")
    GRAY_TEXT = colors.HexColor("#6b7280")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=20*mm, rightMargin=20*mm,
                             topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    style_body = ParagraphStyle("body", parent=styles["Normal"],
                                fontSize=9, leading=13, textColor=colors.black)
    style_small = ParagraphStyle("small", parent=styles["Normal"],
                                 fontSize=7.5, leading=11, textColor=GRAY_TEXT)
    style_h1 = ParagraphStyle("h1", parent=styles["Normal"],
                               fontSize=22, leading=26, textColor=PRIMARY,
                               fontName="Helvetica-Bold")
    style_h2 = ParagraphStyle("h2", parent=styles["Normal"],
                               fontSize=11, leading=14, textColor=PRIMARY,
                               fontName="Helvetica-Bold")
    style_right = ParagraphStyle("right", parent=style_body, alignment=TA_RIGHT)
    style_bold  = ParagraphStyle("bold", parent=style_body, fontName="Helvetica-Bold")

    studio_nome = config.get("STUDIO_NOME", "IUSENTRA")
    studio_piva = p.studio_piva or config.get("STUDIO_PIVA", "")
    studio_cf   = p.studio_cf   or config.get("STUDIO_CF", "")
    studio_ind  = p.studio_indirizzo or config.get("STUDIO_INDIRIZZO", "")
    studio_iban = p.studio_iban or config.get("STUDIO_IBAN", "")

    nome_cliente = cliente.nome_completo if cliente else "Cliente sconosciuto"
    cf_piva_cliente = ""
    if cliente:
        if cliente.codice_fiscale:
            cf_piva_cliente += f"C.F. {cliente.codice_fiscale}"
        if hasattr(cliente, "partita_iva") and cliente.partita_iva:
            sep = " / " if cf_piva_cliente else ""
            cf_piva_cliente += f"{sep}P.IVA {cliente.partita_iva}"

    story = []

    # ---- Header: studio a sinistra, "PARCELLA" a destra
    header_data = [[
        Paragraph(f"<b>{studio_nome}</b>", style_h2),
        Paragraph("PARCELLA PROFESSIONALE", ParagraphStyle(
            "parctit", parent=style_h1, alignment=TA_RIGHT, fontSize=18)),
    ]]
    header_tbl = Table(header_data, colWidths=["60%", "40%"])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_tbl)

    # Studio info + Numero parcella
    info_left = []
    if studio_ind:
        info_left.append(Paragraph(studio_ind, style_small))
    if studio_piva:
        info_left.append(Paragraph(f"P.IVA {studio_piva}", style_small))
    if studio_cf:
        info_left.append(Paragraph(f"C.F. {studio_cf}", style_small))

    n_str   = f"<b>N. {p.numero}</b>"
    dt_str  = f"Data: {p.data_emissione}"
    sc_str  = f"Scadenza: {p.data_scadenza}" if p.data_scadenza else ""

    info_right = [
        Paragraph(n_str, ParagraphStyle("nr", parent=style_body,
                                        alignment=TA_RIGHT, fontName="Helvetica-Bold", fontSize=11)),
        Paragraph(dt_str, ParagraphStyle("dt", parent=style_small, alignment=TA_RIGHT)),
    ]
    if sc_str:
        info_right.append(Paragraph(sc_str, ParagraphStyle("sc", parent=style_small, alignment=TA_RIGHT)))

    info_data = [[
        [x for x in info_left] or [Paragraph("", style_small)],
        info_right,
    ]]
    # Flatten: reportlab Table accetta Flowable nei contenuti se usiamo liste
    info_tbl = Table(
        [[Paragraph("\n".join([studio_ind, f"P.IVA {studio_piva}" if studio_piva else "",
                                f"C.F. {studio_cf}" if studio_cf else ""]).strip(), style_small),
          Paragraph(f"<b>N. {p.numero}</b><br/>{dt_str}<br/>{sc_str}", ParagraphStyle(
              "infori", parent=style_small, alignment=TA_RIGHT))]],
        colWidths=["60%", "40%"]
    )
    info_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(Spacer(1, 4*mm))
    story.append(info_tbl)
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 4*mm))

    # ---- Destinatario
    story.append(Paragraph("Spettabile", style_small))
    story.append(Paragraph(f"<b>{nome_cliente}</b>", style_h2))
    if cf_piva_cliente:
        story.append(Paragraph(cf_piva_cliente, style_small))
    if fascicolo:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f"Rif. pratica: {fascicolo.titolo}" + (f" · RG {fascicolo.numero_rg}" if fascicolo.numero_rg else ""),
            style_small))
    story.append(Spacer(1, 6*mm))

    # ---- Voci
    story.append(Paragraph("Prestazioni professionali", style_h2))
    story.append(Spacer(1, 2*mm))

    voci_data = [
        [Paragraph("<b>Descrizione</b>", style_bold),
         Paragraph("<b>Q.tà</b>", ParagraphStyle("qb", parent=style_bold, alignment=TA_RIGHT)),
         Paragraph("<b>Prezzo unit.</b>", ParagraphStyle("pb", parent=style_bold, alignment=TA_RIGHT)),
         Paragraph("<b>Importo</b>", ParagraphStyle("ib", parent=style_bold, alignment=TA_RIGHT))],
    ]
    for v in p.voci:
        voci_data.append([
            Paragraph(v.descrizione, style_body),
            Paragraph(f"{v.quantita:g}", ParagraphStyle("qv", parent=style_body, alignment=TA_RIGHT)),
            Paragraph(f"€ {v.prezzo_unitario:,.2f}", ParagraphStyle("pv", parent=style_body, alignment=TA_RIGHT)),
            Paragraph(f"€ {v.importo:,.2f}", ParagraphStyle("iv", parent=style_body, alignment=TA_RIGHT)),
        ])

    voci_tbl = Table(voci_data, colWidths=["55%", "10%", "17.5%", "17.5%"])
    voci_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(voci_tbl)
    story.append(Spacer(1, 4*mm))

    # ---- Riepilogo importi
    rows = []
    rows.append(["Imponibile", f"€ {p.imponibile:,.2f}"])
    if p.applica_cassa:
        rows.append(["Contributo Cassa Forense (4 %)", f"€ {p.cassa_forense:,.2f}"])
    if p.applica_iva:
        rows.append([f"IVA 22 % su € {p.base_iva:,.2f}", f"€ {p.iva:,.2f}"])
    if p.applica_bollo:
        rows.append(["Marca da bollo", f"€ {p.bollo:,.2f}"])
    if p.applica_ritenuta:
        rows.append(["Ritenuta d'acconto (20 %)", f"- € {p.ritenuta:,.2f}"])
    rows.append(["TOTALE", f"€ {p.totale:,.2f}"])

    riepilogo_data = [
        [Paragraph(label, ParagraphStyle(
            "rlbl", parent=style_body,
            fontName="Helvetica-Bold" if label == "TOTALE" else "Helvetica",
            textColor=PRIMARY if label == "TOTALE" else colors.black,
            fontSize=11 if label == "TOTALE" else 9)),
         Paragraph(valore, ParagraphStyle(
            "rval", parent=style_body, alignment=TA_RIGHT,
            fontName="Helvetica-Bold" if label == "TOTALE" else "Helvetica",
            textColor=PRIMARY if label == "TOTALE" else colors.black,
            fontSize=11 if label == "TOTALE" else 9))]
        for label, valore in rows
    ]

    rie_tbl = Table(riepilogo_data, colWidths=["75%", "25%"])
    rie_tbl.setStyle(TableStyle([
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, PRIMARY),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BG),
    ]))
    story.append(rie_tbl)
    story.append(Spacer(1, 6*mm))

    calc_summary = riepilogo_contesto_economico(p.log_calcolo)
    if calc_summary:
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("Tracciabilita del calcolo", style_h2))
        meta_rows = []
        if calc_summary.get("source_label"):
            meta_rows.append(f"<b>Origine:</b> {calc_summary['source_label']}")
        if calc_summary.get("pratica_label"):
            meta_rows.append(f"<b>Tipologia:</b> {calc_summary['pratica_label']}")
        regola_label = calc_summary.get("regola_tariffaria_label") or calc_summary.get("regola_tariffaria")
        if regola_label:
            meta_rows.append(f"<b>Regola:</b> {regola_label}")
        if calc_summary.get("grado_sede"):
            meta_rows.append(f"<b>Grado / sede:</b> {calc_summary['grado_sede']}")
        if calc_summary.get("scaglione"):
            meta_rows.append(f"<b>Scaglione:</b> {calc_summary['scaglione']}")
        if calc_summary.get("complessita"):
            meta_rows.append(f"<b>Complessita:</b> {calc_summary['complessita']}")
        audit = calc_summary.get("audit_tariffario") or {}
        if audit.get("compliance_label"):
            audit_parts = [f"<b>Conformita tariffaria:</b> {audit['compliance_label']}"]
            if audit.get("table_code"):
                table_label = str(audit.get("table_label") or "").strip()
                audit_parts.append(
                    f"Tabella {audit['table_code']}" + (f" - {table_label}" if table_label else "")
                )
            if audit.get("compliance_note"):
                audit_parts.append(str(audit["compliance_note"]))
            meta_rows.append(" - ".join(part for part in audit_parts if part))
        if calc_summary.get("adr_accordo"):
            meta_rows.append("<b>ADR:</b> accordo finale con maggiorazioni normative applicate")
        elif calc_summary.get("adr_enabled"):
            meta_rows.append("<b>ADR:</b> procedura con logica parametrica dedicata")
        if calc_summary.get("variazioni_fasi"):
            meta_rows.append(
                "<b>Variazioni:</b> "
                + " · ".join(row["label"] for row in calc_summary["variazioni_fasi"])
            )
        if calc_summary.get("riferimenti_normativi"):
            meta_rows.append(
                "<b>Riferimenti:</b> "
                + " · ".join(calc_summary["riferimenti_normativi"][:3])
            )
        for row in meta_rows:
            story.append(Paragraph(row, style_small))
        story.append(Spacer(1, 4*mm))

    # ---- Pagamento
    if studio_iban or p.note:
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
        story.append(Spacer(1, 3*mm))
        if studio_iban:
            story.append(Paragraph(
                f"<b>Coordinate bancarie:</b> {studio_iban}", style_body))
        if p.data_scadenza:
            story.append(Paragraph(
                f"Si prega di effettuare il pagamento entro il <b>{p.data_scadenza}</b>.",
                style_body))
        if p.note:
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(p.note, style_small))

    # ---- Footer
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
    story.append(Spacer(1, 2*mm))
    footer_txt = studio_nome
    if studio_piva:
        footer_txt += f" — P.IVA {studio_piva}"
    story.append(Paragraph(footer_txt, ParagraphStyle(
        "footer", parent=style_small, alignment=TA_CENTER)))

    doc.build(story)
    buf.seek(0)
    return buf
