"""Checklist and guided fascicolo wizard routes extracted from web.app."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

from pct.fascicoli import TipoDocumento


def register_checklist_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_config_studio: Callable[[], object],
    encrypt_doc: Callable[[bytes], bytes],
    audit: Callable[..., None],
) -> None:
    """Register checklist catalog and fascicolo wizard routes."""

    def _wizard_step_stato(fascicolo, documento_richiesto, id_template):
        nota_tag = f"[wizard:{id_template}:step{documento_richiesto.numero}]"
        nome_prefix = documento_richiesto.nome_file.lower()
        for documento in fascicolo.documenti:
            if nota_tag in (documento.note or ""):
                return "done"
            if documento.nome.lower().startswith(nome_prefix):
                return "done"
        return "pending"

    def _trova_documento_wizard(fascicolo, documento_richiesto, id_template):
        nota_tag = f"[wizard:{id_template}:step{documento_richiesto.numero}]"
        nome_prefix = documento_richiesto.nome_file.lower()
        for documento in fascicolo.documenti:
            if nota_tag in (documento.note or ""):
                return documento
            if documento.nome.lower().startswith(nome_prefix):
                return documento
        return None

    @app.route("/checklist")
    def checklist_atti():
        from pct.checklist_atti import CAT_COL, CAT_ICON, CATEGORIE, TUTTI_I_TEMPLATE

        per_categoria = {}
        for template in TUTTI_I_TEMPLATE:
            per_categoria.setdefault(template.categoria, []).append(template)
        return render_template(
            "checklist/lista.html",
            per_cat=per_categoria,
            categorie=CATEGORIE,
            cat_icon=CAT_ICON,
            cat_col=CAT_COL,
            oggi=date.today(),
        )

    @app.route("/checklist/<id_template>")
    def checklist_dettaglio(id_template):
        from pct.checklist_atti import CAT_COL, CAT_ICON, get_template, nome_cartella_compilato

        template = get_template(id_template)
        if not template:
            flash("Template non trovato.", "warning")
            return redirect(url_for("checklist_atti"))
        id_fasc = request.args.get("id_fasc", "")
        fascicolo_ctx = None
        if id_fasc:
            fascicolo = get_fascicoli().get(id_fasc)
            if fascicolo:
                fascicolo_ctx = fascicolo
        parte = request.args.get("parte") or (fascicolo_ctx.controparte if fascicolo_ctx else "")
        rg = request.args.get("rg") or (getattr(fascicolo_ctx, "numero_rg", "") if fascicolo_ctx else "")
        data = request.args.get("data", date.today().isoformat())
        cartella = nome_cartella_compilato(template, parte=parte, rg=rg, data=data)
        return render_template(
            "checklist/dettaglio.html",
            tmpl=template,
            cartella=cartella,
            parte=parte,
            rg=rg,
            data=data,
            id_fasc=id_fasc,
            fascicolo=fascicolo_ctx,
            cat_icon=CAT_ICON,
            cat_col=CAT_COL,
            oggi=date.today(),
        )

    @app.route("/fascicoli/<id_fasc>/wizard/<id_template>")
    def wizard_atto_avvia(id_fasc, id_template):
        """Avvia o riprende il wizard dal primo step obbligatorio incompleto."""
        from pct.checklist_atti import get_template

        fascicolo = get_fascicoli().get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))
        template = get_template(id_template)
        if not template:
            flash("Template non trovato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        for documento in template.documenti:
            if _wizard_step_stato(fascicolo, documento, id_template) == "pending" and documento.obbligatorio:
                return redirect(
                    url_for(
                        "wizard_atto_step",
                        id_fasc=id_fasc,
                        id_template=id_template,
                        n=documento.numero,
                    )
                )
        return redirect(url_for("wizard_atto_completa", id_fasc=id_fasc, id_template=id_template))

    @app.route("/fascicoli/<id_fasc>/wizard/<id_template>/step/<int:n>", methods=["GET", "POST"])
    def wizard_atto_step(id_fasc, id_template, n):
        from pct.checklist_atti import get_template, nome_cartella_compilato

        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))
        template = get_template(id_template)
        if not template:
            flash("Template non trovato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        doc_step = next((doc for doc in template.documenti if doc.numero == n), None)
        if not doc_step:
            flash("Step non trovato.", "danger")
            return redirect(url_for("wizard_atto_avvia", id_fasc=id_fasc, id_template=id_template))

        if request.method == "POST":
            azione = request.form.get("azione", "carica")
            utente = g.utente_corrente

            if azione == "salta" and not doc_step.obbligatorio:
                skip_key = f"wiz_skip_{id_fasc}_{id_template}"
                skipped = session.get(skip_key, [])
                if n not in skipped:
                    skipped.append(n)
                session[skip_key] = skipped
                flash(f"'{doc_step.descrizione}' saltato.", "info")

            elif azione == "carica":
                if "file" not in request.files or not request.files["file"].filename:
                    flash("Seleziona un file da caricare.", "warning")
                    return redirect(url_for("wizard_atto_step", id_fasc=id_fasc, id_template=id_template, n=n))
                file = request.files["file"]
                estensione = Path(file.filename).suffix or ".pdf"
                nome_wizard = f"{doc_step.nome_file}{estensione}"
                try:
                    contenuto = encrypt_doc(file.read())
                    nota = f"[wizard:{id_template}:step{n}]"
                    nota_extra = request.form.get("note", "").strip()
                    if nota_extra:
                        nota = f"{nota} {nota_extra}"
                    gestore_fascicoli.aggiungi_documento(
                        id_fasc,
                        nome_file=nome_wizard,
                        tipo=TipoDocumento(request.form.get("tipo_doc", "ALTRO")),
                        contenuto=contenuto,
                        note=nota,
                        data_documento=request.form.get("data_documento", ""),
                        firmato=request.form.get("firmato") == "1",
                        caricato_da=utente.username if utente else "",
                    )
                    flash(f"'{doc_step.descrizione}' caricato come {nome_wizard}.", "success")
                    audit(
                        "fascicoli.wizard.carica",
                        "fascicolo",
                        id_fasc,
                        dettagli=f"template:{id_template} step:{n} -> {nome_wizard}",
                    )
                except (ValueError, KeyError) as exc:
                    flash(str(exc), "danger")
                    return redirect(url_for("wizard_atto_step", id_fasc=id_fasc, id_template=id_template, n=n))

            prossimo = n + 1
            if prossimo <= len(template.documenti):
                return redirect(url_for("wizard_atto_step", id_fasc=id_fasc, id_template=id_template, n=prossimo))
            return redirect(url_for("wizard_atto_completa", id_fasc=id_fasc, id_template=id_template))

        skip_key = f"wiz_skip_{id_fasc}_{id_template}"
        skipped = session.get(skip_key, [])
        steps_stato = []
        for documento in template.documenti:
            stato = _wizard_step_stato(fascicolo, documento, id_template)
            if stato == "pending" and not documento.obbligatorio and documento.numero in skipped:
                stato = "saltato"
            steps_stato.append(
                {
                    "doc": documento,
                    "stato": stato,
                    "documento": _trova_documento_wizard(fascicolo, documento, id_template),
                }
            )
        return render_template(
            "fascicoli/wizard_atto.html",
            fascicolo=fascicolo,
            tmpl=template,
            step_corrente=doc_step,
            step_n=n,
            step_totale=len(template.documenti),
            steps_stato=steps_stato,
            doc_esistente=_trova_documento_wizard(fascicolo, doc_step, id_template),
            nome_cartella=nome_cartella_compilato(template, fascicolo.controparte, fascicolo.numero_rg),
            oggi=date.today(),
            tipo_documento_choices=[(tipo.value, tipo.value.replace("_", " ").title()) for tipo in TipoDocumento],
        )

    @app.route("/fascicoli/<id_fasc>/wizard/<id_template>/completa")
    def wizard_atto_completa(id_fasc, id_template):
        from pct.checklist_atti import CANALE_COL, CANALE_ICON, CANALE_LABEL, get_template, nome_cartella_compilato

        fascicolo = get_fascicoli().get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))
        template = get_template(id_template)
        if not template:
            flash("Template non trovato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        skip_key = f"wiz_skip_{id_fasc}_{id_template}"
        skipped = session.get(skip_key, [])
        steps_stato = []
        tutti_obbligatori = True
        for documento in template.documenti:
            stato = _wizard_step_stato(fascicolo, documento, id_template)
            if stato == "pending" and not documento.obbligatorio and documento.numero in skipped:
                stato = "saltato"
            if documento.obbligatorio and stato == "pending":
                tutti_obbligatori = False
            steps_stato.append(
                {
                    "doc": documento,
                    "stato": stato,
                    "documento": _trova_documento_wizard(fascicolo, documento, id_template),
                }
            )

        pec_tribunale = ""
        if fascicolo.tribunale:
            try:
                from pct.uffici_giudiziari import get_gestore as get_uffici

                cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                ufficio = next(
                    (
                        row
                        for row in get_uffici(cache_path).carica()
                        if str(row.get("nome", "")).lower() == fascicolo.tribunale.lower()
                    ),
                    None,
                )
                pec_tribunale = str((ufficio or {}).get("pec") or "")
            except Exception:
                pass

        pec_configurata = False
        firma_backend = "nessuno"
        canale_reale_configurato = False
        try:
            config = get_config_studio().config
            pec_configurata = bool(config and config.pec and config.pec.indirizzo and config.pec.password)
            firma_backend = getattr(getattr(config, "firma", None), "backend_firma_effettivo_safe", "nessuno") or "nessuno"
            canale_reale_configurato = firma_backend in {"p12", "pem"} if template.canale == "PTT_TRIBUTARIO" else pec_configurata
        except Exception:
            pass

        return render_template(
            "fascicoli/wizard_completa.html",
            fascicolo=fascicolo,
            tmpl=template,
            steps_stato=steps_stato,
            tutti_obbligatori=tutti_obbligatori,
            nome_cartella=nome_cartella_compilato(template, fascicolo.controparte, fascicolo.numero_rg),
            pec_tribunale=pec_tribunale,
            pec_configurata=pec_configurata,
            firma_backend=firma_backend,
            canale_reale_configurato=canale_reale_configurato,
            canale_label=CANALE_LABEL,
            canale_icon=CANALE_ICON,
            canale_col=CANALE_COL,
            oggi=date.today(),
        )

    @app.route("/fascicoli/<id_fasc>/wizard/<id_template>/genera-indice", methods=["POST"])
    def wizard_genera_indice(id_fasc, id_template):
        from datetime import datetime as dt_now

        from pct.checklist_atti import get_template, nome_cartella_compilato

        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))
        template = get_template(id_template)
        if not template:
            flash("Template non trovato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        utente = g.utente_corrente
        skip_key = f"wiz_skip_{id_fasc}_{id_template}"
        skipped = session.get(skip_key, [])
        nome_cartella = nome_cartella_compilato(template, fascicolo.controparte, fascicolo.numero_rg)

        righe = []
        for documento in template.documenti:
            doc_fascicolo = _trova_documento_wizard(fascicolo, documento, id_template)
            if doc_fascicolo:
                righe.append(
                    f"  {documento.numero:02d}. {doc_fascicolo.nome}\n"
                    f"      {documento.descrizione}"
                    f" | {doc_fascicolo.data_documento or 'data n.d.'}"
                    f" | sha256: {doc_fascicolo.hash_sha256[:16]}..."
                )
            elif not documento.obbligatorio and documento.numero in skipped:
                righe.append(
                    f"  {documento.numero:02d}. [non allegato] {documento.nome_file} "
                    f"({documento.descrizione} - facoltativo)"
                )
            else:
                righe.append(f"  {documento.numero:02d}. [MANCANTE] {documento.nome_file} ({documento.descrizione})")

        separatore = "=" * 64
        testo = "\n".join(
            [
                separatore,
                f"  INDICE DOCUMENTI - {template.nome.upper()}",
                separatore,
                f"  Fascicolo  : {fascicolo.titolo}",
                f"  RG         : {fascicolo.rg_completo or 'n.d.'}",
                f"  Cliente    : {fascicolo.nome_cliente}",
                f"  Controparte: {fascicolo.controparte}",
                f"  Tribunale  : {fascicolo.tribunale or 'n.d.'}",
                f"  Cartella   : {nome_cartella}",
                f"  Generato il: {dt_now.now().strftime('%d/%m/%Y %H:%M')}",
                separatore,
                "",
                *righe,
                "",
                separatore,
            ]
        )

        try:
            nome_indice = f"00_Indice_{template.id}.txt"
            gestore_fascicoli.aggiungi_documento(
                id_fasc,
                nome_file=nome_indice,
                tipo=TipoDocumento.ALTRO,
                contenuto=encrypt_doc(testo.encode("utf-8")),
                note=f"[wizard:{id_template}:indice] Indice generato automaticamente",
                caricato_da=utente.username if utente else "",
            )
            flash(f"Indice '{nome_indice}' generato e aggiunto al fascicolo.", "success")
            audit("fascicoli.wizard.indice", "fascicolo", id_fasc, dettagli=f"template:{id_template}")
        except Exception as exc:
            app.logger.exception("Errore wizard_genera_indice %s: %s", id_fasc, exc)
            flash(f"Errore generazione indice: {exc}", "danger")

        return redirect(url_for("wizard_atto_completa", id_fasc=id_fasc, id_template=id_template))
