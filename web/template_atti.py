"""
web/blueprints/preventivi.py — Preventivi e conferimenti di incarico.

URL base: /preventivi/
Richiede autenticazione tramite g.utente_corrente (gestita da app.py).
"""
from __future__ import annotations

import io
from datetime import date, timedelta

from flask import (Blueprint, abort, flash, g, redirect,
                   render_template, request, send_file, url_for, current_app)

from web.helpers import get_clienti, get_fascicoli, get_preventivi

preventivi = Blueprint("preventivi", __name__, url_prefix="/preventivi")


# ---------------------------------------------------------------- helpers

def _get_gp():
    return get_preventivi()


def _richiedi_login(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ================================================================ LISTA

@preventivi.route("/", methods=["GET"])
@_richiedi_login
def lista():
    gp = _get_gp()
    gp.aggiorna_scaduti()

    tab = request.args.get("tab", "preventivi")  # preventivi | conferimenti
    anno = int(request.args.get("anno", date.today().year))
    stato_filtro = request.args.get("stato", "")
    cliente_filtro = request.args.get("id_cliente", "")

    tutti_prev = gp.tutti_preventivi()
    tutti_conf = gp.tutti_conferimenti()

    prev_anno = [p for p in tutti_prev if p.data_emissione.startswith(str(anno))]
    conf_anno = [c for c in tutti_conf if c.data_incarico.startswith(str(anno))]

    if stato_filtro:
        prev_anno = [p for p in prev_anno if p.stato.value == stato_filtro]
        conf_anno = [c for c in conf_anno if c.stato.value == stato_filtro]
    if cliente_filtro:
        prev_anno = [p for p in prev_anno if p.id_cliente == cliente_filtro]
        conf_anno = [c for c in conf_anno if c.id_cliente == cliente_filtro]

    clienti_map = {c.id: c for c in get_clienti().tutti()}

    anni_disponibili = sorted({
        int(p.data_emissione[:4]) for p in tutti_prev
    } | {
        int(c.data_incarico[:4]) for c in tutti_conf
    } | {date.today().year}, reverse=True)

    return render_template(
        "preventivi/lista.html",
        tab=tab,
        prev_lista=prev_anno,
        conf_lista=conf_anno,
        clienti_map=clienti_map,
        anno=anno,
        anni_disponibili=anni_disponibili,
        stato_filtro=stato_filtro,
        cliente_filtro=cliente_filtro,
        oggi=date.today(),
    )


# ================================================================ NUOVO PREVENTIVO

@preventivi.route("/nuovo", methods=["GET", "POST"])
@preventivi.route("/nuovo/<id_cliente>", methods=["GET", "POST"])
@_richiedi_login
def nuovo_preventivo(id_cliente: str = ""):
    gc = get_clienti()
    gp = _get_gp()

    if request.method == "POST":
        from pct.preventivi import VocePreventivo, TipoVoce
        f = request.form

        id_cliente = f.get("id_cliente", "").strip()
        if not id_cliente:
            flash("Seleziona un cliente.", "danger")
            return redirect(request.url)

        oggetto = f.get("oggetto", "").strip()
        if not oggetto:
            flash("Inserisci l'oggetto del preventivo.", "danger")
            return redirect(request.url)

        # Raccogli voci
        descrizioni = f.getlist("voce_descr[]")
        importi     = f.getlist("voce_importo[]")
        tipi        = f.getlist("voce_tipo[]")
        voci = []
        for desc, imp, tipo in zip(descrizioni, importi, tipi):
            desc = desc.strip()
            if not desc:
                continue
            try:
                voci.append(VocePreventivo(
                    descrizione=desc,
                    importo=float(imp or 0),
                    tipo=TipoVoce(tipo) if tipo else TipoVoce.ONORARIO,
                ))
            except (ValueError, TypeError):
                pass

        if not voci:
            flash("Aggiungi almeno una voce.", "danger")
            return redirect(request.url)

        from pct.preventivi import TipoCompensoPrevisto, TipoProcedimento
        cfg = current_app.config
        try:
            valore_controversia = float(f.get("valore_controversia", 0) or 0)
        except (ValueError, TypeError):
            valore_controversia = 0.0
        try:
            tariffa_oraria = float(f.get("tariffa_oraria", 0) or 0)
        except (ValueError, TypeError):
            tariffa_oraria = 0.0
        try:
            ore_stimate = float(f.get("ore_stimate", 0) or 0)
        except (ValueError, TypeError):
            ore_stimate = 0.0
        fasi_raw = f.getlist("fasi_incluse[]")
        fasi_str = ",".join(fasi_raw) if fasi_raw else "studio,introduttiva,istruttoria,decisionale"
        p = gp.crea_preventivo(
            id_cliente=id_cliente,
            oggetto=oggetto,
            voci=voci,
            creato_da=g.utente_corrente.username if g.utente_corrente else "",
            id_fascicolo=f.get("id_fascicolo", "").strip() or None,
            data_emissione=f.get("data_emissione") or date.today().isoformat(),
            data_scadenza=f.get("data_scadenza", "").strip() or None,
            applica_cassa=bool(f.get("applica_cassa")),
            applica_iva=bool(f.get("applica_iva")),
            note=f.get("note", "").strip(),
            tipo_compenso=f.get("tipo_compenso", TipoCompensoPrevisto.FISSO.value),
            tipo_procedimento=f.get("tipo_procedimento", TipoProcedimento.CIVILE_COGNIZIONE.value),
            valore_controversia=valore_controversia,
            tariffa_oraria=tariffa_oraria,
            ore_stimate=ore_stimate,
            fasi_incluse=fasi_str,
            complessita=f.get("complessita", "").strip(),
            studio_piva=cfg.get("STUDIO_PIVA", ""),
            studio_cf=cfg.get("STUDIO_CF", ""),
            studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
        )
        flash(f"Preventivo {p.numero} creato.", "success")
        from_page = f.get("from_page", "")
        if from_page == "cliente":
            return redirect(url_for("cartella_cliente", id_cliente=id_cliente))
        if from_page == "fascicolo" and p.id_fascicolo:
            return redirect(url_for("dettaglio_fascicolo", id_fascicolo=p.id_fascicolo))
        return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=p.id))

    # GET
    clienti = gc.tutti()
    cliente_sel = gc.get(id_cliente) if id_cliente else None
    fascicoli = []
    if cliente_sel:
        fascicoli = [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]

    from_page = request.args.get("from_page", "")
    id_fascicolo_pre = request.args.get("id_fascicolo", "")

    return render_template(
        "preventivi/form_preventivo.html",
        clienti=clienti,
        cliente_sel=cliente_sel,
        fascicoli=fascicoli,
        oggi=date.today(),
        scadenza_default=(date.today() + timedelta(days=30)).isoformat(),
        from_page=from_page,
        id_fascicolo_pre=id_fascicolo_pre,
    )


