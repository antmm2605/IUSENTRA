"""Scadenziario routes extracted from web.app."""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any

from web.blueprints.react_shell import render_react_shell_response
from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for
from pct.scadenziario import (
    PRESET_TERMINI,
    GestioneScadenziario,
    PrioritaTermine,
    ProfiloTermine,
    Scadenza,
    StatoTermine,
    TipoTermine,
    calcola_termine,
    profilo_da_preset,
    profili_termine_builtin,
    regola_patrono_ufficio,
    riepilogo_operativo_scadenza,
    è_giorno_lavorativo,
)
from web.services.request_mode import richiede_json, richiede_vista_classica
from web.services.scadenziario_shell_bootstrap import scadenza_detail_shell_texts, scadenziario_shell_texts
from web.services.scadenziario_views import label_vista_scadenziario, normalizza_vista_scadenziario, scadenza_detail_context, scadenze_per_vista


def register_scadenziario_routes(
    app: Flask,
    *,
    get_agenda: Callable[[], object],
    get_scadenziario: Callable[[], GestioneScadenziario],
    get_fascicoli: Callable[[], object],
    get_utenti: Callable[[], object],
    get_config_studio: Callable[[], object],
    _studio_patron_rule_from_config: Callable[[], object],
    _resolve_judicial_office_by_code: Callable[[str], dict[str, Any]],
    audit: Callable[..., None],
    sync_pubblica: Callable[[str, str, str], None],
) -> None:
    """Register scadenziario CRUD, notifications, and calculation routes."""

    def _scadenziario_form_context(scadenza: Scadenza | None = None):
        gf = get_fascicoli()
        gu = get_utenti()
        id_cliente_get = request.args.get("id_cliente", "")
        from_cliente_get = request.args.get("from_cliente", "")
        fascicoli = gf.tutti()
        id_fascicolo_presel = ""
        if id_cliente_get and not scadenza:
            fascicoli_cliente = [f for f in fascicoli if f.id_cliente == id_cliente_get]
            if fascicoli_cliente:
                fascicoli = fascicoli_cliente
                id_fascicolo_presel = fascicoli_cliente[0].id
        return {
            "tipi": list(TipoTermine),
            "preset_list": PRESET_TERMINI,
            "profili_termine": profili_termine_builtin(),
            "fascicoli": fascicoli,
            "utenti": gu.tutti(solo_attivi=True),
            "scadenza": scadenza,
            "id_cliente": id_cliente_get,
            "from_cliente": from_cliente_get,
            "id_fascicolo_presel": id_fascicolo_presel,
            "studio_cfg": get_config_studio().config.studio,
        }

    def _parse_int(value, default=0):
        try:
            return int(value or default)
        except (TypeError, ValueError):
            return default

    def _parse_bool(value) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "on", "yes"}

    def _calcola_scadenza_form_payload(payload: dict) -> dict:
        preset_key = str(payload.get("preset", "") or "").strip()
        profile_code = str(payload.get("deadline_profile_code", "") or "").strip()
        source_event_at = str(
            payload.get("source_event_at", "")
            or payload.get("data_inizio", "")
            or payload.get("data_decorrenza", "")
            or ""
        ).strip()
        office_code = str(payload.get("judicial_office_id", "") or "").strip()
        office_info = _resolve_judicial_office_by_code(office_code)
        office_patron_name = str(payload.get("office_patron_name", "") or "").strip()
        office_patron_day = _parse_int(payload.get("office_patron_day", 0))
        office_patron_month = _parse_int(payload.get("office_patron_month", 0))
        office_operating_mode = str(payload.get("office_operating_mode", "") or "open").strip() or "open"
        operational_lead_business_days = _parse_int(payload.get("operational_lead_business_days", 0))
        october_observance_blocks = _parse_bool(payload.get("october_observance_blocks"))

        if preset_key:
            profile = profilo_da_preset(preset_key)
        elif profile_code:
            profili = profili_termine_builtin()
            if profile_code not in profili:
                raise ValueError("Profilo termine non valido")
            profile = ProfiloTermine.from_dict(profili[profile_code])
        else:
            raise ValueError("Seleziona un preset o un profilo termine")

        if not source_event_at:
            raise ValueError("Data/ora evento origine obbligatoria per il calcolo del termine")

        office_rule = regola_patrono_ufficio(
            office_code,
            office_patron_name,
            office_patron_day,
            office_patron_month,
            operating_mode=office_operating_mode,
            source_url=str(payload.get("office_source_url", "") or "").strip(),
            verified_at=str(payload.get("office_verified_at", "") or "").strip(),
        )
        studio_rule = _studio_patron_rule_from_config()
        result = GestioneScadenziario.calcola_avanzata(
            start_at=source_event_at,
            profile=profile,
            studio_rule=studio_rule,
            office_rule=office_rule,
            include_october_observance_blocking=october_observance_blocks,
            operational_lead_business_days=operational_lead_business_days,
        )
        return {
            "profile": profile,
            "result": result,
            "source_event_at": source_event_at,
            "judicial_office_id": office_code,
            "judicial_office_name": str(office_info.get("nome") or "").strip(),
            "judicial_office_type": str(office_info.get("tipo") or "").strip(),
            "judicial_office_city": str(office_info.get("citta") or office_info.get("city") or "").strip(),
            "judicial_office_patron_name": office_patron_name,
            "judicial_office_patron_day": office_patron_day,
            "judicial_office_patron_month": office_patron_month,
            "judicial_office_operating_mode": office_operating_mode,
            "judicial_office_source_url": str(payload.get("office_source_url", "") or "").strip(),
            "judicial_office_verified_at": str(payload.get("office_verified_at", "") or "").strip(),
            "operational_lead_business_days": operational_lead_business_days,
            "october_observance_blocks": october_observance_blocks,
            "preset_key": preset_key,
        }
    @app.route("/scadenziario")
    def scadenziario():
        gs = get_scadenziario()
        filtro_tipo = request.args.get("tipo", "")
        filtro_priorita = request.args.get("priorita", "")
        id_fascicolo = request.args.get("id_fascicolo", "")
        q = request.args.get("q", "").strip()
        filtro_dal = request.args.get("dal", "")
        filtro_al = request.args.get("al", "")
        filtro_perentorio = request.args.get("perentorio", "")
        filtro_avanzate = request.args.get("avanzate", "")
        filtro_operative = request.args.get("operative", "")
        filtro_vista = normalizza_vista_scadenziario(request.args.get("vista", "aperte"))
        # Aggiorna prima gli stati scaduti, così contatori e viste sono coerenti.
        tipo_obj = TipoTermine(filtro_tipo) if filtro_tipo else None
        priorita_obj = PrioritaTermine(filtro_priorita) if filtro_priorita else None

        scadenze = scadenze_per_vista(
            gs,
            vista=filtro_vista,
            tipo=tipo_obj,
            priorita=priorita_obj,
            id_fascicolo=id_fascicolo,
        )

        if q:
            ql = q.lower()
            scadenze = [
                s
                for s in scadenze
                if ql in s.titolo.lower() or ql in (s.descrizione or "").lower()
            ]
        if filtro_dal:
            scadenze = [s for s in scadenze if s.data_scadenza >= filtro_dal]
        if filtro_al:
            scadenze = [s for s in scadenze if s.data_scadenza <= filtro_al]
        if filtro_perentorio:
            scadenze = [s for s in scadenze if s.perentorio]
        if filtro_avanzate:
            scadenze = [s for s in scadenze if s.ha_calcolo_avanzato]
        if filtro_operative:
            scadenze = [s for s in scadenze if bool(s.operational_due_at)]
        if not richiede_vista_classica():
            texts = scadenziario_shell_texts(scadenze, avanzate=filtro_avanzate, operative=filtro_operative)
            return render_react_shell_response("scadenziario", bootstrap_texts=texts)
        scadute = gs.tutte(stato=StatoTermine.SCADUTO, solo_aperte=False)
        scadenze_critiche = gs.imminenti(entro_giorni=3)
        imminenti = gs.imminenti(entro_giorni=7)
        stats = gs.statistiche()
        return render_template(
            "scadenziario/lista.html",
            scadenze=scadenze,
            scadute=scadute,
            scadenze_critiche=scadenze_critiche,
            imminenti=imminenti,
            stats=stats,
            tipi=list(TipoTermine),
            priorita_list=list(PrioritaTermine),
            filtro_tipo=filtro_tipo,
            filtro_priorita=filtro_priorita,
            id_fascicolo=id_fascicolo,
            q=q,
            filtro_dal=filtro_dal,
            filtro_al=filtro_al,
            filtro_perentorio=filtro_perentorio,
            filtro_avanzate=filtro_avanzate,
            filtro_operative=filtro_operative,
            filtro_vista=filtro_vista,
            vista_label=label_vista_scadenziario(filtro_vista),
        )
    @app.route("/scadenziario/nuova", methods=["GET", "POST"])
    def nuova_scadenza():
        if request.method == "GET" and not richiede_vista_classica():
            return render_react_shell_response("scadenziario/nuova")

        if request.method == "POST":
            gs = get_scadenziario()
            form = request.form
            from_cliente = form.get("from_cliente", "")
            try:
                preset = form.get("preset", "")
                data_scadenza = form.get("data_scadenza", "").strip()
                usa_calcolo = bool(
                    preset or form.get("deadline_profile_code") or form.get("source_event_at")
                )
                if usa_calcolo:
                    calc = _calcola_scadenza_form_payload(dict(form))
                    sc = gs.nuova(
                        titolo=form["titolo"].strip(),
                        tipo=TipoTermine(form["tipo"]),
                        data_scadenza=calc["result"].legal_due_at[:10],
                        id_fascicolo=form.get("id_fascicolo", ""),
                        descrizione=form.get("descrizione", ""),
                        data_decorrenza=calc["source_event_at"][:10],
                        perentorio=form.get("perentorio") == "1",
                        id_utente_responsabile=form.get("id_utente", ""),
                        note=form.get("note", ""),
                        source_event_type=(
                            PRESET_TERMINI.get(calc["preset_key"], {}).get("source_event_type", "")
                            if calc["preset_key"]
                            else "evento"
                        ),
                        source_event_at=calc["source_event_at"],
                        deadline_profile_code=calc["profile"].code,
                        judicial_office_id=calc["judicial_office_id"],
                        judicial_office_name=calc["judicial_office_name"],
                        judicial_office_type=calc["judicial_office_type"],
                        judicial_office_city=calc["judicial_office_city"],
                        judicial_office_patron_name=calc["judicial_office_patron_name"],
                        judicial_office_patron_day=calc["judicial_office_patron_day"],
                        judicial_office_patron_month=calc["judicial_office_patron_month"],
                        judicial_office_operating_mode=calc["judicial_office_operating_mode"],
                        judicial_office_source_url=calc["judicial_office_source_url"],
                        judicial_office_verified_at=calc["judicial_office_verified_at"],
                        raw_due_at=calc["result"].raw_due_at,
                        legal_due_at=calc["result"].legal_due_at,
                        operational_due_at=calc["result"].operational_due_at or "",
                        office_mode_on_legal_due_date=calc["result"].office_mode_on_legal_due_date,
                        trace_json=json.dumps(calc["result"].trace, ensure_ascii=False),
                        operational_lead_business_days=calc["operational_lead_business_days"],
                        october_observance_blocks=calc["october_observance_blocks"],
                    )
                else:
                    if not data_scadenza:
                        raise ValueError("Data scadenza obbligatoria")
                    sc = gs.nuova(
                        titolo=form["titolo"].strip(),
                        tipo=TipoTermine(form["tipo"]),
                        data_scadenza=data_scadenza,
                        id_fascicolo=form.get("id_fascicolo", ""),
                        descrizione=form.get("descrizione", ""),
                        data_decorrenza=form.get("data_decorrenza", "").strip(),
                        perentorio=form.get("perentorio") == "1",
                        id_utente_responsabile=form.get("id_utente", ""),
                        note=form.get("note", ""),
                    )
                audit("scadenziario.crea", "scadenza", sc.id, sc.titolo)
                flash(f"Scadenza '{sc.titolo}' creata.", "success")
                sync_pubblica("crea", "scadenze", sc.id)
                if from_cliente:
                    target = url_for("cartella_cliente", id_cliente=from_cliente)
                    if richiede_json():
                        return jsonify({"ok": True, "id": sc.id, "message": f"Scadenza '{sc.titolo}' creata.", "redirect": target})
                    return redirect(url_for("cartella_cliente", id_cliente=from_cliente))
                target = url_for("scadenziario")
                if richiede_json():
                    return jsonify({"ok": True, "id": sc.id, "message": f"Scadenza '{sc.titolo}' creata.", "redirect": target})
                return redirect(url_for("scadenziario"))
            except (ValueError, KeyError) as e:
                if richiede_json():
                    return jsonify({"ok": False, "message": str(e)}), 400
                flash(str(e), "danger")
        return render_template("scadenziario/form.html", **_scadenziario_form_context())
    @app.route("/scadenziario/<id_sc>")
    def dettaglio_scadenza(id_sc):
        gs = get_scadenziario()
        sc = gs.get(id_sc)
        if not sc:
            flash("Scadenza non trovata.", "warning")
            return redirect(url_for("scadenziario"))
        context = scadenza_detail_context(
            sc, gestione_fascicoli=get_fascicoli(), gestione_utenti=get_utenti(),
            gestione_agenda=get_agenda(), studio_cfg=get_config_studio().config.studio,
            profili_termine=profili_termine_builtin(),
        )
        if not richiede_vista_classica():
            return render_react_shell_response(f"scadenziario/{id_sc}", bootstrap_texts=scadenza_detail_shell_texts(context))
        return render_template("scadenziario/dettaglio.html", **context)
    @app.route("/scadenziario/<id_sc>/modifica", methods=["GET", "POST"])
    def modifica_scadenza(id_sc):
        gs = get_scadenziario()
        sc = gs.get(id_sc)
        if not sc:
            flash("Scadenza non trovata.", "warning")
            return redirect(url_for("scadenziario"))
        if request.method == "GET" and not richiede_vista_classica():
            return render_react_shell_response(f"scadenziario/{id_sc}/modifica")
        if request.method == "POST":
            form = request.form
            try:
                calc_payload = None
                if form.get("deadline_profile_code") or form.get("source_event_at"):
                    calc_payload = _calcola_scadenza_form_payload(dict(form))
                update_kwargs = dict(
                    titolo=form.get("titolo", sc.titolo),
                    tipo=form.get("tipo", sc.tipo.value),
                    data_scadenza=(
                        calc_payload["result"].legal_due_at[:10]
                        if calc_payload
                        else form.get("data_scadenza", sc.data_scadenza)
                    ),
                    descrizione=form.get("descrizione", sc.descrizione),
                    data_decorrenza=(
                        calc_payload["source_event_at"][:10]
                        if calc_payload
                        else form.get("data_decorrenza", sc.data_decorrenza)
                    ),
                    perentorio=form.get("perentorio") == "1",
                    note=form.get("note", sc.note),
                    id_fascicolo=form.get("id_fascicolo", sc.id_fascicolo),
                    id_utente_responsabile=form.get("id_utente", sc.id_utente_responsabile),
                )
                if calc_payload:
                    update_kwargs.update(
                        source_event_type=(
                            PRESET_TERMINI.get(calc_payload["preset_key"], {}).get("source_event_type", "")
                            if calc_payload["preset_key"]
                            else (sc.source_event_type or "evento")
                        ),
                        source_event_at=calc_payload["source_event_at"],
                        deadline_profile_code=calc_payload["profile"].code,
                        judicial_office_id=calc_payload["judicial_office_id"],
                        judicial_office_name=calc_payload["judicial_office_name"],
                        judicial_office_type=calc_payload["judicial_office_type"],
                        judicial_office_city=calc_payload["judicial_office_city"],
                        judicial_office_patron_name=calc_payload["judicial_office_patron_name"],
                        judicial_office_patron_day=calc_payload["judicial_office_patron_day"],
                        judicial_office_patron_month=calc_payload["judicial_office_patron_month"],
                        judicial_office_operating_mode=calc_payload["judicial_office_operating_mode"],
                        judicial_office_source_url=calc_payload["judicial_office_source_url"],
                        judicial_office_verified_at=calc_payload["judicial_office_verified_at"],
                        raw_due_at=calc_payload["result"].raw_due_at,
                        legal_due_at=calc_payload["result"].legal_due_at,
                        operational_due_at=calc_payload["result"].operational_due_at or "",
                        office_mode_on_legal_due_date=calc_payload["result"].office_mode_on_legal_due_date,
                        trace_json=json.dumps(calc_payload["result"].trace, ensure_ascii=False),
                        operational_lead_business_days=calc_payload["operational_lead_business_days"],
                        october_observance_blocks=calc_payload["october_observance_blocks"],
                    )
                else:
                    update_kwargs.update(
                        source_event_type="",
                        source_event_at="",
                        deadline_profile_code="",
                        judicial_office_id="",
                        judicial_office_name="",
                        judicial_office_type="",
                        judicial_office_city="",
                        judicial_office_patron_name="",
                        judicial_office_patron_day=0,
                        judicial_office_patron_month=0,
                        judicial_office_operating_mode="open",
                        judicial_office_source_url="",
                        judicial_office_verified_at="",
                        raw_due_at="",
                        legal_due_at="",
                        operational_due_at="",
                        office_mode_on_legal_due_date="open",
                        trace_json="[]",
                        operational_lead_business_days=0,
                        october_observance_blocks=False,
                    )
                gs.aggiorna(id_sc, **update_kwargs)
                audit("scadenziario.modifica", "scadenza", id_sc)
                flash("Scadenza aggiornata.", "success")
                sync_pubblica("modifica", "scadenze", id_sc)
                if richiede_json():
                    return jsonify({"ok": True, "id": id_sc, "message": "Scadenza aggiornata.", "redirect": url_for("scadenziario")})
                return redirect(url_for("scadenziario"))
            except (ValueError, KeyError) as e:
                if richiede_json():
                    return jsonify({"ok": False, "message": str(e)}), 400
                flash(str(e), "danger")
        return render_template("scadenziario/form.html", **_scadenziario_form_context(sc))
    @app.route("/scadenziario/<id_sc>/completa", methods=["POST"])
    def completa_scadenza(id_sc):
        gs = get_scadenziario()
        note = request.form.get("note", "")
        try:
            gs.completa(id_sc, note=note)
            audit("scadenziario.completa", "scadenza", id_sc)
            sync_pubblica("modifica", "scadenze", id_sc)
        except ValueError as e:
            if request.headers.get("HX-Request"):
                return f'<tr id="sc-{id_sc}"><td colspan="7" class="text-danger small p-2">{e}</td></tr>', 422
            flash(str(e), "danger")
            return redirect(url_for("scadenziario"))
        if request.headers.get("HX-Request"):
            return f'<tr id="sc-{id_sc}" class="sc-completed"><td colspan="7"></td></tr>', 200
        flash("Scadenza segnata come completata.", "success")
        return redirect(url_for("scadenziario"))
    @app.route("/scadenziario/bulk-completa", methods=["POST"])
    def bulk_completa_scadenze():
        u = g.utente_corrente
        if not u or not u.ha_permesso("scadenziario.scrivi"):
            flash("Permesso insufficiente.", "danger")
            return redirect(url_for("scadenziario"))
        ids = request.form.getlist("ids")
        if not ids:
            flash("Nessuna scadenza selezionata.", "warning")
            return redirect(url_for("scadenziario"))
        gs = get_scadenziario()
        completate = 0
        for id_sc in ids:
            try:
                gs.completa(id_sc)
                audit("scadenziario.completa", "scadenza", id_sc, dettagli="bulk")
                completate += 1
            except ValueError:
                pass
        if completate:
            sync_pubblica("modifica", "scadenze", "bulk")
            flash(
                f"{'1 scadenza segnata' if completate == 1 else str(completate) + ' scadenze segnate'} come completate.",
                "success",
            )
        return redirect(url_for("scadenziario"))
    @app.route("/api/notifiche/pending")
    def notifiche_pending():
        if not g.utente_corrente:
            return jsonify([])
        try:
            gs = get_scadenziario()
            alerts = []
            scadute = [
                s
                for s in gs.imminenti(entro_giorni=0)
                if s.giorni_alla_scadenza is not None and s.giorni_alla_scadenza < 0
            ]
            critiche_oggi = [s for s in gs.imminenti(entro_giorni=1) if s.giorni_alla_scadenza == 0]
            imminenti = [
                s
                for s in gs.imminenti(entro_giorni=3)
                if s.perentorio and (s.giorni_alla_scadenza or 0) > 0
            ]
            if scadute:
                alerts.append(
                    {
                        "titolo": f"⚠️ {len(scadute)} scadenza/e SCADUTA/E",
                        "corpo": " • ".join(s.titolo for s in scadute[:3]),
                        "url": "/scadenziario",
                        "delay": 2000,
                    }
                )
            if critiche_oggi:
                alerts.append(
                    {
                        "titolo": f"🔴 {len(critiche_oggi)} scadenza/e OGGI",
                        "corpo": " • ".join(s.titolo for s in critiche_oggi[:3]),
                        "url": "/scadenziario",
                        "delay": 4000,
                    }
                )
            if imminenti:
                alerts.append(
                    {
                        "titolo": f"🔔 {len(imminenti)} termine/i perentorio/i imminente/i",
                        "corpo": " • ".join(s.titolo for s in imminenti[:3]),
                        "url": "/scadenziario",
                        "delay": 6000,
                    }
                )
            return jsonify(alerts)
        except Exception as e:
            app.logger.exception("Errore notifiche_pending: %s", e)
            return jsonify([])
    @app.route("/api/notifiche/inbox")
    def notifiche_inbox():
        if not g.utente_corrente:
            return jsonify([])
        try:
            from datetime import timedelta

            gs = get_scadenziario()
            agenda = get_agenda()
            alerts = []
            oggi = date.today()
            domani = oggi + timedelta(days=1)

            scadute = [
                s
                for s in gs.imminenti(entro_giorni=0)
                if s.giorni_alla_scadenza is not None and s.giorni_alla_scadenza < 0
            ]
            if scadute:
                alerts.append(
                    {
                        "id": f"scad-scadute-{oggi.isoformat()}",
                        "tipo": "danger",
                        "icona": "alarm-fill",
                        "titolo": f"{len(scadute)} scadenza/e SCADUTA/E",
                        "corpo": " • ".join(s.titolo for s in scadute[:3]),
                        "url": "/scadenziario",
                        "ts": oggi.isoformat(),
                        "priorita": 1,
                    }
                )

            sc_oggi = [s for s in gs.imminenti(entro_giorni=1) if s.giorni_alla_scadenza == 0]
            if sc_oggi:
                alerts.append(
                    {
                        "id": f"scad-oggi-{oggi.isoformat()}",
                        "tipo": "danger",
                        "icona": "exclamation-circle-fill",
                        "titolo": f"{len(sc_oggi)} scadenza/e OGGI",
                        "corpo": " • ".join(s.titolo for s in sc_oggi[:3]),
                        "url": "/scadenziario",
                        "ts": oggi.isoformat(),
                        "priorita": 2,
                    }
                )

            imminenti = [
                s
                for s in gs.imminenti(entro_giorni=3)
                if s.perentorio and (s.giorni_alla_scadenza or 0) > 0
            ]
            if imminenti:
                alerts.append(
                    {
                        "id": f"scad-perent-{oggi.isoformat()}",
                        "tipo": "warning",
                        "icona": "clock-history",
                        "titolo": f"{len(imminenti)} termine/i perentorio/i (entro 3 gg)",
                        "corpo": " • ".join(
                            f"{s.titolo} ({s.giorni_alla_scadenza}gg)" for s in imminenti[:3]
                        ),
                        "url": "/scadenziario",
                        "ts": oggi.isoformat(),
                        "priorita": 3,
                    }
                )

            app_oggi = sorted(
                [a for a in agenda.tutti() if a.data_ora_dt.date() == oggi],
                key=lambda a: a.data_ora,
            )
            if app_oggi:
                alerts.append(
                    {
                        "id": f"app-oggi-{oggi.isoformat()}",
                        "tipo": "primary",
                        "icona": "calendar-check-fill",
                        "titolo": f"{len(app_oggi)} appuntamento/i oggi",
                        "corpo": " • ".join(
                            f"{a.titolo} {a.data_ora_dt.strftime('%H:%M')}" for a in app_oggi[:3]
                        ),
                        "url": "/agenda",
                        "ts": oggi.isoformat(),
                        "priorita": 4,
                    }
                )

            app_domani = sorted(
                [a for a in agenda.tutti() if a.data_ora_dt.date() == domani],
                key=lambda a: a.data_ora,
            )
            if app_domani:
                alerts.append(
                    {
                        "id": f"app-domani-{domani.isoformat()}",
                        "tipo": "info",
                        "icona": "calendar-event",
                        "titolo": f"{len(app_domani)} appuntamento/i domani",
                        "corpo": " • ".join(
                            f"{a.titolo} {a.data_ora_dt.strftime('%H:%M')}" for a in app_domani[:3]
                        ),
                        "url": "/agenda",
                        "ts": domani.isoformat(),
                        "priorita": 5,
                    }
                )

            alerts.sort(key=lambda x: x["priorita"])
            return jsonify(alerts)
        except Exception as e:
            app.logger.exception("Errore notifiche_inbox: %s", e)
            return jsonify([])
    @app.route("/scadenziario/<id_sc>/elimina", methods=["POST"])
    def elimina_scadenza(id_sc):
        gs = get_scadenziario()
        next_url = str(request.form.get("next") or "").strip()
        try:
            gs.elimina(id_sc)
            audit("scadenziario.elimina", "scadenza", id_sc)
            flash("Scadenza eliminata.", "success")
            sync_pubblica("elimina", "scadenze", id_sc)
        except ValueError as e:
            flash(str(e), "danger")
        if next_url:
            return redirect(next_url)
        return redirect(url_for("scadenziario"))
    @app.route("/scadenziario/calcola-termine", methods=["POST"])
    def calcola_termine_route():
        data = request.get_json() or {}
        try:
            if data.get("preset") or data.get("deadline_profile_code"):
                calc = _calcola_scadenza_form_payload(data)
                return jsonify(
                    {
                        "data_scadenza": calc["result"].legal_due_at[:10],
                        "raw_due_at": calc["result"].raw_due_at,
                        "legal_due_at": calc["result"].legal_due_at,
                        "operational_due_at": calc["result"].operational_due_at,
                        "office_mode_on_legal_due_date": calc["result"].office_mode_on_legal_due_date,
                        "trace": calc["result"].trace,
                        "operational_notes": riepilogo_operativo_scadenza(
                            trace=calc["result"].trace,
                            operational_due_at=calc["result"].operational_due_at,
                            operational_lead_business_days=calc["operational_lead_business_days"],
                            october_observance_blocks=calc["october_observance_blocks"],
                            office_patron_day=calc["judicial_office_patron_day"],
                            office_patron_month=calc["judicial_office_patron_month"],
                            office_operating_mode=calc["judicial_office_operating_mode"],
                        ),
                        "judicial_office_name": calc["judicial_office_name"],
                        "profile_code": calc["profile"].code,
                        "profile_label": calc["profile"].label,
                    }
                )
            d_inizio = date.fromisoformat(data["data_inizio"])
            d_scadenza = calcola_termine(
                d_inizio,
                giorni=int(data.get("giorni", 0)),
                tipo=data.get("tipo", "liberi"),
                sospensione_feriale=data.get("sospensione_feriale", True),
                mesi=int(data.get("mesi", 0)),
                anni=int(data.get("anni", 0)),
            )
            return jsonify(
                {
                    "data_scadenza": d_scadenza.isoformat(),
                    "lavorativo": è_giorno_lavorativo(d_scadenza),
                }
            )
        except (KeyError, ValueError) as e:
            return jsonify({"errore": str(e)}), 400
    @app.route("/api/scadenziario/imminenti")
    def api_scadenze_imminenti():
        try:
            giorni = int(request.args.get("giorni", 7))
            gs = get_scadenziario()
            scadenze = gs.imminenti(entro_giorni=giorni)
            return jsonify([s.to_dict() for s in scadenze])
        except Exception as e:
            app.logger.exception("Errore api_scadenze_imminenti: %s", e)
            return jsonify([])
    @app.route("/api/scadenziario/statistiche")
    def api_scadenziario_statistiche():
        try:
            return jsonify(get_scadenziario().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_scadenziario_statistiche: %s", e)
            return jsonify({"errore": str(e)})
