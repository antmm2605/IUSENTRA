"""
web/blueprints/template_atti.py — Generatore atti legali da template.

URL base: /template-atti/
"""
from __future__ import annotations

import io
import json
import re
from datetime import date
from html import escape
from types import SimpleNamespace

from flask import (Blueprint, abort, current_app, flash, g, jsonify,
                   redirect, render_template, request, send_file, url_for)

from web.helpers import get_clienti, get_fascicoli, get_soggetti, get_utenti

template_atti = Blueprint("template_atti", __name__, url_prefix="/template-atti")


def _get_gt():
    from pct.template_atti import GestioneTemplateAtti
    return GestioneTemplateAtti(
        db_path=current_app.config.get("TEMPLATE_ATTI_DB", "./template_atti/templates.json")
    )


def _get_gp():
    from pct.template_atti import GestionePreferenzeTemplateAtti, percorso_preferenze_editor

    prefs_path = current_app.config.get("TEMPLATE_ATTI_PREFS_DB")
    if not prefs_path:
        prefs_path = percorso_preferenze_editor(
            current_app.config.get("TEMPLATE_ATTI_DB", "./template_atti/templates.json")
        )
    return GestionePreferenzeTemplateAtti(prefs_path=prefs_path)


def _get_assistente_redazionale():
    from pct.assistente_redazionale import AssistenteRedazionale

    return AssistenteRedazionale(
        audit_db_path=current_app.config.get("REDACTION_ASSISTANT_DB", "./intelligence/assistente_redazionale.json"),
        office_cache_path=current_app.config.get("UFFICI_GIUDIZIARI_DB", "") or current_app.config.get("REGINDE_DB", ""),
        pst_wsdl_catalog_zip_path=current_app.config.get("PST_WSDL_CATALOG_ZIP", ""),
        pst_official_cache_path=current_app.config.get("PST_OFFICIAL_CACHE", ""),
        pst_catalog_endpoint=current_app.config.get("PST_SOAP_CATALOGO_UG_ENDPOINT", ""),
        pst_timeout=float(current_app.config.get("PST_SOAP_TIMEOUT", 8.0) or 8.0),
    )


@template_atti.context_processor
def _inject_editor_preferences():
    from pct.template_atti import DEFAULT_EDITOR_LAYOUT, catalogo_font_editor

    return {
        "editor_preferences": _get_gp().carica(),
        "editor_default_preferences": DEFAULT_EDITOR_LAYOUT,
        "editor_font_choices": catalogo_font_editor(),
    }


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


def _namespace_from_mapping(mapping: dict | None = None):
    return SimpleNamespace(**(mapping or {}))


def _soggetto_template_namespace(soggetto, *, parte=None):
    if not soggetto:
        return None
    ruolo = getattr(parte, "ruolo", None)
    note = getattr(parte, "note", "") if parte else ""
    return SimpleNamespace(
        id=getattr(soggetto, "id", ""),
        nome_completo=getattr(soggetto, "nome_completo", ""),
        identificativo=getattr(soggetto, "identificativo", ""),
        codice_fiscale=getattr(soggetto, "codice_fiscale", ""),
        partita_iva=getattr(soggetto, "partita_iva", ""),
        qualifica=getattr(soggetto, "qualifica", ""),
        email=getattr(getattr(soggetto, "recapiti", None), "email", ""),
        pec=getattr(getattr(soggetto, "recapiti", None), "pec", ""),
        telefono=(
            getattr(getattr(soggetto, "recapiti", None), "telefono", "")
            or getattr(getattr(soggetto, "recapiti", None), "cellulare", "")
        ),
        indirizzo=str(getattr(soggetto, "indirizzo", "") or ""),
        ruolo=getattr(ruolo, "value", ""),
        ruolo_label=getattr(ruolo, "label", ""),
        note=note,
    )