# ================================================================ DETTAGLIO PREVENTIVO

@preventivi.route("/p/<id_preventivo>", methods=["GET"])
@_richiedi_login
def dettaglio_preventivo(id_preventivo: str):
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        abort(404)
    cliente = get_clienti().get(p.id_cliente)
    fascicolo = get_fascicoli().get(p.id_fascicolo) if p.id_fascicolo else None
    # Conferimenti collegati
    conferimenti = [c for c in gp.tutti_conferimenti() if c.id_preventivo == id_preventivo]
    return render_template(
        "preventivi/dettaglio_preventivo.html",
        p=p,
        cliente=cliente,
        fascicolo=fascicolo,
        conferimenti=conferimenti,
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
        oggi=date.today(),
    )


# ================================================================ CAMBIA STATO PREVENTIVO

@preventivi.route("/p/<id_preventivo>/stato", methods=["POST"])
@_richiedi_login
def cambia_stato_preventivo(id_preventivo: str):
    from pct.preventivi import StatoPreventivo
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        abort(404)
    stato_str = request.form.get("stato", "")
    try:
        nuovo_stato = StatoPreventivo(stato_str)
    except ValueError:
        flash("Stato non valido.", "danger")
        return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))
    gp.cambia_stato_preventivo(id_preventivo, nuovo_stato)
    flash(f"Stato aggiornato: {nuovo_stato.value}.", "success")
    return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))


# ================================================================ ELIMINA PREVENTIVO

@preventivi.route("/p/<id_preventivo>/elimina", methods=["POST"])
@_richiedi_login
def elimina_preventivo(id_preventivo: str):
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        abort(404)
    gp.elimina_preventivo(id_preventivo)
    flash("Preventivo eliminato.", "success")
    return redirect(url_for("preventivi.lista"))


# ================================================================ PDF PREVENTIVO

