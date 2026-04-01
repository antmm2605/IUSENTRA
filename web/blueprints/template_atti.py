"""
web/blueprints/template_atti.py — Generatore atti legali da template.

URL base: /template-atti/
"""
from __future__ import annotations

import io
from datetime import date

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, send_file, url_for, current_app)

from web.helpers import get_clienti, get_fascicoli, get_utenti

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


def _valore_form(value):
    if isinstance(value, list):
        return "\n".join([str(item) for item in value if str(item).strip()])
    return value or ""


def _contesto_compilatore(model_code: str, *, payload: dict, selected_cliente=None,
                          selected_fascicolo=None, errors: dict | None = None):
    from pct.compilatore_atti import (
        get_modello,
        campi_base_visibili,
        campi_extra_modello,
        opzioni_campo,
        professional_guidance_for_model,
        suggested_attachments_for_model,
        suggested_clauses_for_model,
        validation_rules_for_model,
    )
    model = get_modello(model_code)
    clienti = get_clienti().tutti()
    fascicoli = get_fascicoli().tutti()
    utenti = get_utenti().tutti(solo_attivi=True)
    base_fields = campi_base_visibili()
    extra_fields = campi_extra_modello(model_code)
    field_options = {}
    for field in base_fields + extra_fields:
        if field["type"] == "select":
            field_options[field["name"]] = opzioni_campo(
                field["name"],
                fascicoli=fascicoli,
                utenti=utenti,
                model=model,
            )
    form_values = {key: _valore_form(value) for key, value in payload.items()}
    return {
        "model": model,
        "clienti": clienti,
        "fascicoli": fascicoli,
        "utenti": utenti,
        "base_fields": base_fields,
        "extra_fields": extra_fields,
        "field_options": field_options,
        "form_values": form_values,
        "payload": payload,
        "errors": errors or {},
        "selected_cliente": selected_cliente,
        "selected_fascicolo": selected_fascicolo,
        "guidance": professional_guidance_for_model(model_code),
        "suggested_attachments": suggested_attachments_for_model(model_code),
        "suggested_clauses": suggested_clauses_for_model(model_code),
        "validation_rules": validation_rules_for_model(model_code),
    }


# ================================================================ LISTA

@template_atti.route("/", methods=["GET"])
@_richiedi_login
def lista():
    gt = _get_gt()
    templates = gt.tutti()
    from pct.template_atti import CATEGORIE
    from pct.compilatore_atti import modelli_per_area
    return render_template(
        "template_atti/lista.html",
        templates=templates,
        categorie=CATEGORIE,
        modelli_compilatore=modelli_per_area(),
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


@template_atti.route("/compila/<model_code>", methods=["GET", "POST"])
@_richiedi_login
def compila(model_code: str):
    from pct.compilatore_atti import (
        get_modello,
        prefill_payload,
        merge_payload_with_form,
        validate_payload,
        render_compiled_act,
    )
    model = get_modello(model_code)
    if not model:
        abort(404)

    id_cliente = request.values.get("id_cliente", "").strip()
    id_fascicolo = request.values.get("id_fascicolo", "").strip()

    clienti_repo = get_clienti()
    fascicoli_repo = get_fascicoli()
    selected_cliente = clienti_repo.get(id_cliente) if id_cliente else None
    selected_fascicolo = fascicoli_repo.get(id_fascicolo) if id_fascicolo else None
    if selected_fascicolo and not selected_cliente and getattr(selected_fascicolo, "id_cliente", ""):
        selected_cliente = clienti_repo.get(selected_fascicolo.id_cliente)
        id_cliente = getattr(selected_cliente, "id", "") if selected_cliente else id_cliente

    initial_payload = prefill_payload(
        model_code,
        fascicolo=selected_fascicolo,
        cliente=selected_cliente,
        utente=g.get("utente_corrente"),
        config=current_app.config,
    )

    if request.method == "POST":
        form_data = request.form.to_dict(flat=True)
        form_data["case_id"] = id_fascicolo
        if id_cliente and not form_data.get("client_or_sender"):
            form_data["client_or_sender"] = getattr(selected_cliente, "nome_completo", "")
        payload = merge_payload_with_form(
            model_code,
            initial_payload=initial_payload,
            form_data=form_data,
        )
        errors = validate_payload(model_code, payload)
        if errors:
            flash("Completa i campi obbligatori evidenziati prima di generare l'atto.", "warning")
            ctx = _contesto_compilatore(
                model_code,
                payload=payload,
                selected_cliente=selected_cliente,
                selected_fascicolo=selected_fascicolo,
                errors=errors,
            )
            return render_template(
                "template_atti/compilatore.html",
                **ctx,
            )

        testo_generato = render_compiled_act(model_code, payload)
        ctx = _contesto_compilatore(
            model_code,
            payload=payload,
            selected_cliente=selected_cliente,
            selected_fascicolo=selected_fascicolo,
        )
        return render_template(
            "template_atti/anteprima_compilatore.html",
            model=model,
            payload=payload,
            form_values={key: _valore_form(value) for key, value in payload.items()},
            testo_generato=testo_generato,
            selected_cliente=selected_cliente,
            selected_fascicolo=selected_fascicolo,
            guidance=ctx["guidance"],
            suggested_attachments=ctx["suggested_attachments"],
            suggested_clauses=ctx["suggested_clauses"],
        )

    return render_template(
        "template_atti/compilatore.html",
        **_contesto_compilatore(
            model_code,
            payload=initial_payload,
            selected_cliente=selected_cliente,
            selected_fascicolo=selected_fascicolo,
        ),
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


@template_atti.route("/compila/<model_code>/pdf", methods=["POST"])
@_richiedi_login
def compila_pdf(model_code: str):
    from pct.compilatore_atti import get_modello
    model = get_modello(model_code)
    if not model:
        abort(404)
    testo = request.form.get("testo_generato", "")
    titolo = request.form.get("title", "") or model["name"]
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
