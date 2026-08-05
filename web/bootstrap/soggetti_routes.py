"""Soggetti and parti fascicolo routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from types import SimpleNamespace

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for

from pct.soggetti import RuoloSoggetto, TipoSoggetto, soggetto_coincide_con_cliente
from web.blueprints.react_shell import render_react_shell_response
from web.services.territorio_forms import address_fields_from_form


def _richiede_vista_legacy() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def _richiede_json() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("Accept") or "")
    )


def _soggetto_form_probe(form) -> SimpleNamespace:
    return SimpleNamespace(
        id_cliente=str(form.get("id_cliente", "") or "").strip(),
        nome=str(form.get("nome", "") or "").strip(),
        cognome=str(form.get("cognome", "") or "").strip(),
        ragione_sociale=str(form.get("ragione_sociale", "") or "").strip(),
        codice_fiscale=str(form.get("codice_fiscale", "") or "").strip(),
        partita_iva=str(form.get("partita_iva", "") or "").strip(),
    )


def _reject_soggetto_cliente_if_needed(clienti: list[object]):
    probe = _soggetto_form_probe(request.form)
    if probe.id_cliente or soggetto_coincide_con_cliente(probe, clienti):
        message = (
            "Questo nominativo risulta già nell'anagrafica clienti dello studio. "
            "I clienti restano in Clienti e anagrafiche; Soggetti e Parti contiene solo controparti, difensori, enti e altri soggetti processuali."
        )
        if _richiede_json():
            return jsonify({"ok": False, "message": message, "code": "subject_is_existing_client"}), 409
        flash(message, "warning")
        return redirect(url_for("nuovo_soggetto"))
    return None


def _safe_internal_next_url(value: object) -> str:
    raw = str(value or "").strip()
    if raw.startswith("/") and not raw.startswith("//"):
        return raw
    return ""


def _ruolo_soggetto_from_form(form) -> RuoloSoggetto:
    raw = str(form.get("ruolo_collegamento") or form.get("ruolo") or form.get("qualifica") or "ALTRO").strip()
    normalized = raw.replace("-", "_").replace(" ", "_").upper()
    try:
        return RuoloSoggetto(normalized)
    except ValueError:
        return RuoloSoggetto.ALTRO


def register_soggetti_routes(
    app: Flask,
    *,
    get_soggetti: Callable[[], object],
    get_clienti: Callable[[], object],
    get_fascicoli: Callable[[], object],
    audit: Callable[..., None],
) -> None:
    """Register soggetti CRUD routes and fascicolo party management routes."""

    @app.route("/soggetti")
    def lista_soggetti():
        if not _richiede_vista_legacy():
            return render_react_shell_response("soggetti")

        query = request.args.get("q", "").strip()
        tipo_filtro = request.args.get("tipo", "").strip()
        soggetti = get_soggetti().cerca(q=query, tipo=tipo_filtro)
        return render_template(
            "soggetti/lista.html",
            soggetti=soggetti,
            q=query,
            tipo_f=tipo_filtro,
            oggi=date.today(),
        )

    @app.route("/soggetti/nuovo", methods=["GET", "POST"])
    def nuovo_soggetto():
        soggetti = get_soggetti()
        clienti = get_clienti().tutti()
        if request.method == "GET" and not _richiede_vista_legacy():
            return render_react_shell_response("soggetti/nuovo")

        if request.method == "POST":
            tipo_val = request.form.get("tipo", "PERSONA_FISICA")
            try:
                tipo = TipoSoggetto(tipo_val)
            except ValueError:
                tipo = TipoSoggetto.PERSONA_FISICA
            rejected = _reject_soggetto_cliente_if_needed(clienti)
            if rejected is not None:
                return rejected
            from pct.clienti import Indirizzo, Recapiti

            indirizzo = Indirizzo(**address_fields_from_form(request.form))
            recapiti = Recapiti(
                telefono=request.form.get("telefono", ""),
                cellulare=request.form.get("cellulare", ""),
                email=request.form.get("email", ""),
                pec=request.form.get("pec", ""),
                fax=request.form.get("fax", ""),
                sito_web=request.form.get("sito_web", ""),
            )
            tag = [item.strip() for item in request.form.get("tag", "").split(",") if item.strip()]
            soggetto = soggetti.crea(
                tipo=tipo,
                nome=request.form.get("nome", ""),
                cognome=request.form.get("cognome", ""),
                codice_fiscale=request.form.get("codice_fiscale", ""),
                data_nascita=request.form.get("data_nascita", ""),
                luogo_nascita=request.form.get("luogo_nascita", ""),
                provincia_nascita=request.form.get("provincia_nascita", ""),
                sesso=request.form.get("sesso", ""),
                ragione_sociale=request.form.get("ragione_sociale", ""),
                partita_iva=request.form.get("partita_iva", ""),
                forma_giuridica=request.form.get("forma_giuridica", ""),
                rappresentante_legale=request.form.get("rappresentante_legale", ""),
                qualifica=request.form.get("qualifica", ""),
                ordine=request.form.get("ordine", ""),
                numero_iscrizione=request.form.get("numero_iscrizione", ""),
                indirizzo=indirizzo,
                recapiti=recapiti,
                id_cliente="",
                note=request.form.get("note", ""),
                tag=tag,
            )
            audit("soggetti.crea", "soggetto", soggetto.id, dettagli=soggetto.nome_completo)
            message = f"Soggetto '{soggetto.nome_completo}' creato."
            target = url_for("dettaglio_soggetto", id_soggetto=soggetto.id)
            id_fascicolo = str(request.form.get("id_fascicolo", "") or "").strip()
            if id_fascicolo:
                fascicolo = get_fascicoli().get(id_fascicolo)
                if fascicolo:
                    ruolo_collegamento = _ruolo_soggetto_from_form(request.form)
                    soggetti.aggiungi_parte(
                        id_fascicolo,
                        soggetto.id,
                        ruolo_collegamento,
                        note=request.form.get("note_collegamento", "") or "Creato dal form soggetto collegato al fascicolo.",
                    )
                    audit(
                        "soggetti.aggiungi_parte",
                        "fascicolo",
                        id_fascicolo,
                        dettagli=f"{soggetto.nome_completo} -> {ruolo_collegamento.label}",
                    )
                    message = f"Soggetto '{soggetto.nome_completo}' creato e collegato come {ruolo_collegamento.label}."
                    target = _safe_internal_next_url(request.form.get("next_url")) or url_for("dettaglio_fascicolo", id_fasc=id_fascicolo)
            flash(message, "success")
            if _richiede_json():
                return jsonify({"ok": True, "id": soggetto.id, "message": message, "redirect": target})
            return redirect(target)

        prefill = {
            key: request.args.get(key, "")
            for key in (
                "tipo",
                "nome",
                "cognome",
                "ragione_sociale",
                "codice_fiscale",
                "partita_iva",
                "email",
                "cellulare",
                "telefono",
                "pec",
                "id_cliente",
            )
        }
        return render_template(
            "soggetti/form.html",
            soggetto=None,
            clienti=clienti,
            TipoSoggetto=TipoSoggetto,
            oggi=date.today(),
            prefill=prefill,
        )

    @app.route("/soggetti/<id_soggetto>")
    def dettaglio_soggetto(id_soggetto):
        soggetto = get_soggetti().get(id_soggetto)
        if not soggetto:
            abort(404)
        if not _richiede_vista_legacy():
            return render_react_shell_response(f"soggetti/{id_soggetto}")
        ids_fascicoli = get_soggetti().fascicoli_con_soggetto(id_soggetto)
        fascicoli_collegati = [fascicolo for fascicolo in (get_fascicoli().get(item) for item in ids_fascicoli) if fascicolo]
        cliente_collegato = get_clienti().get(soggetto.id_cliente) if soggetto.id_cliente else None
        return render_template(
            "soggetti/dettaglio.html",
            soggetto=soggetto,
            fascicoli_collegati=fascicoli_collegati,
            cliente_collegato=cliente_collegato,
            oggi=date.today(),
        )

    @app.route("/soggetti/<id_soggetto>/modifica", methods=["GET", "POST"])
    def modifica_soggetto(id_soggetto):
        soggetti = get_soggetti()
        soggetto = soggetti.get(id_soggetto)
        if not soggetto:
            if _richiede_json():
                return jsonify({"ok": False, "message": "Soggetto non trovato."}), 404
            abort(404)
        clienti = get_clienti().tutti()
        if request.method == "GET" and not _richiede_vista_legacy():
            return render_react_shell_response(f"soggetti/{id_soggetto}/modifica")
        if request.method == "POST":
            tipo_val = request.form.get("tipo", soggetto.tipo.value)
            try:
                tipo = TipoSoggetto(tipo_val)
            except ValueError:
                tipo = soggetto.tipo
            rejected = _reject_soggetto_cliente_if_needed(clienti)
            if rejected is not None:
                return rejected
            from pct.clienti import Indirizzo, Recapiti

            indirizzo = Indirizzo(**address_fields_from_form(request.form))
            recapiti = Recapiti(
                telefono=request.form.get("telefono", ""),
                cellulare=request.form.get("cellulare", ""),
                email=request.form.get("email", ""),
                pec=request.form.get("pec", ""),
                fax=request.form.get("fax", ""),
                sito_web=request.form.get("sito_web", ""),
            )
            tag = [item.strip() for item in request.form.get("tag", "").split(",") if item.strip()]
            soggetti.aggiorna(
                id_soggetto,
                tipo=tipo,
                nome=request.form.get("nome", ""),
                cognome=request.form.get("cognome", ""),
                codice_fiscale=request.form.get("codice_fiscale", ""),
                data_nascita=request.form.get("data_nascita", ""),
                luogo_nascita=request.form.get("luogo_nascita", ""),
                provincia_nascita=request.form.get("provincia_nascita", ""),
                sesso=request.form.get("sesso", ""),
                ragione_sociale=request.form.get("ragione_sociale", ""),
                partita_iva=request.form.get("partita_iva", ""),
                forma_giuridica=request.form.get("forma_giuridica", ""),
                rappresentante_legale=request.form.get("rappresentante_legale", ""),
                qualifica=request.form.get("qualifica", ""),
                ordine=request.form.get("ordine", ""),
                numero_iscrizione=request.form.get("numero_iscrizione", ""),
                indirizzo=indirizzo,
                recapiti=recapiti,
                id_cliente="",
                note=request.form.get("note", ""),
                tag=tag,
            )
            audit("soggetti.modifica", "soggetto", id_soggetto, dettagli=soggetto.nome_completo)
            flash("Soggetto aggiornato.", "success")
            target = url_for("dettaglio_soggetto", id_soggetto=id_soggetto)
            if _richiede_json():
                return jsonify({"ok": True, "id": id_soggetto, "message": "Soggetto aggiornato.", "redirect": target})
            return redirect(url_for("dettaglio_soggetto", id_soggetto=id_soggetto))
        return render_template(
            "soggetti/form.html",
            soggetto=soggetto,
            clienti=clienti,
            TipoSoggetto=TipoSoggetto,
            oggi=date.today(),
        )

    @app.route("/soggetti/<id_soggetto>/elimina", methods=["POST"])
    def elimina_soggetto(id_soggetto):
        soggetti = get_soggetti()
        soggetto = soggetti.get(id_soggetto)
        if soggetto:
            nome = soggetto.nome_completo
            soggetti.elimina(id_soggetto)
            audit("soggetti.elimina", "soggetto", id_soggetto, dettagli=nome)
            flash(f"Soggetto '{nome}' eliminato.", "success")
        return redirect(url_for("lista_soggetti"))

    @app.route("/api/soggetti")
    def api_soggetti():
        """Autocomplete JSON dei soggetti."""
        try:
            query = request.args.get("q", "").strip()
            risultati = get_soggetti().cerca(q=query)[:20]
            return jsonify(
                [
                    {
                        "id": soggetto.id,
                        "nome": soggetto.nome_completo,
                        "tipo": soggetto.tipo.value,
                        "sigla": soggetto.sigla_tipo,
                        "qualifica": soggetto.qualifica,
                        "identificativo": soggetto.identificativo,
                    }
                    for soggetto in risultati
                ]
            )
        except Exception as exc:
            app.logger.exception("Errore api_soggetti: %s", exc)
            return jsonify([])

    @app.route("/fascicoli/<id_fasc>/parti/aggiungi", methods=["POST"])
    def aggiungi_parte_fascicolo(id_fasc):
        fascicolo = get_fascicoli().get(id_fasc)
        if not fascicolo:
            abort(404)
        id_soggetto = request.form.get("id_soggetto", "")
        ruolo_val = request.form.get("ruolo", "ALTRO")
        note = request.form.get("note", "")
        next_url = _safe_internal_next_url(
            request.form.get("next_url")
            or request.form.get("next")
            or request.args.get("next_url")
            or request.args.get("next")
        )
        redirect_to = next_url or url_for("dettaglio_fascicolo", id_fasc=id_fasc)
        try:
            ruolo = RuoloSoggetto(ruolo_val)
        except ValueError:
            ruolo = RuoloSoggetto.ALTRO
        soggetto = get_soggetti().get(id_soggetto)
        if not soggetto:
            if _richiede_json():
                return jsonify({"ok": False, "message": "Soggetto non trovato."}), 404
            flash("Soggetto non trovato.", "danger")
            return redirect(redirect_to)
        get_soggetti().aggiungi_parte(id_fasc, id_soggetto, ruolo, note)
        audit("soggetti.aggiungi_parte", "fascicolo", id_fasc, dettagli=f"{soggetto.nome_completo} -> {ruolo.label}")
        message = f"'{soggetto.nome_completo}' aggiunto come {ruolo.label}."
        if _richiede_json():
            return jsonify({"ok": True, "message": message, "redirect": redirect_to, "id": id_soggetto})
        flash(message, "success")
        return redirect(redirect_to)

    @app.route("/fascicoli/<id_fasc>/parti/<id_parte>/rimuovi", methods=["POST"])
    def rimuovi_parte_fascicolo(id_fasc, id_parte):
        get_soggetti().rimuovi_parte(id_fasc, id_parte)
        audit("soggetti.rimuovi_parte", "fascicolo", id_fasc, dettagli=id_parte)
        flash("Parte rimossa dal fascicolo.", "success")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