@preventivi.route("/p/<id_preventivo>/pdf", methods=["GET"])
@_richiedi_login
def pdf_preventivo(id_preventivo: str):
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        abort(404)
    cliente = get_clienti().get(p.id_cliente)
    fascicolo = get_fascicoli().get(p.id_fascicolo) if p.id_fascicolo else None
    buf = _genera_pdf_preventivo(p, cliente, fascicolo, current_app.config)
    nome_file = f"preventivo_{p.numero.replace('/', '-')}.pdf"
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=False, download_name=nome_file)


# ================================================================ NUOVO CONFERIMENTO

@preventivi.route("/conferimento/nuovo", methods=["GET", "POST"])
@preventivi.route("/conferimento/nuovo/<id_cliente>", methods=["GET", "POST"])
@_richiedi_login
def nuovo_conferimento(id_cliente: str = ""):
    gc = get_clienti()
    gp = _get_gp()

    if request.method == "POST":
        f = request.form
        id_cliente = f.get("id_cliente", "").strip()
        if not id_cliente:
            flash("Seleziona un cliente.", "danger")
            return redirect(request.url)

        oggetto = f.get("oggetto", "").strip()
        if not oggetto:
            flash("Inserisci l'oggetto dell'incarico.", "danger")
            return redirect(request.url)

        avvocato = f.get("avvocato_referente", "").strip()
        if not avvocato:
            flash("Inserisci il nome dell'avvocato referente.", "danger")
            return redirect(request.url)

        try:
            compenso = float(f.get("compenso_pattuito", 0) or 0)
        except (ValueError, TypeError):
            compenso = 0.0

        from pct.preventivi import TipoCompensoPrevisto, TipoProcedimento
        cfg = current_app.config
        try:
            tariffa_oraria = float(f.get("tariffa_oraria", 0) or 0)
        except (ValueError, TypeError):
            tariffa_oraria = 0.0
        try:
            quota_palmario = float(f.get("quota_palmario_pct", 0) or 0)
        except (ValueError, TypeError):
            quota_palmario = 0.0
        c = gp.crea_conferimento(
            id_cliente=id_cliente,
            oggetto=oggetto,
            avvocato_referente=avvocato,
            creato_da=g.utente_corrente.username if g.utente_corrente else "",
            id_preventivo=f.get("id_preventivo", "").strip() or None,
            id_fascicolo=f.get("id_fascicolo", "").strip() or None,
            data_incarico=f.get("data_incarico") or date.today().isoformat(),
            compenso_pattuito=compenso,
            note=f.get("note", "").strip(),
            tipo_compenso=f.get("tipo_compenso", TipoCompensoPrevisto.FISSO.value),
            tipo_procedimento=f.get("tipo_procedimento", TipoProcedimento.CIVILE_COGNIZIONE.value),
            tariffa_oraria=tariffa_oraria,
            numero_iscrizione_albo=f.get("numero_iscrizione_albo", "").strip(),
            ordine_avvocati=f.get("ordine_avvocati", "").strip(),
            informativa_art13_resa=bool(f.get("informativa_art13_resa")),
            clausola_adr_resa=bool(f.get("clausola_adr_resa")),
            patto_palmario=bool(f.get("patto_palmario")),
            quota_palmario_pct=quota_palmario,
            studio_piva=cfg.get("STUDIO_PIVA", ""),
            studio_cf=cfg.get("STUDIO_CF", ""),
            studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
        )
        flash(f"Conferimento incarico {c.numero} creato.", "success")
        from_page = f.get("from_page", "")
        if from_page == "preventivo":
            id_prev = f.get("id_preventivo", "").strip()
            if id_prev:
                return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_prev))
        if from_page == "cliente":
            return redirect(url_for("cartella_cliente", id_cliente=id_cliente))
        return redirect(url_for("preventivi.dettaglio_conferimento", id_conferimento=c.id))

    # GET
    clienti = gc.tutti()
    cliente_sel = gc.get(id_cliente) if id_cliente else None
    fascicoli = []
    if cliente_sel:
        fascicoli = [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]

    id_preventivo_pre = request.args.get("id_preventivo", "")
    preventivo_pre = gp.get_preventivo(id_preventivo_pre) if id_preventivo_pre else None
    from_page = request.args.get("from_page", "")
    id_fascicolo_pre = request.args.get("id_fascicolo", "")

    # Preventivi del cliente per il select
    preventivi_cliente = []
    if cliente_sel:
        preventivi_cliente = gp.preventivi_per_cliente(id_cliente)

    return render_template(
        "preventivi/form_conferimento.html",
        clienti=clienti,
        cliente_sel=cliente_sel,
        fascicoli=fascicoli,
        preventivo_pre=preventivo_pre,
        preventivi_cliente=preventivi_cliente,
        oggi=date.today(),
        from_page=from_page,
        id_fascicolo_pre=id_fascicolo_pre,
    )


