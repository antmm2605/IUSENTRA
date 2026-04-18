"""Route dedicate al timesheet operativo."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, g, redirect, render_template, request, url_for

from pct.economic_pipeline import build_timesheet_billing_summary, genera_parcella_da_timesheet
from pct.timesheet import StatoTimesheet


def register_timesheet_routes(
    app: Flask,
    *,
    get_timesheet: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    audit: Callable[..., None],
) -> None:
    """Registra la superficie timesheet in modo indipendente dal resto del core."""

    @app.route("/timesheet")
    def timesheet_lista():
        gestore = get_timesheet()
        id_cliente = str(request.args.get("id_cliente", "") or "").strip()
        id_fascicolo = str(request.args.get("id_fascicolo", "") or "").strip()
        filtro_stato = str(request.args.get("stato", "") or "").strip()
        filtro_utente = str(request.args.get("utente", "") or "").strip()

        entries = gestore.tutte()
        if id_cliente:
            entries = [entry for entry in entries if entry.id_cliente == id_cliente]
        if id_fascicolo:
            entries = [entry for entry in entries if entry.id_fascicolo == id_fascicolo]
        if filtro_stato:
            entries = [entry for entry in entries if entry.stato.value == filtro_stato]
        if filtro_utente:
            entries = [entry for entry in entries if (entry.username or entry.id_utente) == filtro_utente]

        clienti = get_clienti()
        fascicoli = get_fascicoli()
        cliente_corrente = clienti.get(id_cliente) if id_cliente else None
        fascicolo_corrente = fascicoli.get(id_fascicolo) if id_fascicolo else None
        utenti_disponibili = sorted({entry.username or entry.id_utente for entry in gestore.tutte() if entry.username or entry.id_utente})
        billing_summary = build_timesheet_billing_summary(entries)

        return render_template(
            "timesheet/lista.html",
            entries=entries,
            stats=gestore.statistiche(entries),
            stati=list(StatoTimesheet),
            fascicoli=fascicoli.tutti(stato=None),
            clienti=clienti.tutti(stato=None),
            id_cliente=id_cliente,
            id_fascicolo=id_fascicolo,
            filtro_stato=filtro_stato,
            filtro_utente=filtro_utente,
            utente_corrente_filtro=filtro_utente,
            utenti_disponibili=utenti_disponibili,
            cliente_corrente=cliente_corrente,
            fascicolo_corrente=fascicolo_corrente,
            billing_summary=billing_summary,
            oggi=date.today(),
        )

    @app.route("/timesheet/nuovo", methods=["POST"])
    def timesheet_nuovo():
        gestore = get_timesheet()
        id_fascicolo = str(request.form.get("id_fascicolo", "") or "").strip()
        id_cliente = str(request.form.get("id_cliente", "") or "").strip()
        from_page = str(request.form.get("from_page", "") or "").strip()
        focus = str(request.form.get("focus", "") or "").strip()
        utente = g.utente_corrente
        fascicolo = get_fascicoli().get(id_fascicolo) if id_fascicolo else None
        if fascicolo and not id_cliente:
            id_cliente = fascicolo.id_cliente or ""
        try:
            voce = gestore.crea(
                descrizione=request.form.get("descrizione", ""),
                minuti=int(request.form.get("minuti", 0) or 0),
                id_fascicolo=id_fascicolo,
                id_cliente=id_cliente,
                id_utente=getattr(utente, "id", ""),
                username=getattr(utente, "username", ""),
                data_attivita=request.form.get("data_attivita", ""),
                valore_unitario=float(request.form.get("valore_unitario", 0.0) or 0.0),
                fatturabile=request.form.get("fatturabile", "1") == "1",
                origine="manuale-ui",
                note=request.form.get("note", ""),
                dati_json={"contesto": request.form.get("contesto", "")},
            )
            audit(
                "timesheet.crea",
                "timesheet",
                voce.id,
                dettagli=f"fascicolo={id_fascicolo or '-'} cliente={id_cliente or '-'}",
            )
            flash("Tempo registrato correttamente.", "success")
        except Exception as exc:
            flash(str(exc), "danger")

        if from_page == "cliente" and id_cliente:
            return redirect(url_for("cartella_cliente", id_cliente=id_cliente, _anchor=focus or "sezione-workflow-cliente"))
        if from_page == "fascicolo" and id_fascicolo:
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fascicolo, focus=focus or "workflow"))
        return redirect(url_for("timesheet_lista", id_cliente=id_cliente, id_fascicolo=id_fascicolo))

    @app.route("/timesheet/<id_entry>/stato", methods=["POST"])
    def timesheet_cambia_stato(id_entry: str):
        gestore = get_timesheet()
        from_page = str(request.form.get("from_page", "") or "").strip()
        id_cliente = str(request.form.get("id_cliente", "") or "").strip()
        id_fascicolo = str(request.form.get("id_fascicolo", "") or "").strip()
        try:
            nuovo_stato = StatoTimesheet(request.form.get("stato", StatoTimesheet.VALIDATO.value))
            gestore.cambia_stato(id_entry, nuovo_stato)
            audit("timesheet.stato", "timesheet", id_entry, dettagli=nuovo_stato.value)
            flash("Stato timesheet aggiornato.", "success")
        except Exception as exc:
            flash(str(exc), "danger")

        if from_page == "cliente" and id_cliente:
            return redirect(url_for("cartella_cliente", id_cliente=id_cliente, _anchor="sezione-workflow-cliente"))
        if from_page == "fascicolo" and id_fascicolo:
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fascicolo, focus="workflow"))
        return redirect(url_for("timesheet_lista", id_cliente=id_cliente, id_fascicolo=id_fascicolo))

    @app.route("/timesheet/genera-parcella", methods=["POST"])
    def timesheet_genera_parcella():
        gestore = get_timesheet()
        gestore_fatturazione = get_fatturazione()
        id_cliente = str(request.form.get("id_cliente", "") or "").strip()
        id_fascicolo = str(request.form.get("id_fascicolo", "") or "").strip()
        try:
            payload = genera_parcella_da_timesheet(
                timesheet=gestore,
                fatturazione=gestore_fatturazione,
                creato_da=getattr(g.get("utente_corrente"), "username", ""),
                entry_ids=request.form.getlist("entry_ids"),
                data_scadenza=str(request.form.get("data_scadenza", "") or "").strip() or None,
            )
            parcella = payload["parcella"]
            audit(
                "timesheet.parcella",
                "parcella",
                parcella.id,
                dettagli=f"origine=timesheet voci={len(payload['entries'])}",
            )
            flash(
                f"Parcella {parcella.numero} generata da {len(payload['entries'])} voci timesheet validate.",
                "success",
            )
            return redirect(url_for("fatturazione.dettaglio", id_parcella=parcella.id))
        except Exception as exc:
            flash(str(exc), "danger")
            return redirect(url_for("timesheet_lista", id_cliente=id_cliente, id_fascicolo=id_fascicolo))