def _build_parti_template_context(id_fascicolo: str):
    empty = _namespace_from_mapping(
        {
            "elenco": [],
            "assistiti": [],
            "controparti": [],
            "difensori_controparte": [],
            "altri": [],
            "assistito_principale": None,
            "controparte_principale": None,
            "difensore_controparte_principale": None,
        }
    )
    if not id_fascicolo:
        return [], empty

    pairs = get_soggetti().parti_fascicolo(id_fascicolo)
    elenco = [_soggetto_template_namespace(soggetto, parte=parte) for parte, soggetto in pairs]
    assistiti = [item for item in elenco if item and item.ruolo == "ASSISTITO"]
    controparti = [item for item in elenco if item and item.ruolo in {"CONTROPARTE", "CREDITORE", "DEBITORE"}]
    difensori_controparte = [item for item in elenco if item and item.ruolo == "DIFENSORE_CONTROPARTE"]
    altri = [
        item
        for item in elenco
        if item and item.ruolo not in {"ASSISTITO", "CONTROPARTE", "CREDITORE", "DEBITORE", "DIFENSORE_CONTROPARTE"}
    ]
    return elenco, _namespace_from_mapping(
        {
            "elenco": elenco,
            "assistiti": assistiti,
            "controparti": controparti,
            "difensori_controparte": difensori_controparte,
            "altri": altri,
            "assistito_principale": assistiti[0] if assistiti else None,
            "controparte_principale": controparti[0] if controparti else None,
            "difensore_controparte_principale": difensori_controparte[0] if difensori_controparte else None,
        }
    )


def _valore_form(value):
    if isinstance(value, list):
        return "\n".join([str(item) for item in value if str(item).strip()])
    return value or ""


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _build_correction_context() -> dict:
    intent = (request.args.get("intent", "") or "").strip()
    focus_field = (request.args.get("focus_field", "") or "").strip()
    highlight_fields = _split_csv(request.args.get("highlight_fields", ""))
    title = (request.args.get("correction_title", "") or "").strip()
    help_text = (request.args.get("correction_help", "") or "").strip()
    if not any([intent, focus_field, highlight_fields, title, help_text]):
        return {}
    return {
        "active": True,
        "intent": intent,
        "focus_field": focus_field,
        "highlight_fields": highlight_fields,
        "title": title or "Correzione guidata",
        "help": help_text or "Completa i campi evidenziati per superare il controllo di conformita'.",
    }


def _contesto_compilatore(model_code: str, *, payload: dict, selected_cliente=None,
                          selected_fascicolo=None, errors: dict | None = None,
                          assistant_analysis: dict | None = None,
                          correction_context: dict | None = None):
    from pct.compilatore_atti import (
        opzioni_campo,
        wizard_schema_modello,
    )
    schema = wizard_schema_modello(model_code)
    model = schema["model"]
    clienti = get_clienti().tutti()
    fascicoli = get_fascicoli().tutti()
    utenti = get_utenti().tutti(solo_attivi=True)
    base_fields = schema["base_fields"]
    extra_fields = schema["extra_fields"]
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
        "guidance": schema["guidance"],
        "suggested_attachments": schema["suggested_attachments"],
        "suggested_clauses": schema["suggested_clauses"],
        "validation_rules": schema["validation_rules"],
        "sections": schema["sections"],
        "renderer_name": schema["renderer"],
        "prefill_map": schema["prefill_map"],
        "assistant_analysis": assistant_analysis or {},
        "correction_context": correction_context or {},
    }