# ================================================================ DETTAGLIO CONFERIMENTO

@preventivi.route("/conferimento/<id_conferimento>", methods=["GET"])
@_richiedi_login
def dettaglio_conferimento(id_conferimento: str):
    gp = _get_gp()
    c = gp.get_conferimento(id_conferimento)
    if not c:
        abort(404)
    cliente = get_clienti().get(c.id_cliente)
    fascicolo = get_fascicoli().get(c.id_fascicolo) if c.id_fascicolo else None
    preventivo = gp.get_preventivo(c.id_preventivo) if c.id_preventivo else None
    return render_template(
        "preventivi/dettaglio_conferimento.html",
        c=c,
        cliente=cliente,
        fascicolo=fascicolo,
        preventivo=preventivo,
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
        oggi=date.today(),
    )


# ================================================================ CAMBIA STATO CONFERIMENTO

@preventivi.route("/conferimento/<id_conferimento>/stato", methods=["POST"])
@_richiedi_login
def cambia_stato_conferimento(id_conferimento: str):
    from pct.preventivi import StatoConferimento
    gp = _get_gp()
    c = gp.get_conferimento(id_conferimento)
    if not c:
        abort(404)
    stato_str = request.form.get("stato", "")
    try:
        nuovo_stato = StatoConferimento(stato_str)
    except ValueError:
        flash("Stato non valido.", "danger")
        return redirect(url_for("preventivi.dettaglio_conferimento", id_conferimento=id_conferimento))
    gp.cambia_stato_conferimento(id_conferimento, nuovo_stato)
    flash(f"Stato aggiornato: {nuovo_stato.value}.", "success")
    return redirect(url_for("preventivi.dettaglio_conferimento", id_conferimento=id_conferimento))


# ================================================================ ELIMINA CONFERIMENTO

@preventivi.route("/conferimento/<id_conferimento>/elimina", methods=["POST"])
@_richiedi_login
def elimina_conferimento(id_conferimento: str):
    gp = _get_gp()
    c = gp.get_conferimento(id_conferimento)
    if not c:
        abort(404)
    gp.elimina_conferimento(id_conferimento)
    flash("Conferimento incarico eliminato.", "success")
    return redirect(url_for("preventivi.lista", tab="conferimenti"))


# ================================================================ PDF CONFERIMENTO

@preventivi.route("/conferimento/<id_conferimento>/pdf", methods=["GET"])
@_richiedi_login
def pdf_conferimento(id_conferimento: str):
    gp = _get_gp()
    c = gp.get_conferimento(id_conferimento)
    if not c:
        abort(404)
    cliente = get_clienti().get(c.id_cliente)
    fascicolo = get_fascicoli().get(c.id_fascicolo) if c.id_fascicolo else None
    preventivo = gp.get_preventivo(c.id_preventivo) if c.id_preventivo else None
    buf = _genera_pdf_conferimento(c, cliente, fascicolo, preventivo, current_app.config)
    nome_file = f"conferimento_incarico_{c.numero.replace('/', '-')}.pdf"
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=False, download_name=nome_file)


# ================================================================ AJAX fascicoli per cliente

@preventivi.route("/ajax/fascicoli/<id_cliente>")
@_richiedi_login
def ajax_fascicoli(id_cliente: str):
    from flask import jsonify
    fascicoli = [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]
    return jsonify([{"id": f.id, "titolo": f.titolo,
                     "numero_rg": f.numero_rg or ""} for f in fascicoli])


@preventivi.route("/ajax/preventivi/<id_cliente>")
@_richiedi_login
def ajax_preventivi(id_cliente: str):
    from flask import jsonify
    gp = _get_gp()
    prev = gp.preventivi_per_cliente(id_cliente)
    return jsonify([{"id": p.id, "numero": p.numero,
                     "oggetto": p.oggetto, "totale": p.totale} for p in prev])


@preventivi.route("/ajax/parametri_dm55")
@_richiedi_login
def ajax_parametri_dm55():
    """Restituisce i parametri D.M. 55/2014 per tipo procedimento e valore controversia."""
    from flask import jsonify
    from pct.preventivi import calcola_onorari_dm55, TABELLE_DM55
    tipo = request.args.get("tipo_procedimento", "")
    try:
        valore = float(request.args.get("valore", 0) or 0)
    except (ValueError, TypeError):
        valore = 0.0
    fasi_raw = request.args.get("fasi", "studio,introduttiva,istruttoria,decisionale")
    fasi = [f.strip() for f in fasi_raw.split(",") if f.strip()]
    if tipo not in TABELLE_DM55:
        return jsonify({"errore": "Tipo procedimento non supportato"}), 400
    risultato = calcola_onorari_dm55(tipo, valore, fasi)
    return jsonify(risultato)


