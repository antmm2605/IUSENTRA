"""Checklist and guided fascicolo wizard routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, flash, g, redirect, request, session, url_for

from pct.fascicoli import TipoDocumento
from web.blueprints.react_shell import render_react_shell_response


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
        # Checklist degli atti e percorso guidato: pagina React (ChecklistAttiPage); dati e passi da /api/v1/ui.
        return render_react_shell_response("checklist")

    @app.route("/checklist/<id_template>")
    def checklist_dettaglio(id_template):
        # Checklist degli atti e percorso guidato: pagina React (ChecklistAttiPage); dati e passi da /api/v1/ui.
        return render_react_shell_response(f"checklist/{id_template}")

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
        # Checklist degli atti e percorso guidato: pagina React (ChecklistAttiPage); dati e passi da /api/v1/ui.
        if request.method == "POST":
            return redirect(request.path)
        return render_react_shell_response(f"fascicoli/{id_fasc}/wizard/{id_template}/step/{n}")

    @app.route("/fascicoli/<id_fasc>/wizard/<id_template>/completa")
    def wizard_atto_completa(id_fasc, id_template):
        # Checklist degli atti e percorso guidato: pagina React (ChecklistAttiPage); dati e passi da /api/v1/ui.
        return render_react_shell_response(f"fascicoli/{id_fasc}/wizard/{id_template}/completa")

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