def _resolve_compiler_context(model_code: str):
    from pct.compilatore_atti import (
        merge_payload_with_form,
        prefill_payload,
    )

    if request.method == "POST":
        id_cliente = (
            request.form.get("id_cliente", "").strip()
            or request.args.get("id_cliente", "").strip()
        )
        id_fascicolo = (
            request.form.get("id_fascicolo", "").strip()
            or request.form.get("case_id", "").strip()
            or request.args.get("id_fascicolo", "").strip()
        )
    else:
        id_cliente = (
            request.args.get("id_cliente", "").strip()
            or request.form.get("id_cliente", "").strip()
        )
        id_fascicolo = (
            request.args.get("id_fascicolo", "").strip()
            or request.form.get("id_fascicolo", "").strip()
            or request.form.get("case_id", "").strip()
        )

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
    payload = initial_payload
    if request.method == "POST":
        form_data = request.form.to_dict(flat=True)
        form_data["case_id"] = form_data.get("case_id", "").strip() or id_fascicolo
        if id_cliente and not form_data.get("client_or_sender"):
            form_data["client_or_sender"] = getattr(selected_cliente, "nome_completo", "")
        payload = merge_payload_with_form(
            model_code,
            initial_payload=initial_payload,
            form_data=form_data,
        )
    return {
        "id_cliente": id_cliente,
        "id_fascicolo": id_fascicolo,
        "selected_cliente": selected_cliente,
        "selected_fascicolo": selected_fascicolo,
        "initial_payload": initial_payload,
        "payload": payload,
        "correction_context": _build_correction_context(),
    }


def _build_assistant_analysis(model_code: str, *, payload: dict, selected_cliente=None, selected_fascicolo=None):
    return _get_assistente_redazionale().analyze(
        model_code,
        payload,
        fascicolo=selected_fascicolo,
        cliente=selected_cliente,
        utente=g.get("utente_corrente"),
    ).to_dict()


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


# ================================================================ CATALOGO ATTI

@template_atti.route("/catalogo", methods=["GET"])
@_richiedi_login
def catalogo():
    from pct.compilatore_atti import MODELS, AREA_LABELS, AREA_ORDINE, get_essential_docs
    from pct.motore_preventivo import catalogo_wizard

    # Raggruppa i modelli del compilatore per area con metadati
    area_groups: list[dict] = []
    for area_key in AREA_ORDINE:
        modelli = []
        for m in MODELS:
            if m["area"] == area_key:
                modelli.append({**m, "essential_docs": get_essential_docs(m["code"])})
        if modelli:
            area_groups.append({
                "area_key": area_key,
                "area_label": AREA_LABELS.get(area_key, area_key.title()),
                "modelli": modelli,
            })

    # Catalogo piatto per JS (ricerca client-side)
    catalogo_flat = []
    for grp in area_groups:
        for m in grp["modelli"]:
            catalogo_flat.append({
                "code":  m["code"],
                "name":  m["name"],
                "area":  grp["area_key"],
                "area_label": grp["area_label"],
                "url":   url_for("template_atti.compila", model_code=m["code"]),
            })

    # Tipologie del wizard preventivi con mapping verso atti (per la sezione "da pratica")
    try:
        from pct.motore_preventivo import catalogo_wizard as _cw
        wizard_cat = _cw()
    except Exception:
        wizard_cat = {}
    from pct.compilatore_atti import PRATICA_TO_MODELS, MODEL_INDEX
    wizard_tipologie = []
    for area_name, items in wizard_cat.items():
        for tip in items:
            pid = tip.get("id", "")
            codes = PRATICA_TO_MODELS.get(pid, [])
            modelli_atti = [{"code": c, "name": MODEL_INDEX[c]["name"]} for c in codes if c in MODEL_INDEX]
            if modelli_atti:
                wizard_tipologie.append({
                    "id": pid,
                    "label": tip.get("label", pid),
                    "area": area_name,
                    "modelli_atti": modelli_atti,
                })

    return render_template(
        "template_atti/catalogo.html",
        area_groups=area_groups,
        catalogo_flat=catalogo_flat,
        wizard_tipologie=wizard_tipologie,
        oggi=date.today(),
    )