# ================================================================ Generazione PDF preventivo

def _genera_pdf_preventivo(p, cliente, fascicolo, config) -> io.BytesIO:
    """Genera PDF professionale del preventivo con ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    except ImportError:
        buf = io.BytesIO()
        buf.write(f"Preventivo {p.numero}\nTotale: € {p.totale:.2f}".encode())
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
    style_body  = ParagraphStyle("body",  parent=styles["Normal"], fontSize=9, leading=13)
    style_small = ParagraphStyle("small", parent=styles["Normal"], fontSize=7.5, leading=11, textColor=GRAY_TEXT)
    style_h1    = ParagraphStyle("h1",    parent=styles["Normal"], fontSize=18, leading=22, textColor=PRIMARY, fontName="Helvetica-Bold")
    style_h2    = ParagraphStyle("h2",    parent=styles["Normal"], fontSize=11, leading=14, textColor=PRIMARY, fontName="Helvetica-Bold")
    style_bold  = ParagraphStyle("bold",  parent=style_body, fontName="Helvetica-Bold")

    studio_nome = config.get("STUDIO_NOME", "IUSENTRA")
    studio_piva = p.studio_piva or config.get("STUDIO_PIVA", "")
    studio_cf   = p.studio_cf   or config.get("STUDIO_CF", "")
    studio_ind  = p.studio_indirizzo or config.get("STUDIO_INDIRIZZO", "")

    nome_cliente = cliente.nome_completo if cliente else "Cliente sconosciuto"

    story = []

    # Header
    header_data = [[
        Paragraph(f"<b>{studio_nome}</b>", style_h2),
        Paragraph("PREVENTIVO PROFESSIONALE", ParagraphStyle(
            "ptit", parent=style_h1, alignment=TA_RIGHT)),
    ]]
    ht = Table(header_data, colWidths=["60%", "40%"])
    ht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(ht)

    info_right_txt = f"<b>N. {p.numero}</b><br/>Data: {p.data_emissione}"
    if p.data_scadenza:
        info_right_txt += f"<br/>Valido fino al: {p.data_scadenza}"
    info_left_txt = studio_ind or ""
    if studio_piva:
        info_left_txt += f"<br/>P.IVA {studio_piva}"
    if studio_cf:
        info_left_txt += f"<br/>C.F. {studio_cf}"

    info_tbl = Table([[
        Paragraph(info_left_txt.strip("<br/>"), style_small),
        Paragraph(info_right_txt, ParagraphStyle("itr", parent=style_small, alignment=TA_RIGHT)),
    ]], colWidths=["60%", "40%"])
    info_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(Spacer(1, 4*mm))
    story.append(info_tbl)
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 4*mm))

    # Destinatario
    story.append(Paragraph("Spettabile", style_small))
    story.append(Paragraph(f"<b>{nome_cliente}</b>", style_h2))
    if fascicolo:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f"Rif. pratica: {fascicolo.titolo}" + (f" · RG {fascicolo.numero_rg}" if fascicolo.numero_rg else ""),
            style_small))
    story.append(Spacer(1, 4*mm))

    # Oggetto
    story.append(Paragraph(f"<b>Oggetto:</b> {p.oggetto}", style_body))
    story.append(Spacer(1, 6*mm))

    # Voci
    story.append(Paragraph("Voci del preventivo", style_h2))
    story.append(Spacer(1, 2*mm))

    voci_data = [[
        Paragraph("<b>Descrizione</b>", style_bold),
        Paragraph("<b>Tipo</b>", ParagraphStyle("tb", parent=style_bold, alignment=TA_RIGHT)),
        Paragraph("<b>Importo</b>", ParagraphStyle("ib", parent=style_bold, alignment=TA_RIGHT)),
    ]]
    for v in p.voci:
        voci_data.append([
            Paragraph(v.descrizione, style_body),
            Paragraph(v.tipo.value, ParagraphStyle("tv", parent=style_small, alignment=TA_RIGHT)),
            Paragraph(f"€ {v.importo:,.2f}", ParagraphStyle("iv", parent=style_body, alignment=TA_RIGHT)),
        ])

    voci_tbl = Table(voci_data, colWidths=["60%", "20%", "20%"])
    voci_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(voci_tbl)
    story.append(Spacer(1, 4*mm))

    # Riepilogo
    rows = [("Imponibile", f"€ {p.imponibile:,.2f}")]
    if p.applica_cassa:
        rows.append(("Contributo Cassa Forense (4%)", f"€ {p.cassa_forense:,.2f}"))
    if p.applica_iva:
        rows.append((f"IVA 22% su € {p.base_iva:,.2f}", f"€ {p.iva:,.2f}"))
    rows.append(("TOTALE STIMATO", f"€ {p.totale:,.2f}"))

    rie_data = [
        [Paragraph(label, ParagraphStyle(
            "rl", parent=style_body,
            fontName="Helvetica-Bold" if "TOTALE" in label else "Helvetica",
            textColor=PRIMARY if "TOTALE" in label else colors.black,
            fontSize=11 if "TOTALE" in label else 9)),
         Paragraph(valore, ParagraphStyle(
            "rv", parent=style_body, alignment=TA_RIGHT,
            fontName="Helvetica-Bold" if "TOTALE" in label else "Helvetica",
            textColor=PRIMARY if "TOTALE" in label else colors.black,
            fontSize=11 if "TOTALE" in label else 9))]
        for label, valore in rows
    ]
    rie_tbl = Table(rie_data, colWidths=["75%", "25%"])
    rie_tbl.setStyle(TableStyle([
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, PRIMARY),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BG),
    ]))
    story.append(rie_tbl)
    story.append(Spacer(1, 6*mm))

    # Note + disclaimer
    if p.note:
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(p.note, style_small))
        story.append(Spacer(1, 3*mm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "Il presente preventivo ha valore indicativo ed è soggetto a variazioni in base all'effettivo sviluppo della pratica.",
        ParagraphStyle("disc", parent=style_small, alignment=TA_CENTER, fontName="Helvetica-Oblique")))
    story.append(Spacer(1, 4*mm))

    # Footer
    footer_txt = studio_nome
    if studio_piva:
        footer_txt += f" — P.IVA {studio_piva}"
    story.append(Paragraph(footer_txt, ParagraphStyle(
        "footer", parent=style_small, alignment=TA_CENTER)))

    doc.build(story)
    buf.seek(0)
    return buf


# ================================================================ Generazione PDF conferimento incarico

def _genera_pdf_conferimento(c, cliente, fascicolo, preventivo, config) -> io.BytesIO:
    """Genera lettera di conferimento di incarico in formato PDF."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT, TA_JUSTIFY
    except ImportError:
        buf = io.BytesIO()
        buf.write(f"Conferimento Incarico {c.numero}".encode())
        buf.seek(0)
        return buf

    PRIMARY   = colors.HexColor("#1a3a5c")
    LIGHT_BG  = colors.HexColor("#f4f6fa")
    GRAY_TEXT = colors.HexColor("#6b7280")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=25*mm, rightMargin=25*mm,
                             topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    style_body  = ParagraphStyle("body",  parent=styles["Normal"], fontSize=10, leading=15)
    style_just  = ParagraphStyle("just",  parent=style_body, alignment=TA_JUSTIFY)
    style_small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=11, textColor=GRAY_TEXT)
    style_h1    = ParagraphStyle("h1",    parent=styles["Normal"], fontSize=16, leading=20, textColor=PRIMARY, fontName="Helvetica-Bold")
    style_h2    = ParagraphStyle("h2",    parent=styles["Normal"], fontSize=11, leading=14, textColor=PRIMARY, fontName="Helvetica-Bold")
    style_bold  = ParagraphStyle("bold",  parent=style_body, fontName="Helvetica-Bold")

    studio_nome = config.get("STUDIO_NOME", "IUSENTRA")
    studio_piva = c.studio_piva or config.get("STUDIO_PIVA", "")
    studio_cf   = c.studio_cf   or config.get("STUDIO_CF", "")
    studio_ind  = c.studio_indirizzo or config.get("STUDIO_INDIRIZZO", "")

    nome_cliente = cliente.nome_completo if cliente else "Cliente sconosciuto"

    story = []

    # Header studio
    header_data = [[
        Paragraph(f"<b>{studio_nome}</b>", style_h2),
        Paragraph("CONFERIMENTO DI INCARICO", ParagraphStyle(
            "ctit", parent=style_h1, alignment=TA_RIGHT, fontSize=14)),
    ]]
    ht = Table(header_data, colWidths=["55%", "45%"])
    ht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(ht)

    info_left_txt = studio_ind or ""
    if studio_piva:
        info_left_txt += f"<br/>P.IVA {studio_piva}"
    if studio_cf:
        info_left_txt += f"<br/>C.F. {studio_cf}"
    info_right_txt = f"<b>N. {c.numero}</b><br/>Data: {c.data_incarico}"

    info_tbl = Table([[
        Paragraph(info_left_txt.strip("<br/>"), style_small),
        Paragraph(info_right_txt, ParagraphStyle("itr", parent=style_small, alignment=TA_RIGHT)),
    ]], colWidths=["55%", "45%"])
    info_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(Spacer(1, 3*mm))
    story.append(info_tbl)
    story.append(Spacer(1, 3*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 5*mm))

    # Destinatario
    story.append(Paragraph("Spettabile", style_small))
    story.append(Paragraph(f"<b>{nome_cliente}</b>", style_h2))
    story.append(Spacer(1, 6*mm))

    # Corpo lettera
    story.append(Paragraph(f"<b>Oggetto:</b> Conferimento incarico professionale — {c.oggetto}", style_bold))
    story.append(Spacer(1, 5*mm))

    story.append(Paragraph(
        f"Con la presente il/la sottoscritto/a <b>{nome_cliente}</b> conferisce incarico professionale "
        f"all'<b>Avv. {c.avvocato_referente}</b> dello {studio_nome} per la trattazione della seguente questione:",
        style_just))
    story.append(Spacer(1, 3*mm))

    # Riquadro oggetto
    obj_tbl = Table([[Paragraph(c.oggetto, style_body)]], colWidths=["100%"])
    obj_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("BOX",        (0, 0), (-1, -1), 0.5, PRIMARY),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(obj_tbl)
    story.append(Spacer(1, 5*mm))

    if fascicolo:
        story.append(Paragraph(
            f"Il presente incarico è riferito alla pratica: <b>{fascicolo.titolo}</b>" +
            (f" (RG {fascicolo.numero_rg})" if fascicolo.numero_rg else "") + ".",
            style_just))
        story.append(Spacer(1, 3*mm))

    # Tipo procedimento
    story.append(Paragraph(
        f"Tipo di procedimento: <b>{c.tipo_procedimento}</b>.",
        style_just))
    story.append(Spacer(1, 3*mm))

    # Compenso (art. 13 co. 2 L. 247/2012)
    story.append(Paragraph("<b>Compenso professionale</b>", style_bold))
    story.append(Spacer(1, 2*mm))
    if c.tipo_compenso == "Compenso orario" and c.tariffa_oraria > 0:
        story.append(Paragraph(
            f"Il compenso è determinato in base al tempo impiegato, con tariffa oraria di "
            f"<b>€ {c.tariffa_oraria:,.2f}/ora</b> (oltre Contributo Cassa Forense 4% e IVA 22%).",
            style_just))
    elif c.compenso_pattuito > 0:
        story.append(Paragraph(
            f"Modalità: <b>{c.tipo_compenso}</b>.<br/>"
            f"Compenso concordato: <b>€ {c.compenso_pattuito:,.2f}</b> "
            f"(oltre Contributo Cassa Forense 4% ed IVA 22%), "
            f"salvo adeguamento in ragione della complessità e dello sviluppo della pratica.",
            style_just))
    else:
        story.append(Paragraph(
            "Il compenso professionale sarà determinato al termine dell'incarico in conformità "
            "ai parametri forensi di cui al <b>D.M. 55/2014</b> (come modificato dal D.M. 147/2022) "
            "e successive modifiche, salvo preventivo concordato separatamente.",
            style_just))
    if c.patto_palmario and c.quota_palmario_pct > 0:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f"È altresì concordato, ai sensi dell'art. 13 co. 4 L. 247/2012, "
            f"un compenso aggiuntivo pari al <b>{c.quota_palmario_pct:.1f}%</b> "
            "sul vantaggio economico conseguito dal cliente (patto di palmario).",
            style_just))
    story.append(Spacer(1, 4*mm))

    # Rif. preventivo
    if preventivo:
        story.append(Paragraph(
            f"Il presente incarico fa riferimento al preventivo n. <b>{preventivo.numero}</b> "
            f"del {preventivo.data_emissione} (totale stimato € {preventivo.totale:,.2f}).",
            style_small))
        story.append(Spacer(1, 3*mm))

    # Note aggiuntive
    if c.note:
        story.append(Paragraph(c.note, style_just))
        story.append(Spacer(1, 4*mm))

    # ---- Informativa obbligatoria art. 13 L. 247/2012 ----
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d1d5db")))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "<b>Informativa ai sensi dell'art. 13 L. 247/2012 — Ordinamento della professione forense</b>",
        ParagraphStyle("inf_h", parent=style_bold, fontSize=9, textColor=PRIMARY)))
    story.append(Spacer(1, 2*mm))

    inf_style = ParagraphStyle("inf", parent=styles["Normal"], fontSize=8, leading=11,
                               textColor=colors.HexColor("#374151"))
    story.append(Paragraph(
        "Ai sensi dell'art. 13 L. 247/2012 il professionista è tenuto, all'atto del conferimento "
        "dell'incarico, a rendere noto al cliente il grado di complessità dell'incarico, fornendo "
        "tutte le informazioni utili circa gli oneri ipotizzabili dal momento del conferimento "
        "alla conclusione dell'incarico, nonché a comunicare gli estremi della propria polizza "
        "assicurativa per la responsabilità professionale.",
        inf_style))
    story.append(Spacer(1, 2*mm))

    # Clausola ADR/mediazione (art. 4 D.Lgs. 28/2010 + art. 13 L. 247/2012)
    if c.clausola_adr_resa:
        story.append(Paragraph(
            "<b>Informativa su strumenti alternativi di risoluzione delle controversie (ADR):</b> "
            "L'avvocato ha informato il cliente della possibilità di avvalersi, ove applicabile, "
            "degli strumenti di risoluzione alternativa delle controversie previsti dalla legge "
            "(mediazione civile e commerciale ex D.Lgs. 28/2010, negoziazione assistita ex "
            "D.L. 132/2014, arbitrato). Il cliente dichiara di aver ricevuto tale informativa.",
            inf_style))
        story.append(Spacer(1, 2*mm))

    # Albo professionale
    albo_txt = f"Avv. {c.avvocato_referente}"
    if c.numero_iscrizione_albo:
        albo_txt += f", iscritto/a al n. {c.numero_iscrizione_albo}"
    if c.ordine_avvocati:
        albo_txt += f" dell'{c.ordine_avvocati}"
    story.append(Paragraph(albo_txt + ".", inf_style))
    story.append(Spacer(1, 4*mm))

    # ---- Sezione firme ----
    story.append(Spacer(1, 6*mm))

    # Firma avvocato
    avv_firma = f"<b>Per lo Studio</b><br/>Avv. {c.avvocato_referente}"
    if c.numero_iscrizione_albo:
        avv_firma += f"<br/><font size='7'>Iscritto n. {c.numero_iscrizione_albo}"
        if c.ordine_avvocati:
            avv_firma += f" — {c.ordine_avvocati}"
        avv_firma += "</font>"
    avv_firma += "<br/><br/><br/>_________________________"

    firme_data = [[
        Paragraph(avv_firma, style_body),
        Paragraph(
            "<b>Il/La Cliente</b><br/>Firma per accettazione<br/><br/><br/>_________________________",
            style_body),
    ]]
    firme_tbl = Table(firme_data, colWidths=["50%", "50%"])
    firme_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    story.append(firme_tbl)
    story.append(Spacer(1, 5*mm))

    # Dichiarazione informativa
    if c.informativa_art13_resa:
        story.append(Paragraph(
            "Il/La sottoscritto/a cliente dichiara di aver ricevuto l'informativa ai sensi "
            "dell'art. 13 L. 247/2012 e di accettare le condizioni del presente incarico.",
            ParagraphStyle("dich", parent=inf_style, fontSize=7.5)))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(
            "Firma per ricevuta informativa: _________________________",
            ParagraphStyle("dich2", parent=inf_style, fontSize=8)))
        story.append(Spacer(1, 2*mm))

    story.append(Paragraph(
        f"Luogo e data: _________________________, {c.data_incarico}", style_body))

    # Footer
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
    story.append(Spacer(1, 2*mm))
    footer_txt = studio_nome
    if studio_piva:
        footer_txt += f" — P.IVA {studio_piva}"
    if c.numero_iscrizione_albo and c.ordine_avvocati:
        footer_txt += f" — Albo n. {c.numero_iscrizione_albo} ({c.ordine_avvocati})"
    story.append(Paragraph(footer_txt, ParagraphStyle(
        "footer", parent=style_small, alignment=TA_CENTER)))

    doc.build(story)
    buf.seek(0)
    return buf
