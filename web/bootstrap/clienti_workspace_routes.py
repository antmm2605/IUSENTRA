"""Client workspace routes extracted from web.app."""

from __future__ import annotations

import io
import json
import tempfile
import zipfile as _zipfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for

from pct.fascicoli import StatoFascicolo
from pct.reports import faldone_pdf
from web.services.copertine_pdf import copertina_faldone_pdf, oggi_roma, risposta_pdf_copertina
from web.blueprints.react_shell import render_react_shell_response
from web.services.clienti_faldone_runtime import carica_note_faldone, salva_note_faldone


def _get_portale_mgr(app: Flask):
    from pct.portale import GestionePortale

    return GestionePortale(
        db_path=app.config["PORTALE_DB"],
        uploads_dir=app.config["PORTALE_UPLOADS"],
    )


def register_clienti_workspace_routes(
    app: Flask,
    *,
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_messaggi: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    get_timesheet: Callable[[], Any],
    get_preventivi: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_config_studio: Callable[[], Any],
    cliente_accessibile: Callable[..., bool],
    track_recente: Callable[..., None],
    audit: Callable[..., None],
) -> None:
    """Register workspace routes tied to the cliente dossier."""

    @app.route("/clienti/<id_cliente>/cartella")
    def cartella_cliente(id_cliente: str):
        gc = get_clienti()
        cliente = gc.get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        if not cliente_accessibile(id_cliente):
            flash("Non hai accesso a questa cartella cliente.", "danger")
            return redirect(url_for("lista_clienti"))
        track_recente(
            "cliente",
            id_cliente,
            cliente.nome_completo,
            url_for("cartella_cliente", id_cliente=id_cliente),
            "bi-folder2-open",
        )
        return render_react_shell_response(f"clienti/{id_cliente}/cartella")

    @app.route("/clienti/<id_cliente>/faldone")
    def faldone_cliente(id_cliente: str):
        cliente = get_clienti().get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        if not cliente_accessibile(id_cliente):
            flash("Non hai accesso a questa cartella cliente.", "danger")
            return redirect(url_for("lista_clienti"))
        audit("faldone.accesso", "cliente", id_cliente)
        # Faldone del cliente: pagina React (AnagraficaClientiPage); dati da /api/v1/ui.
        return render_react_shell_response(f"clienti/{id_cliente}/faldone")

    @app.route("/clienti/<id_cliente>/faldone/note", methods=["POST"])
    def faldone_salva_note(id_cliente: str):
        try:
            gc = get_clienti()
            if not gc.get(id_cliente):
                return jsonify({"ok": False, "errore": "Cliente non trovato"}), 404
            if not cliente_accessibile(id_cliente):
                return jsonify({"ok": False, "errore": "Non autorizzato"}), 403

            dati = request.get_json(silent=True) or {}
            sezione = dati.get("sezione", "generale")
            testo = dati.get("testo", "")
            note = carica_note_faldone(app.config["NOTE_FALDONE_DB"], id_cliente)
            note[sezione] = testo
            note["_modificato_il"] = date.today().isoformat()
            utente = g.utente_corrente
            note["_modificato_da"] = utente.username if utente else ""
            salva_note_faldone(app.config["NOTE_FALDONE_DB"], id_cliente, note)
            audit("faldone.note", "cliente", id_cliente, dettagli=f"sezione={sezione}")
            return jsonify({"ok": True})
        except Exception as exc:
            app.logger.exception("Errore faldone_salva_note %s: %s", id_cliente, exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200

    @app.route("/clienti/<id_cliente>/faldone/pdf")
    def faldone_pdf_export(id_cliente: str):
        try:
            gc = get_clienti()
            cliente = gc.get(id_cliente)
            if not cliente:
                flash("Cliente non trovato.", "warning")
                return redirect(url_for("lista_clienti"))
            if not cliente_accessibile(id_cliente):
                flash("Non hai accesso a questa cartella cliente.", "danger")
                return redirect(url_for("lista_clienti"))

            gf = get_fascicoli()
            gs = get_scadenziario()
            from pct.scadenziario import StatoTermine

            tutti = gf.cerca(id_cliente=id_cliente, archiviati=True)
            stati_chiusi = {StatoFascicolo.ARCHIVIATO, StatoFascicolo.DEFINITO}
            fascicoli_attivi = [fascicolo for fascicolo in tutti if fascicolo.stato not in stati_chiusi]

            ordine = [
                "CIVILE",
                "PENALE",
                "LAVORO",
                "FAMIGLIA",
                "AMMINISTRATIVO",
                "STRAGIUDIZIALE",
                "SUCCESSIONI",
                "CONSULENZA",
                "ALTRO",
            ]
            fascicoli_per_tipo_raw: dict[str, list[dict[str, Any]]] = {}
            for tipo in ordine:
                gruppo = [fascicolo.to_dict() for fascicolo in fascicoli_attivi if fascicolo.tipo.value == tipo]
                if gruppo:
                    fascicoli_per_tipo_raw[tipo] = gruppo
            for fascicolo in fascicoli_attivi:
                fascicoli_per_tipo_raw.setdefault(fascicolo.tipo.value, []).append(fascicolo.to_dict())

            scad_pdf: list[dict[str, Any]] = []
            for fascicolo in tutti:
                for scadenza in gs.tutte(id_fascicolo=fascicolo.id, stato=None):
                    if scadenza.stato == StatoTermine.APERTO and scadenza.data_scadenza:
                        scad_pdf.append(
                            {
                                "data_scadenza": scadenza.data_scadenza,
                                "fascicolo_numero": fascicolo.numero,
                                "titolo": scadenza.titolo,
                                "priorita": scadenza.priorita.value,
                                "perentorio": scadenza.perentorio,
                            }
                        )
            scad_pdf.sort(key=lambda item: item["data_scadenza"])

            timeline_pdf = sorted(
                [
                    {
                        "data": attivita.data,
                        "fascicolo_numero": fascicolo.numero,
                        "tipo": attivita.tipo.value,
                        "titolo": attivita.titolo,
                        "esito": attivita.esito.value,
                    }
                    for fascicolo in tutti
                    for attivita in fascicolo.attivita
                ],
                key=lambda item: item["data"] or "",
                reverse=True,
            )
            stats = {
                "n_doc": sum(fascicolo.documenti_count for fascicolo in tutti),
                "n_dep": sum(len(fascicolo.depositi_pct) for fascicolo in tutti),
                "n_att": sum(fascicolo.attivita_count for fascicolo in fascicoli_attivi),
                "n_scad": len(scad_pdf),
            }
            note = carica_note_faldone(app.config["NOTE_FALDONE_DB"], id_cliente)
            cfg_studio = get_config_studio()
            studio_nome = cfg_studio.nome or app.config.get("PCT_STUDIO_NOME", "IUSENTRA")

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name

            faldone_pdf(
                cliente_dict={
                    "nome_completo": cliente.nome_completo,
                    "codice_fiscale": cliente.codice_fiscale or "",
                    "partita_iva": getattr(cliente, "partita_iva", "") or "",
                },
                fascicoli_per_tipo=fascicoli_per_tipo_raw,
                scadenze_aperte=scad_pdf,
                timeline=timeline_pdf[:20],
                note=note,
                studio_nome=studio_nome,
                output_path=tmp_path,
                stats=stats,
            )
            audit("faldone.pdf", "cliente", id_cliente)
            nome_file = f"faldone_{cliente.nome_completo.replace(' ', '_').lower()}_{date.today().isoformat()}.pdf"
            data = io.BytesIO(Path(tmp_path).read_bytes())
            Path(tmp_path).unlink(missing_ok=True)
            return send_file(
                data,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=nome_file,
            )
        except Exception as exc:
            app.logger.exception("Errore faldone_pdf_export %s: %s", id_cliente, exc)
            flash(f"Errore generazione PDF: {exc}", "danger")
            return redirect(url_for("faldone_cliente", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/faldone/copertina")
    def copertina_faldone(id_cliente: str):
        try:
            gc = get_clienti()
            cliente = gc.get(id_cliente)
            if not cliente:
                flash("Cliente non trovato.", "warning")
                return redirect(url_for("lista_clienti"))
            if not cliente_accessibile(id_cliente):
                flash("Non hai accesso a questa cartella cliente.", "danger")
                return redirect(url_for("lista_clienti"))
            gf = get_fascicoli()
            tutti = gf.cerca(id_cliente=id_cliente, archiviati=True)
            stati_chiusi = {StatoFascicolo.ARCHIVIATO, StatoFascicolo.DEFINITO}
            fascicoli_attivi = [fascicolo for fascicolo in tutti if fascicolo.stato not in stati_chiusi]
            fascicoli_archiviati = [fascicolo for fascicolo in tutti if fascicolo.stato in stati_chiusi]
            cfg_studio = get_config_studio()
            # Copertina come PDF da stampare (prima pagina Jinja clienti/copertina_faldone.html).
            pdf = copertina_faldone_pdf(
                cliente,
                fascicoli_attivi,
                fascicoli_archiviati,
                studio_nome=cfg_studio.nome or app.config.get("PCT_STUDIO_NOME", "Studio Legale"),
                oggi=oggi_roma(),
            )
            return risposta_pdf_copertina(pdf, f"copertina_faldone_{cliente.id}.pdf")
        except Exception as exc:
            app.logger.exception("Errore copertina_faldone %s: %s", id_cliente, exc)
            flash(f"Errore copertina faldone: {exc}", "danger")
            return redirect(url_for("faldone_cliente", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/portale", methods=["GET"])
    def portale_config(id_cliente: str):
        cliente = get_clienti().get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        # Portale del cliente: sezione della cartella React (AnagraficaClientiPage).
        return render_react_shell_response(f"clienti/{id_cliente}/portale")

    @app.route("/clienti/<id_cliente>/portale/attiva", methods=["POST"])
    def portale_attiva(id_cliente: str):
        cliente = get_clienti().get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))

        from pct.portale import PermessiPortale

        gp = _get_portale_mgr(app)
        form = request.form
        permessi = PermessiPortale(
            vedi_anagrafica=bool(form.get("vedi_anagrafica")),
            modifica_anagrafica=bool(form.get("modifica_anagrafica")),
            vedi_fascicoli=bool(form.get("vedi_fascicoli")),
            vedi_economici=bool(form.get("vedi_economici")),
            accetta_preventivi=bool(form.get("accetta_preventivi")),
            firma_conferimenti=bool(form.get("firma_conferimenti")),
            vedi_attivita=bool(form.get("vedi_attivita")),
            vedi_appuntamenti=bool(form.get("vedi_appuntamenti")),
            vedi_scadenze=bool(form.get("vedi_scadenze")),
            carica_documenti=bool(form.get("carica_documenti")),
            firma_privacy=bool(form.get("firma_privacy")),
            max_upload_mb=int(form.get("max_upload_mb", 10)),
        )
        scade_il = form.get("scade_il", "").strip() or None
        if scade_il:
            scade_il = f"{scade_il}T23:59:59"
        utente = g.utente_corrente
        token_grezzo, _ = gp.crea(
            id_cliente=id_cliente,
            creato_da=utente.username if utente else "avvocato",
            permessi=permessi,
            scade_il=scade_il,
        )
        session["portale_token_grezzo"] = token_grezzo
        session.pop("portale_link_cache", None)
        flash("Portale attivato. Il link è pronto per essere inviato al cliente.", "success")
        return redirect(url_for("portale_config", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/portale/revoca", methods=["POST"])
    def portale_revoca(id_cliente: str):
        gp = _get_portale_mgr(app)
        portale_obj = gp.get_by_cliente(id_cliente)
        if portale_obj:
            gp.revoca(portale_obj.id)
            session.pop("portale_token_grezzo", None)
            session.pop("portale_link_cache", None)
            flash("Accesso al portale revocato.", "success")
        return redirect(url_for("portale_config", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/esporta")
    def esporta_cartella(id_cliente: str):
        if not cliente_accessibile(id_cliente):
            flash("Non hai accesso a questa cartella cliente.", "danger")
            return redirect(url_for("lista_clienti"))

        cliente = get_clienti().get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))

        gf = get_fascicoli()
        fascicoli_cliente = [fascicolo for fascicolo in gf.tutti() if fascicolo.id_cliente == id_cliente]

        buf = io.BytesIO()
        with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "anagrafica.json",
                json.dumps(
                    cliente.__dict__ if hasattr(cliente, "__dict__") else vars(cliente),
                    default=str,
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            for fascicolo in fascicoli_cliente:
                prefix = f"fascicoli/{fascicolo.numero or fascicolo.id}/"
                fascicolo_dict = fascicolo.to_dict() if hasattr(fascicolo, "to_dict") else vars(fascicolo)
                zf.writestr(
                    prefix + "fascicolo.json",
                    json.dumps(fascicolo_dict, default=str, ensure_ascii=False, indent=2),
                )
                for documento in fascicolo.documenti:
                    try:
                        percorso = gf.percorso_documento(fascicolo.id, documento.id)
                        if percorso.exists():
                            zf.write(percorso, prefix + "documenti/" + documento.nome)
                    except (KeyError, OSError):
                        continue

            indice = {
                "cliente": cliente.nome_completo,
                "fascicoli": [
                    {"id": fascicolo.id, "numero": fascicolo.numero, "titolo": fascicolo.titolo}
                    for fascicolo in fascicoli_cliente
                ],
                "esportato_il": date.today().isoformat(),
                "esportato_da": g.utente_corrente.username if g.utente_corrente else "—",
            }
            zf.writestr("indice.json", json.dumps(indice, ensure_ascii=False, indent=2))

        buf.seek(0)
        audit("condivisione.esporta", "cliente", id_cliente, dettagli=f"ZIP cartella {cliente.nome_completo}")
        nome_zip = f"cartella_{cliente.nome_completo.replace(' ', '_')}.zip"
        return send_file(buf, as_attachment=True, download_name=nome_zip, mimetype="application/zip")