@template_atti.route("/api/modelli-per-pratica/<id_pratica>", methods=["GET"])
@_richiedi_login
def api_modelli_per_pratica(id_pratica: str):
    from pct.compilatore_atti import get_modelli_per_pratica
    modelli = get_modelli_per_pratica(id_pratica)
    return jsonify([{"code": m["code"], "name": m["name"], "area": m["area"]} for m in modelli])


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
        soggetti_fascicolo, parti = _build_parti_template_context(id_fascicolo)
        variabili["cliente"]             = cliente
        variabili["fascicolo"]           = fascicolo
        variabili["soggetti"]            = soggetti_fascicolo
        variabili["parti"]               = parti
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
            editor_html=_to_editor_html(testo_generato),
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
        validate_payload,
        render_compiled_act,
    )
    model = get_modello(model_code)
    if not model:
        abort(404)
    resolved = _resolve_compiler_context(model_code)
    id_cliente = resolved["id_cliente"]
    id_fascicolo = resolved["id_fascicolo"]
    selected_cliente = resolved["selected_cliente"]
    selected_fascicolo = resolved["selected_fascicolo"]
    initial_payload = resolved["initial_payload"]
    payload = resolved["payload"]
    correction_context = resolved["correction_context"]
    assistant_analysis = _build_assistant_analysis(
        model_code,
        payload=payload,
        selected_cliente=selected_cliente,
        selected_fascicolo=selected_fascicolo,
    )

    if request.method == "POST":
        errors = validate_payload(model_code, payload)
        blockers = [issue for issue in assistant_analysis.get("issues", []) if issue.get("level") == "BLOCK"]
        if errors:
            flash("Completa i campi obbligatori evidenziati prima di generare l'atto.", "warning")
            ctx = _contesto_compilatore(
                model_code,
                payload=payload,
                selected_cliente=selected_cliente,
                selected_fascicolo=selected_fascicolo,
                errors=errors,
                assistant_analysis=assistant_analysis,
                correction_context=correction_context,
            )
            return render_template(
                "template_atti/compilatore.html",
                **ctx,
            )
        if blockers:
            first = blockers[0]
            flash(
                f"Bozza bloccata: {first.get('title')}. {first.get('suggested_action', '')}".strip(),
                "warning",
            )
            ctx = _contesto_compilatore(
                model_code,
                payload=payload,
                selected_cliente=selected_cliente,
                selected_fascicolo=selected_fascicolo,
                assistant_analysis=assistant_analysis,
                correction_context=correction_context,
            )
            return render_template("template_atti/compilatore.html", **ctx)

        testo_generato = render_compiled_act(model_code, payload)
        ctx = _contesto_compilatore(
            model_code,
            payload=payload,
            selected_cliente=selected_cliente,
            selected_fascicolo=selected_fascicolo,
            assistant_analysis=assistant_analysis,
            correction_context=correction_context,
        )
        return render_template(
            "template_atti/anteprima_compilatore.html",
            model=model,
            payload=payload,
            form_values={key: _valore_form(value) for key, value in payload.items()},
            testo_generato=testo_generato,
            editor_html=_to_editor_html(testo_generato),
            selected_cliente=selected_cliente,
            selected_fascicolo=selected_fascicolo,
            guidance=ctx["guidance"],
            suggested_attachments=ctx["suggested_attachments"],
            suggested_clauses=ctx["suggested_clauses"],
            sections=ctx["sections"],
            renderer_name=ctx["renderer_name"],
            assistant_analysis=assistant_analysis,
            correction_context=correction_context,
        )

    return render_template(
        "template_atti/compilatore.html",
        **_contesto_compilatore(
            model_code,
            payload=payload,
            selected_cliente=selected_cliente,
            selected_fascicolo=selected_fascicolo,
            assistant_analysis=assistant_analysis,
            correction_context=correction_context,
        ),
    )


@template_atti.route("/api/editor-layout", methods=["POST"])
@_richiedi_login
def salva_editor_layout():
    try:
        from pct.template_atti import normalizza_editor_layout

        payload = request.get_json(silent=True) or {}
        layout = payload.get("layout", payload)
        salvato = _get_gp().salva(normalizza_editor_layout(layout))
        return jsonify({"ok": True, "layout": salvato}), 200
    except Exception as e:
        current_app.logger.exception("Errore salvataggio layout editor template atti: %s", e)
        return jsonify({"ok": False, "errore": str(e)}), 200


