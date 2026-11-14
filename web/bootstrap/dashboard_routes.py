"""Dashboard and agenda routes extracted from web.app."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from pct.agenda import Agenda, StatoAppuntamento, TipoAppuntamento
from pct.agenda_sql_writer import AgendaConflict
from web.blueprints.react_shell import render_react_shell_response
from web.services.request_mode import richiede_json
from web.bootstrap.agenda_api_routes import agenda_non_autorizzato as _agenda_non_autorizzato, register_agenda_api_routes



def register_dashboard_routes(
    app: Flask,
    *,
    get_agenda: Callable[[], Agenda],
    get_scadenziario: Callable[[], object],
    get_fascicoli: Callable[[], object],
    get_clienti: Callable[[], object],
    get_timesheet: Callable[[], object],
    get_preventivi: Callable[[], object],
    get_fatturazione: Callable[[], object],
    get_pagamenti: Callable[[], object],
    get_condivisioni: Callable[[], object],
    get_workspace_intelligente: Callable[[], object],
    get_calendar_sync: Callable[[], object],
    audit: Callable[..., None],
    sync_pubblica: Callable[[str, str, str], None],
    track_recente: Callable[[str, str, str, str, str], None],
) -> None:
    """Register dashboard, agenda, calendar import, and agenda API routes."""
    @app.errorhandler(AgendaConflict)
    def agenda_conflict(error):
        if richiede_json():
            return jsonify({"ok": False, "message": str(error), "conflict": True}), 409
        flash(str(error), "danger")
        return redirect(url_for("agenda_view"))

    @app.route("/")
    def dashboard():
        return render_react_shell_response("")
    @app.route("/agenda")
    def agenda_view():
        return render_react_shell_response("agenda")
    @app.route("/agenda/nuovo", methods=["GET", "POST"])
    def nuovo_appuntamento():
        if request.method == "GET":
            return render_react_shell_response("agenda/nuovo")
        if request.method == "POST":
            negato = _agenda_non_autorizzato("agenda.scrivi")
            if negato is not None:
                return negato
            id_fascicolo = request.form.get("id_fascicolo", "").strip()
            if id_fascicolo and get_fascicoli().get(id_fascicolo) is None:
                if richiede_json():
                    return jsonify({"ok": False, "message": "Il fascicolo collegato non è disponibile nello studio corrente."}), 404
                flash("Il fascicolo collegato non è disponibile nello studio corrente.", "danger")
                return redirect(url_for("agenda_view"))
            agenda = get_agenda()
            data = request.form.get("data", "")
            ora = request.form.get("ora", "09:00")
            data_ora = f"{data}T{ora}:00" if data else ""
            id_cliente_post = request.form.get("id_cliente", "")
            from_cliente = request.form.get("from_cliente", "")
            try:
                new_app = agenda.aggiungi(
                    titolo=request.form["titolo"],
                    tipo=TipoAppuntamento(request.form["tipo"]),
                    data_ora=data_ora,
                    durata_minuti=int(request.form.get("durata", 60)),
                    luogo=request.form.get("luogo", ""),
                    cliente=request.form.get("cliente", ""),
                    cf_cliente=request.form.get("cf_cliente", ""),
                    id_cliente=id_cliente_post,
                    id_fascicolo=id_fascicolo,
                    procedimento=request.form.get("procedimento", ""),
                    tribunale=request.form.get("tribunale", ""),
                    avvocato=request.form.get("avvocato", ""),
                    note=request.form.get("note", ""),
                    reminder_minuti=int(request.form.get("reminder", 60)),
                )
                flash(f"Appuntamento '{new_app.titolo}' aggiunto.", "success")
                if from_cliente:
                    target = url_for("cartella_cliente", id_cliente=from_cliente)
                    if richiede_json():
                        return jsonify({"ok": True, "id": new_app.id, "message": f"Appuntamento '{new_app.titolo}' aggiunto.", "redirect": target})
                    return redirect(url_for("cartella_cliente", id_cliente=from_cliente))
                target = url_for("dettaglio_appuntamento", id_app=new_app.id)
                if richiede_json():
                    return jsonify({"ok": True, "id": new_app.id, "message": f"Appuntamento '{new_app.titolo}' aggiunto.", "redirect": target})
                return redirect(url_for("dettaglio_appuntamento", id_app=new_app.id))
            except ValueError as e:
                if richiede_json():
                    return jsonify({"ok": False, "message": str(e)}), 400
                flash(str(e), "danger")
        return redirect(url_for("nuovo_appuntamento"))
    @app.route("/agenda/<id_app>")
    def dettaglio_appuntamento(id_app):
        agenda = get_agenda()
        app_item = agenda.get(id_app)
        if not app_item:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))
        return render_react_shell_response(f"agenda/{id_app}")
    def _allinea_scadenze_spostamento(id_app: str, data_prima: str, data_dopo: str) -> None:
        # L'udienza spostata in agenda sposta anche la scadenza collegata.
        try:
            from web.services.agenda_scadenze_sync import allinea_dopo_spostamento

            allinea_dopo_spostamento(get_scadenziario(), id_app, data_prima, data_dopo)
        except Exception as exc:
            app.logger.warning("Scadenze non allineate allo spostamento di %s: %s", id_app, exc)

    def _allinea_scadenze_eliminazione(id_app: str, evento: str = "eliminato dall'agenda") -> None:
        try:
            from web.services.agenda_scadenze_sync import allinea_dopo_eliminazione

            allinea_dopo_eliminazione(get_scadenziario(), id_app, evento=evento)
        except Exception as exc:
            app.logger.warning("Scadenze non scollegate dall'appuntamento %s: %s", id_app, exc)

    @app.route("/agenda/<id_app>/modifica", methods=["GET", "POST"])
    def modifica_appuntamento(id_app):
        _negato = _agenda_non_autorizzato("agenda.scrivi")
        if _negato is not None:
            return _negato
        agenda = get_agenda()
        app_item = agenda.get(id_app)
        if not app_item:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))
        if request.method == "GET":
            return render_react_shell_response(f"agenda/{id_app}/modifica")
        if request.method == "POST":
            data = request.form.get("data", "")
            ora = request.form.get("ora", "09:00")
            campi = {
                "titolo": request.form["titolo"],
                "tipo": TipoAppuntamento(request.form["tipo"]),
                "data_ora": f"{data}T{ora}:00" if data else app_item.data_ora,
                "durata_minuti": int(request.form.get("durata", app_item.durata_minuti)),
                "luogo": request.form.get("luogo", ""),
                "cliente": request.form.get("cliente", ""),
                "cf_cliente": request.form.get("cf_cliente", ""),
                "id_cliente": request.form.get("id_cliente", app_item.id_cliente),
                "procedimento": request.form.get("procedimento", ""),
                "tribunale": request.form.get("tribunale", ""),
                "avvocato": request.form.get("avvocato", ""),
                "note": request.form.get("note", ""),
                "reminder_minuti": int(request.form.get("reminder", app_item.reminder_minuti)),
            }
            try:
                data_prima = str(app_item.data_ora or "")
                version = request.form.get("expected_version")
                if richiede_json() and not version:
                    raise AgendaConflict("Carica la versione aggiornata dell’appuntamento prima di salvare. I dati inseriti restano nel modulo.")
                agenda.modifica(id_app, expected_version=version, **campi)
                _allinea_scadenze_spostamento(id_app, data_prima, str(campi.get("data_ora") or ""))
                flash("Appuntamento aggiornato.", "success")
                sync_pubblica("modifica", "agenda", id_app)
                target = url_for("dettaglio_appuntamento", id_app=id_app)
                if richiede_json():
                    return jsonify({"ok": True, "id": id_app, "message": "Appuntamento aggiornato.", "redirect": target})
                return redirect(url_for("dettaglio_appuntamento", id_app=id_app))
            except (ValueError, KeyError) as e:
                if richiede_json():
                    return jsonify({"ok": False, "message": str(e)}), 400
                flash(str(e), "danger")
        return redirect(url_for("modifica_appuntamento", id_app=id_app))
    @app.route("/agenda/<id_app>/stato", methods=["POST"])
    def cambia_stato(id_app):
        _negato = _agenda_non_autorizzato("agenda.scrivi")
        if _negato is not None:
            return _negato
        agenda = get_agenda()
        nuovo = request.form.get("stato")
        try:
            aggiornato = agenda.cambia_stato(id_app, StatoAppuntamento(nuovo))
            if aggiornato.stato == StatoAppuntamento.ANNULLATO:
                _allinea_scadenze_eliminazione(id_app, evento="annullato in agenda")
            sync_pubblica("modifica", "agenda", id_app)
            message = f"Stato aggiornato: {aggiornato.stato.value.lower()}."
            flash(message, "success")
            if richiede_json():
                return jsonify({"ok": True, "id": id_app, "stato": aggiornato.stato.value, "message": message})
        except (KeyError, ValueError) as e:
            flash(str(e), "danger")
            if richiede_json():
                return jsonify({"ok": False, "message": str(e)}), 400
        return redirect(url_for("dettaglio_appuntamento", id_app=id_app))
    @app.route("/agenda/<id_app>/elimina", methods=["POST"])
    def elimina_appuntamento(id_app):
        _negato = _agenda_non_autorizzato("agenda.elimina")
        if _negato is not None:
            return _negato
        agenda = get_agenda()
        try:
            agenda.elimina(id_app)
            _allinea_scadenze_eliminazione(id_app)
            message = "Voce eliminata dall'agenda."
            flash(message, "success")
            sync_pubblica("elimina", "agenda", id_app)
            if richiede_json():
                return jsonify({"ok": True, "id": id_app, "message": message, "redirect": url_for("agenda_view")})
        except KeyError:
            flash("Appuntamento non trovato.", "danger")
            if richiede_json():
                return jsonify({"ok": False, "message": "Appuntamento non trovato."}), 404
        return redirect(url_for("agenda_view"))
    @app.route("/agenda/importa", methods=["GET", "POST"])
    def importa_calendario():
        if request.method == "GET":
            return render_react_shell_response("agenda/importa")
        import json as _json
        from pct.agenda import TipoAppuntamento
        from pct.ical_import import dict_to_evento, evento_to_dict, parse_ics
        fase = request.form.get("fase", "")
        calendar_sync = get_calendar_sync()
        def _render_upload_form(**extra):
            context = {
                "fase": "upload_form",
                "sorgente": "generico",
                "profili_sync": calendar_sync.list_profiles(),
                "oggi": date.today(),
            }
            context.update(extra)
            return render_template("importa_calendario.html", **context)
        def _render_preview(*, sorgente, eventi, import_metadata, source_url="", content_type=""):
            return render_template(
                "importa_calendario.html",
                fase="preview",
                sorgente=sorgente,
                eventi=eventi,
                eventi_json=_json.dumps([evento_to_dict(e) for e in eventi], ensure_ascii=False),
                import_metadata_json=_json.dumps(import_metadata, ensure_ascii=False),
                source_url=source_url,
                content_type=content_type,
                profili_sync=calendar_sync.list_profiles(),
                oggi=date.today(),
            )
        if request.method == "GET":
            return _render_upload_form()
        if request.method == "POST" and fase == "upload":
            import hashlib as _hashlib
            modalita_import = request.form.get("modalita_import", "file")
            sorgente = request.form.get("sorgente", "generico")
            default_tipo = request.form.get("default_tipo", TipoAppuntamento.ALTRO.value)
            reminder_raw = request.form.get("default_reminder_minuti", "60")
            try:
                default_reminder_minuti = max(int(reminder_raw or 60), 0)
            except (TypeError, ValueError):
                default_reminder_minuti = 60
            if modalita_import == "url":
                source_url = request.form.get("source_url", "").strip()
                save_profile = request.form.get("salva_profilo") == "1"
                profile_name = (request.form.get("profile_name", "") or "").strip()
                if not source_url:
                    flash("Inserisci l'URL del calendario remoto.", "warning")
                    return _render_upload_form(
                        sorgente=sorgente,
                        modalita_import=modalita_import,
                        source_url=source_url,
                    )
                try:
                    preview = calendar_sync.preview_remote_calendar(source_url)
                    eventi = preview["events"]
                except Exception as e:
                    app.logger.exception("Errore preview calendario remoto: %s", e)
                    flash(f"Impossibile leggere il calendario remoto: {e}", "danger")
                    return _render_upload_form(
                        sorgente=sorgente,
                        modalita_import=modalita_import,
                        source_url=source_url,
                    )
                if not eventi:
                    flash("Il calendario remoto non contiene eventi validi.", "warning")
                    return _render_upload_form(
                        sorgente=sorgente,
                        modalita_import=modalita_import,
                        source_url=source_url,
                    )
                import_metadata = {
                    "modalita_import": "url",
                    "provider": sorgente or "webcal",
                    "source_url": preview["source_url"],
                    "source_hash": preview["source_hash"],
                    "save_profile": save_profile,
                    "profile_name": profile_name or "Calendario esterno",
                    "default_tipo": default_tipo,
                    "default_reminder_minuti": default_reminder_minuti,
                }
                return _render_preview(
                    sorgente=sorgente,
                    eventi=eventi,
                    import_metadata=import_metadata,
                    source_url=preview["source_url"],
                    content_type=preview.get("content_type", ""),
                )
            file = request.files.get("file_ics")
            if not file or not file.filename:
                flash("Nessun file selezionato.", "warning")
                return _render_upload_form(sorgente=sorgente, modalita_import=modalita_import)

            raw = file.read()
            try:
                testo = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    testo = raw.decode("utf-16")
                except UnicodeDecodeError:
                    testo = raw.decode("latin-1", errors="replace")

            try:
                eventi = parse_ics(testo)
            except Exception as e:
                app.logger.exception("Errore parsing ICS: %s", e)
                flash(f"Errore nell'analisi del file: {e}", "danger")
                return _render_upload_form(sorgente=sorgente, modalita_import=modalita_import)

            if not eventi:
                flash("Il file non contiene eventi validi.", "warning")
                return _render_upload_form(sorgente=sorgente, modalita_import=modalita_import)

            import_metadata = {
                "modalita_import": "file",
                "provider": f"manual_{sorgente}",
                "source_url": "",
                "source_hash": _hashlib.sha256(raw).hexdigest(),
                "filename": file.filename,
                "save_profile": False,
                "profile_name": "",
                "default_tipo": default_tipo,
                "default_reminder_minuti": default_reminder_minuti,
            }
            return _render_preview(
                sorgente=sorgente,
                eventi=eventi,
                import_metadata=import_metadata,
            )

        if request.method == "POST" and fase == "importa":
            sorgente = request.form.get("sorgente", "generico")
            selezionati_str = request.form.getlist("sel")
            eventi_json_str = request.form.get("eventi_json", "[]")
            import_metadata_str = request.form.get("import_metadata_json", "{}")

            try:
                tutti_eventi_dict = _json.loads(eventi_json_str)
                import_metadata = _json.loads(import_metadata_str or "{}")
            except Exception:
                flash("Errore nei dati del form. Riprova.", "danger")
                return redirect(url_for("importa_calendario"))

            selezionati_idx = set()
            for item in selezionati_str:
                try:
                    selezionati_idx.add(int(item))
                except ValueError:
                    pass

            eventi_da_importare = [
                dict_to_evento(tutti_eventi_dict[i])
                for i in sorted(selezionati_idx)
                if 0 <= i < len(tutti_eventi_dict)
            ]

            if not eventi_da_importare:
                flash("Nessun evento selezionato.", "warning")
                return redirect(url_for("importa_calendario"))

            agenda = get_agenda()
            provider = import_metadata.get("provider") or f"manual_{sorgente}"
            source_url = import_metadata.get("source_url", "")
            default_tipo = import_metadata.get("default_tipo", TipoAppuntamento.ALTRO.value)
            reminder_minuti = int(import_metadata.get("default_reminder_minuti", 60) or 60)
            profile_id = ""
            if import_metadata.get("save_profile") and source_url:
                profile_name = (import_metadata.get("profile_name", "") or "").strip() or "Calendario esterno"
                profilo_esistente = next(
                    (
                        profilo
                        for profilo in calendar_sync.list_profiles()
                        if (profilo.get("source_url") or "").strip() == source_url
                        and (profilo.get("provider") or "").strip() == provider
                    ),
                    None,
                )
                if profilo_esistente:
                    profilo = calendar_sync.update_profile(
                        profilo_esistente["id"],
                        nome=profile_name,
                        enabled=True,
                        default_tipo=default_tipo,
                        default_reminder_minuti=reminder_minuti,
                        source_url=source_url,
                    )
                else:
                    profilo = calendar_sync.create_profile(
                        nome=profile_name,
                        provider=provider,
                        source_url=source_url,
                        default_tipo=default_tipo,
                        default_reminder_minuti=reminder_minuti,
                        enabled=True,
                    )
                profile_id = profilo["id"]

            importati = 0
            aggiornati = 0
            saltati = 0
            conflitti = 0
            titoli_err: list[str] = []

            for ev in eventi_da_importare:
                try:
                    report = agenda.upsert_da_evento_importato(
                        ev,
                        provider=provider,
                        source_url=source_url,
                        profile_id=profile_id,
                        default_tipo=default_tipo,
                        reminder_minuti=reminder_minuti,
                    )
                    outcome = report.get("outcome")
                    if outcome == "created":
                        importati += 1
                    elif outcome == "updated":
                        aggiornati += 1
                    elif outcome == "conflict":
                        conflitti += 1
                        titoli_err.append(f"{ev.titolo} ({report.get('message', 'conflitto')})")
                    else:
                        saltati += 1
                except ValueError as e:
                    conflitti += 1
                    titoli_err.append(f"{ev.titolo} ({e})")
                except Exception as e:
                    saltati += 1
                    app.logger.warning("Import evento '%s': %s", ev.titolo, e)

            msg_parts = []
            if importati:
                msg_parts.append(f"{importati} eventi creati.")
            if aggiornati:
                msg_parts.append(f"{aggiornati} eventi aggiornati.")
            if conflitti:
                msg_parts.append(f"{conflitti} con conflitto di orario (saltati).")
            if saltati:
                msg_parts.append(f"{saltati} gia allineati o non importati.")
            if not msg_parts:
                msg_parts.append("Nessun cambiamento da importare.")
            flash(" ".join(msg_parts), "success" if (importati or aggiornati) else "warning")

            if titoli_err:
                flash("Conflitti: " + "; ".join(titoli_err[:5]), "warning")

            if profile_id and source_url:
                calendar_sync.update_profile(
                    profile_id,
                    last_sync_at=datetime.now().replace(microsecond=0).isoformat(),
                    last_status="ok",
                    last_message="Import iniziale completato dal wizard agenda.",
                    last_created=importati,
                    last_updated=aggiornati,
                    last_skipped=saltati,
                    last_conflicts=conflitti,
                    last_source_hash=import_metadata.get("source_hash", ""),
                )
                flash("Profilo sincronizzazione salvato nelle impostazioni calendario.", "success")

            return redirect(url_for("agenda_view"))
        return render_template(
            "importa_calendario.html",
            fase="upload_form",
            sorgente="generico",
            oggi=date.today(),
        )
    register_agenda_api_routes(app, get_agenda=get_agenda, audit=audit, allinea_spostamento=_allinea_scadenze_spostamento)
