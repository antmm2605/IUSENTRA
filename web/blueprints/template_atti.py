"""
web/blueprints/template_atti.py — Generatore atti legali da template.

URL base: /template-atti/
"""
from __future__ import annotations

import io
from datetime import date

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, send_file, url_for, current_app)

from web.helpers import get_clienti, get_fascicoli

template_atti = Blueprint("template_atti", __name__, url_prefix="/template-atti")


def _get_gt():
    from pct.template_atti import GestioneTemplateAtti
    return GestioneTemplateAtti(
        db_path=current_app.config.get("TEMPLATE_ATTI_DB", "./template_atti/templates.json")
    )


def _richiedi_login(f):
    from functools import wraps
    @wraps(f)
    def w(*a, **kw):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


def _variabili_base(config):
    return {
        "data_oggi":         date.today().strftime("%d/%m/%Y"),
        "studio_nome":       config.get("STUDIO_NOME", "Studio Legale PCT"),
        "studio_indirizzo":  config.get("STUDIO_INDIRIZZO", ""),
        "studio_iban":       config.get("STUDIO_IBAN", ""),
        "avvocato_nome":     config.get("STUDIO_AVVOCATO", config.get("STUDIO_NOME", "Avvocato")),
    }


# ================================================================ LISTA

@template_atti.route("/", methods=["GET"])
@_richiedi_login
def lista():
    gt = _get_gt()
    templates = gt.tutti()
    from pct.template_atti import CATEGORIE
    return render_template(
        "template_atti/lista.html",
        templates=templates,
        categorie=CATEGORIE,
    )


# ================================================================ NUOVO TEMPLATE

@template_atti.route("/nuovo", methods=["GET", "POST"])
@_richiedi_login
def nuovo():
    from pct.template_atti import CATEGORIE
    if request.method == "POST":
        gt = _get_gt()
        titolo   = request.form.get("titolo", "").strip()
        categoria = request.form.get("categoria", "Altro")
        corpo    = request.form.get("corpo", "").strip()
        note     = request.form.get("note", "").strip()
        if not titolo or not corpo:
            flash("Titolo e corpo obbligatori.", "danger")
            return render_template("template_atti/form.html", categorie=CATEGORIE,
                                   t=None, form=request.form)
        t = gt.crea(titolo=titolo, categoria=categoria, corpo=corpo, note=note)
        flash(f"Template '{t.titolo}' creato.", "success")
        return redirect(url_for("template_atti.lista"))
    return render_template("template_atti/form.html", categorie=CATEGORIE, t=None, form={})


# ================================================================ MODIFICA