@template_atti.route("/api/editor-layout/reset", methods=["POST"])
@_richiedi_login
def reset_editor_layout():
    try:
        ripristinato = _get_gp().reset()
        return jsonify({"ok": True, "layout": ripristinato}), 200
    except Exception as e:
        current_app.logger.exception("Errore reset layout editor template atti: %s", e)
        return jsonify({"ok": False, "errore": str(e)}), 200


@template_atti.route("/api/scanner/windows-scan", methods=["POST"])
@_richiedi_login
def scanner_windows_scan():
    try:
        from pct.template_atti import acquisisci_da_scanner_windows

        scan = acquisisci_da_scanner_windows()
        return jsonify({"ok": True, "scan": scan}), 200
    except Exception as e:
        current_app.logger.exception("Errore scanner desktop template atti: %s", e)
        return jsonify({"ok": False, "errore": str(e)}), 200


# ================================================================ IMPORTA DOCUMENTO

@template_atti.route("/api/importa-documento", methods=["POST"])
@_richiedi_login
def api_importa_documento():
    """Converte un documento DOCX o PDF in testo/HTML per l'editor template."""
    try:
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"errore": "Nessun file ricevuto."}), 200

        filename = file.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext == "docx":
            import mammoth
            result = mammoth.convert_to_html(file)
            html = result.value or ""
            # Stripping di tag vuoti lasciati da mammoth
            html = re.sub(r"<p>\s*</p>", "", html)
            return jsonify({"ok": True, "tipo": "html", "contenuto": html})

        if ext == "pdf":
            import io as _io
            import pdfplumber
            data = file.read()
            testo_pagine = []
            with pdfplumber.open(_io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    testo = page.extract_text() or ""
                    if testo.strip():
                        testo_pagine.append(testo.strip())
            testo = "\n\n".join(testo_pagine)
            return jsonify({"ok": True, "tipo": "testo", "contenuto": testo})

        return jsonify({"errore": f"Formato '.{ext}' non supportato via server. Usa DOCX o PDF (TXT e HTML vengono gestiti direttamente nel browser)."}), 200

    except Exception as e:
        current_app.logger.exception("Errore api_importa_documento: %s", e)
        return jsonify({"errore": str(e)}), 200


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
    layout = _parse_editor_layout(request.form.get("testo_generato__editor_layout"))
    buf = _genera_pdf(titolo, testo, current_app.config, layout=layout)
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
    layout = _parse_editor_layout(request.form.get("testo_generato__editor_layout"))
    buf = _genera_pdf(titolo, testo, current_app.config, layout=layout)
    nome_file = titolo.lower().replace(" ", "_").replace("/", "-") + ".pdf"
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=False, download_name=nome_file)


# ================================================================ API assistente redazionale

@template_atti.route("/api/assistente-redazionale/<model_code>", methods=["POST"])
@_richiedi_login
def api_assistente_redazionale(model_code: str):
    try:
        from pct.compilatore_atti import get_modello

        if not get_modello(model_code):
            return jsonify({"ok": False, "errore": "Modello non trovato."}), 200
        resolved = _resolve_compiler_context(model_code)
        analysis = _build_assistant_analysis(
            model_code,
            payload=resolved["payload"],
            selected_cliente=resolved["selected_cliente"],
            selected_fascicolo=resolved["selected_fascicolo"],
        )
        return jsonify({"ok": True, "analysis": analysis}), 200
    except Exception as e:
        current_app.logger.exception("Errore api_assistente_redazionale: %s", e)
        return jsonify({"ok": False, "errore": str(e)}), 200


# ================================================================ helpers

def _variabili_safe(v: dict) -> dict:
    """Serializza le variabili per il form nascosto (solo stringhe)."""
    safe = {}
    for k, val in v.items():
        if isinstance(val, str):
            safe[k] = val
    return safe


