"""Dashboard and agenda routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for, g

from pct.agenda import Agenda, StatoAppuntamento, TipoAppuntamento
from pct.economic_dashboard import build_studio_economic_dashboard
from pct.studio_demo import build_studio_demo_snapshot


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

    @app.route("/")
    def dashboard():
        agenda = get_agenda()
        oggi = date.today()
        apps_oggi = agenda.per_giorno(oggi)
        apps_settimana = agenda.per_settimana(oggi)
        reminder = agenda.prossimi_reminder(entro_minuti=120)
        stats = agenda.statistiche()
        gs = get_scadenziario()
        scadenze_critiche = gs.imminenti(entro_giorni=3)
        scadenze_imminenti = gs.imminenti(entro_giorni=7)
        stats_sc = gs.statistiche()
        gestore_fascicoli = get_fascicoli()
        gestore_clienti = get_clienti()
        gestore_timesheet = get_timesheet()
        gestore_preventivi = get_preventivi()
        gestore_fatturazione = get_fatturazione()
        gestore_pagamenti = get_pagamenti()
        stats_fascicoli = gestore_fascicoli.statistiche()
        stats_clienti = gestore_clienti.statistiche()
        economic_overview = build_studio_economic_dashboard(
            fascicoli=gestore_fascicoli.tutti(stato=None),
            parcelle=gestore_fatturazione.tutte(),
            timesheet_entries=gestore_timesheet.tutte(),
            scadenze_imminenti=scadenze_imminenti,
        )
        studio_demo_snapshot = build_studio_demo_snapshot(
            clienti=gestore_clienti.tutti(stato=None),
            fascicoli=gestore_fascicoli.tutti(stato=None),
            preventivi=gestore_preventivi.tutti_preventivi(),
            conferimenti=gestore_preventivi.tutti_conferimenti(),
            parcelle=gestore_fatturazione.tutte(),
            timesheet_entries=gestore_timesheet.tutte(),
            payment_links=gestore_pagamenti.tutti_link(),
        )
        workspace_overview = get_workspace_intelligente().panoramica(
            horizon_days=14,
            hot_limit=6,
        )
        u_dash = g.utente_corrente
        cartelle_mie = []
        accessi_in_scadenza = []
        if u_dash and not u_dash.ha_permesso("clienti.leggi"):
            gcd = get_condivisioni()
            gc = get_clienti()
            cartelle_mie = [
                (gc.get(id_c), ac)
                for id_c, ac in gcd.cartelle_condivise_con(u_dash.id)
                if gc.get(id_c) and not ac.is_scaduto
            ][:5]
            accessi_in_scadenza = gcd.accessi_in_scadenza(entro_giorni=7)
        clienti_doc_scaduti = []
        if u_dash and u_dash.ha_permesso("clienti.leggi"):
            try:
                clienti_doc_scaduti = [
                    c
                    for c in get_clienti().tutti()
                    if c.documento.scaduto and c.documento.numero
                ][:10]
            except Exception:
                pass
        return render_template(
            "dashboard.html",
            apps_oggi=apps_oggi,
            apps_settimana=apps_settimana,
            reminder=reminder,
            stats=stats,
            scadenze_critiche=scadenze_critiche,
            scadenze_imminenti=scadenze_imminenti,
            stats_sc=stats_sc,
            stats_fascicoli=stats_fascicoli,
            stats_clienti=stats_clienti,
            cartelle_mie=cartelle_mie,
            accessi_in_scadenza=accessi_in_scadenza,
            clienti_doc_scaduti=clienti_doc_scaduti,
            workspace_overview=workspace_overview,
            economic_overview=economic_overview,
            studio_demo_snapshot=studio_demo_snapshot,
        )

    @app.route("/agenda")
    def agenda_view():
        agenda = get_agenda()
        vista = request.args.get("vista", "settimana")
        oggi = date.today()
        offset = int(request.args.get("offset", 0))

        if vista == "giorno":
            giorno = oggi + timedelta(days=offset)
            apps = agenda.per_giorno(giorno)
            return render_template(
                "agenda.html",
                vista=vista,
                apps=apps,
                giorno=giorno,
                offset=offset,
            )

        if vista == "mese":
            import calendar

            anno = oggi.year
            mese = oggi.month + offset
            while mese > 12:
                mese -= 12
                anno += 1
            while mese < 1:
                mese += 12
                anno -= 1
            apps = agenda.per_mese(anno, mese)
            primo = date(anno, mese, 1)
            pad = primo.weekday()
            giorni_mese = calendar.monthrange(anno, mese)[1]
            return render_template(
                "agenda.html",
                vista=vista,
                apps=apps,
                anno=anno,
                mese=mese,
                primo=primo,
                pad=pad,
                giorni_mese=giorni_mese,
                offset=offset,
                nomi_mesi=["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"],
            )

        inizio = oggi + timedelta(weeks=offset) - timedelta(days=oggi.weekday())
        fine = inizio + timedelta(days=6)
        apps = agenda.per_settimana(inizio)
        giorni = [inizio + timedelta(days=i) for i in range(7)]
        apps_per_giorno = {g: [a for a in apps if a.data_ora_dt.date() == g] for g in giorni}
        return render_template(
            "agenda.html",
            vista=vista,
            apps=apps,
            apps_per_giorno=apps_per_giorno,
            giorni=giorni,
            inizio=inizio,
            fine=fine,
            offset=offset,
        )

    @app.route("/agenda/nuovo", methods=["GET", "POST"])
    def nuovo_appuntamento():
        if request.method == "POST":
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
                    procedimento=request.form.get("procedimento", ""),
                    tribunale=request.form.get("tribunale", ""),
                    avvocato=request.form.get("avvocato", ""),
                    note=request.form.get("note", ""),
                    reminder_minuti=int(request.form.get("reminder", 60)),
                )
                flash(f"Appuntamento '{new_app.titolo}' aggiunto.", "success")
                if from_cliente:
                    return redirect(url_for("cartella_cliente", id_cliente=from_cliente))
                return redirect(url_for("dettaglio_appuntamento", id_app=new_app.id))
            except ValueError as e:
                flash(str(e), "danger")

        data_default = request.args.get("data", "")
        id_cliente_get = request.args.get("id_cliente", "")
        from_cliente_get = request.args.get("from_cliente", "")
        cliente_presel = None
        if id_cliente_get:
            cliente_presel = get_clienti().get(id_cliente_get)
        return render_template(
            "form_appuntamento.html",
            app=None,
            tipi=list(TipoAppuntamento),
            data_default=data_default,
            id_cliente=id_cliente_get,
            from_cliente=from_cliente_get,
            cliente_presel=cliente_presel,
        )

    @app.route("/agenda/<id_app>")
    def dettaglio_appuntamento(id_app):
        agenda = get_agenda()
        app_item = agenda.get(id_app)
        if not app_item:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))
        track_recente(
            "appuntamento",
            id_app,
            app_item.titolo,
            url_for("dettaglio_appuntamento", id_app=id_app),
            "bi-calendar-event",
        )
        return render_template("dettaglio_appuntamento.html", app=app_item)

    @app.route("/agenda/<id_app>/modifica", methods=["GET", "POST"])
    def modifica_appuntamento(id_app):
        agenda = get_agenda()
        app_item = agenda.get(id_app)
        if not app_item:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))

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
                agenda.modifica(id_app, **campi)
                flash("Appuntamento aggiornato.", "success")
                sync_pubblica("modifica", "agenda", id_app)
                return redirect(url_for("dettaglio_appuntamento", id_app=id_app))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        return render_template(
            "form_appuntamento.html",
            app=app_item,
            tipi=list(TipoAppuntamento),
        )

    @app.route("/agenda/<id_app>/stato", methods=["POST"])
    def cambia_stato(id_app):
        agenda = get_agenda()
        nuovo = request.form.get("stato")
        try:
            agenda.cambia_stato(id_app, StatoAppuntamento(nuovo))
            flash("Stato aggiornato.", "success")
        except (KeyError, ValueError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_appuntamento", id_app=id_app))

    @app.route("/agenda/<id_app>/elimina", methods=["POST"])
    def elimina_appuntamento(id_app):
        agenda = get_agenda()
        try:
            agenda.elimina(id_app)
            flash("Appuntamento eliminato.", "success")
            sync_pubblica("elimina", "agenda", id_app)
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("agenda_view"))

    @app.route("/agenda/importa", methods=["GET", "POST"])
    def importa_calendario():
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

    @app.route("/api/agenda/<id_app>/sposta", methods=["POST"])
    def api_sposta_appuntamento(id_app):
        if not g.utente_corrente or not g.utente_corrente.ha_permesso("agenda.scrivi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        agenda = get_agenda()
        appt = agenda.get(id_app)
        if not appt:
            return jsonify({"errore": "Appuntamento non trovato"}), 404
        payload = request.get_json(silent=True) or {}
        nuova_data = payload.get("data")
        nuova_data_ora = payload.get("data_ora")
        if nuova_data and not nuova_data_ora:
            ora_orig = appt.data_ora_dt.strftime("%H:%M:%S")
            nuova_data_ora = f"{nuova_data}T{ora_orig}"
        if not nuova_data_ora:
            return jsonify({"errore": "Parametro 'data' o 'data_ora' richiesto"}), 400
        try:
            appt = agenda.modifica(id_app, data_ora=nuova_data_ora)
            audit("agenda.sposta", "appuntamento", id_app, dettagli=f"→ {nuova_data_ora}")
            return jsonify({"ok": True, "data_ora": appt.data_ora})
        except (ValueError, KeyError) as e:
            return jsonify({"errore": str(e)}), 409

    @app.route("/api/agenda")
    def api_agenda():
        try:
            agenda = get_agenda()
            da_str = request.args.get("da")
            a_str = request.args.get("a")
            da = date.fromisoformat(da_str) if da_str else None
            a = date.fromisoformat(a_str) if a_str else None
            apps = agenda.cerca(da=da, a=a)
            return jsonify([a.to_dict() for a in apps])
        except Exception as e:
            app.logger.exception("Errore api_agenda: %s", e)
            return jsonify([])

    @app.route("/api/agenda/<id_app>")
    def api_appuntamento(id_app):
        try:
            agenda = get_agenda()
            appt = agenda.get(id_app)
            if not appt:
                return jsonify({"errore": "Non trovato"}), 404
            return jsonify(appt.to_dict())
        except Exception as e:
            app.logger.exception("Errore api_appuntamento: %s", e)
            return jsonify({"errore": str(e)})

    @app.route("/api/reminder")
    def api_reminder():
        try:
            agenda = get_agenda()
            entro = int(request.args.get("entro", 60))
            apps = agenda.prossimi_reminder(entro_minuti=entro)
            return jsonify([a.to_dict() for a in apps])
        except Exception as e:
            app.logger.exception("Errore api_reminder: %s", e)
            return jsonify([])

    @app.route("/api/statistiche")
    def api_statistiche():
        try:
            return jsonify(get_agenda().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_statistiche: %s", e)
            return jsonify({"errore": str(e)})