@template_atti.route("/<id_template>/modifica", methods=["GET", "POST"])
@_richiedi_login
def modifica(id_template: str):
    from pct.template_atti import CATEGORIE
    gt = _get_gt()
    t = gt.get(id_template)
    if not t:
        abort(404)
    if t.builtin:
        flash("I template built-in non possono essere modificati. Clonalo prima.", "warning")
        return redirect(url_for("template_atti.lista"))
    if request.method == "POST":
        try:
            gt.aggiorna(id_template,
                        titolo=request.form.get("titolo", t.titolo),
                        categoria=request.form.get("categoria", t.categoria),
                        corpo=request.form.get("corpo", t.corpo),
                        note=request.form.get("note", t.note))
            flash("Template aggiornato.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("template_atti.lista"))
    return render_template("template_atti/form.html", categorie=CATEGORIE, t=t, form=t.to_dict())


# ================================================================ CLONA

@template_atti.route("/<id_template>/clona", methods=["POST"])
@_richiedi_login
def clona(id_template: str):
    gt = _get_gt()
    t = gt.get(id_template)
    if not t:
        abort(404)
    nuovo = gt.crea(
        titolo=f"[Copia] {t.titolo}",
        categoria=t.categoria,
        corpo=t.corpo,
        note=t.note,
    )
    flash(f"Template clonato: '{nuovo.titolo}'.", "success")
    return redirect(url_for("template_atti.modifica", id_template=nuovo.id))


# ================================================================ ELIMINA

@template_atti.route("/<id_template>/elimina", methods=["POST"])
@_richiedi_login
def elimina(id_template: str):
    gt = _get_gt()
    try:
        gt.elimina(id_template)
        flash("Template eliminato.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    return redirect(url_for("template_atti.lista"))


# ================================================================ USA TEMPLATE (form variabili)

@template_atti.route("/<id_template>/usa", methods=["GET", "POST"])
@_richiedi_login
def usa(id_template: str):
    gt = _get_gt()
    t = gt.get(id_template)
    if not t:
        abort(404)
    clienti   = get_clienti().tutti()
    fascicoli_tutti = get_fascicoli().tutti()

    if request.method == "POST":
        f = request.form
        id_cliente   = f.get("id_cliente", "").strip()
        id_fascicolo = f.get("id_fascicolo", "").strip()

        cliente  = get_clienti().get(id_cliente) if id_cliente else None
        fascicolo = get_fascicoli().get(id_fascicolo) if id_fascicolo else None

        variabili = _variabili_base(current_app.config)
        variabili["cliente"]             = cliente
        variabili["fascicolo"]           = fascicolo
        variabili["destinatario_nome"]   = f.get("destinatario_nome", "")
        variabili["destinatario_indirizzo"] = f.get("destinatario_indirizzo", "")
        variabili["oggetto_diffida"]     = f.get("oggetto_diffida", "")
        variabili["importo_dovuto"]      = f.get("importo_dovuto", "")
        variabili["titolo_credito"]      = f.get("titolo_credito", "")
        variabili["termine_giorni"]      = f.get("termine_giorni", "15")
        variabili["tribunale_competente"] = f.get("tribunale_competente", "")
        variabili["durata_anni"]         = f.get("durata_anni", "5")

        try:
            testo_generato = gt.renderizza(id_template, variabili)
        except Exception as e:
            flash(f"Errore nella generazione: {e}", "danger")
            testo_generato = ""

        return render_template(
            "template_atti/anteprima.html",
            t=t,
            testo_generato=testo_generato,
            id_template=id_template,
            variabili_json=_variabili_safe(variabili),
            cliente=cliente,
            fascicolo=fascicolo,
        )

    fascicoli = []
    if request.args.get("id_cliente"):
        fascicoli = [f for f in fascicoli_tutti
                     if f.id_cliente == request.args.get("id_cliente")]

    return render_template(
        "template_atti/usa.html",
        t=t,
        clienti=clienti,
        fascicoli=fascicoli,
    )


# ================================================================ PDF

@template_atti.route("/<id_template>/pdf", methods=["POST"])
@_richiedi_login
def pdf(id_template: str):
    gt = _get_gt()
    t = gt.get(id_template)
    if not t:
        abort(404)
    testo = request.form.get("testo_generato", "")
    titolo = t.titolo
    buf = _genera_pdf(titolo, testo, current_app.config)
    nome_file = titolo.lower().replace(" ", "_").replace("/", "-") + ".pdf"
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=False, download_name=nome_file)


# ================================================================ helpers

def _variabili_safe(v: dict) -> dict:
    """Serializza le variabili per il form nascosto (solo stringhe)."""
    safe = {}
    for k, val in v.items():
        if isinstance(val, str):
            safe[k] = val
    return safe


def _genera_pdf(titolo: str, testo: str, config: dict) -> io.BytesIO:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                         Spacer, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        PRIMARY = colors.HexColor("#1a3a5c")
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                 leftMargin=25*mm, rightMargin=25*mm,
                                 topMargin=25*mm, bottomMargin=25*mm)
        styles = getSampleStyleSheet()
        style_body = ParagraphStyle("body", parent=styles["Normal"],
                                    fontSize=10, leading=15,
                                    fontName="Helvetica")
        style_title = ParagraphStyle("title", parent=styles["Normal"],
                                     fontSize=13, leading=17,
                                     fontName="Helvetica-Bold",
                                     textColor=PRIMARY,
                                     alignment=TA_CENTER)
        story = []
        story.append(Paragraph(titolo.upper(), style_title))
        story.append(Spacer(1, 6*mm))
        story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY))
        story.append(Spacer(1, 6*mm))
        for riga in testo.split("\n"):
            if riga.strip():
                story.append(Paragraph(riga.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                                       style_body))
            else:
                story.append(Spacer(1, 4*mm))
        studio_nome = config.get("STUDIO_NOME", "Studio Legale PCT")
        story.append(Spacer(1, 8*mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8")))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(studio_nome, ParagraphStyle(
            "footer", parent=style_body, fontSize=8,
            textColor=colors.HexColor("#6b7280"), alignment=TA_CENTER)))
        doc.build(story)
        buf.seek(0)
        return buf
    except ImportError:
        buf = io.BytesIO(testo.encode("utf-8"))
        buf.seek(0)
        return buf