def _parse_editor_layout(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        from pct.template_atti import normalizza_editor_layout

        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return normalizza_editor_layout(parsed)
    except Exception:
        return None


def _to_editor_html(content: str) -> str:
    text = (content or "").strip()
    if not text:
        return "<p></p>"
    if _looks_like_html(text):
        return text
    return _plain_text_to_editor_html(text)


def _looks_like_html(content: str) -> bool:
    lowered = (content or "").strip().lower()
    return any(
        tag in lowered
        for tag in ("<p", "<div", "<h1", "<h2", "<h3", "<ul", "<ol", "<li", "<table", "<blockquote", "<br", "<hr", "<img", "<figure")
    )


def _plain_text_to_editor_html(content: str) -> str:
    normalized = (content or "").replace("\r", "").strip()
    if not normalized:
        return "<p></p>"

    blocks = [
        [line.strip() for line in block.split("\n") if line.strip()]
        for block in re.split(r"\n\s*\n", normalized)
    ]
    blocks = [lines for lines in blocks if lines]
    html_blocks: list[str] = []

    for index, lines in enumerate(blocks):
        if len(lines) == 1:
            line = lines[0]
            if index == 0 and _is_upper_heading(line):
                html_blocks.append(f'<div class="legal-doc-kicker">{escape(line)}</div>')
                continue
            if (index == 0 or index == 1) and len(line) <= 90 and not line.endswith(":"):
                html_blocks.append(f"<h1>{escape(line)}</h1>")
                continue
            if _is_upper_heading(line):
                html_blocks.append(f"<h2>{escape(line)}</h2>")
                continue
            if line.endswith(":") and len(line) <= 60:
                html_blocks.append(f'<p class="legal-doc-label"><strong>{escape(line)}</strong></p>')
                continue

        if all(re.match(r"^\d+\.\s+", line) for line in lines):
            items = [re.sub(r"^\d+\.\s+", "", line) for line in lines]
            html_blocks.append("<ol>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ol>")
            continue

        if all(line.startswith("- ") for line in lines):
            items = [line[2:].strip() for line in lines]
            html_blocks.append("<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>")
            continue

        css_class = ' class="legal-doc-party"' if len(lines) > 1 else ""
        html_blocks.append(f"<p{css_class}>" + "<br>".join(escape(line) for line in lines) + "</p>")

    return "\n".join(html_blocks) or "<p></p>"


def _is_upper_heading(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped or len(stripped) > 90:
        return False
    letters = [char for char in stripped if char.isalpha()]
    if not letters:
        return False
    return stripped == stripped.upper()


def _fallback_pdf_from_text(titolo: str, testo: str, config: dict) -> io.BytesIO:
    safe_text = testo or ""
    safe_text = re.sub(r"(?i)<br\s*/?>", "\n", safe_text)
    safe_text = re.sub(r"(?i)</(p|div|h1|h2|h3|h4|blockquote)>", "\n", safe_text)
    safe_text = re.sub(r"(?i)<li[^>]*>", "- ", safe_text)
    safe_text = re.sub(r"(?i)</li>", "\n", safe_text)
    safe_text = re.sub(r"<[^>]+>", "", safe_text)
    safe_text = re.sub(r"\n{3,}", "\n\n", safe_text).strip()
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
        for riga in safe_text.split("\n"):
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
        buf = io.BytesIO(safe_text.encode("utf-8"))
        buf.seek(0)
        return buf


def _genera_pdf(titolo: str, testo: str, config: dict, layout: dict | None = None) -> io.BytesIO:
    html = _to_editor_html(testo)
    try:
        from pct.editor import html_to_pdf

        pdf_bytes = html_to_pdf(html, titolo, layout=layout)
        buf = io.BytesIO(pdf_bytes)
        buf.seek(0)
        return buf
    except Exception as exc:
        current_app.logger.exception("Errore generazione PDF HTML template atti: %s", exc)
        return _fallback_pdf_from_text(titolo, testo, config)
