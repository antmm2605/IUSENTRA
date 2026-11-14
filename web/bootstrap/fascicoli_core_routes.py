"""Core fascicoli routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any

from flask import Flask, flash, redirect, request, url_for

from pct.fascicoli import EsitoAttivita, TipoAttivita
from web.blueprints.react_shell import render_react_shell_response
from web.bootstrap.fascicoli_create_routes import register_fascicoli_create_routes


def _attivita_derivata_da_documento(attivita: Any) -> bool:
    """Impedisce di alterare dal pannello generico una rilevazione automatica."""

    context = "\n".join(
        str(getattr(attivita, field, "") or "")
        for field in ("note", "descrizione", "remote_hearing_source")
    )
    title = re.sub(r"\s+", " ", str(getattr(attivita, "titolo", "") or "")).strip().lower()
    return title in {"udienza rilevata", "termine rilevato"} or bool(
        re.search(r"\b(?:PEC_DOCUMENT_PRESIDIO|PEC_AUDIT):docpresidio:", context, re.IGNORECASE)
    )


def register_fascicoli_core_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    get_timesheet: Callable[[], Any],
    get_preventivi: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_telematico: Callable[[], Any],
    get_indice: Callable[[], Any],
    get_workspace_intelligente: Callable[[], Any],
    get_config_studio: Callable[[], Any],
    sync_pubblica: Callable[..., None],
    track_recente: Callable[..., None],
    build_responsabile_conformita_fascicolo: Callable[..., Any],
    build_fascicolo_workspace: Callable[..., Any],
    fascicolo_form_correction_context: Callable[[], dict[str, Any]],
    pst_import_dir_for_fascicolo: Callable[..., Any],
    pst_import_pending_count: Callable[..., int],
    catalogo_documenti_portale_fascicolo: Callable[..., list[dict[str, Any]]],
    gruppa_catalogo_documenti_portale: Callable[..., dict[str, list[dict[str, Any]]]],
    portale_ufficiale_label: Callable[..., str],
    pdp_penale_summary_for_fascicolo: Callable[..., dict[str, Any]],
    luogo_timbro_firma_visibile: Callable[[], str],
) -> None:
    """Register the remaining core fascicoli routes."""

    def _redirect_to_fascicolo_section(id_fasc: str, default_section: str = "sezione-attivita-processuali"):
        section = str(request.form.get("next_section") or default_section).strip().lstrip("#")
        if not section.startswith("sezione-"):
            section = default_section
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc) + f"#{section}")

    register_fascicoli_create_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi,
        get_config_studio=get_config_studio,
        sync_pubblica=sync_pubblica,
        fascicolo_form_correction_context=fascicolo_form_correction_context,
    )
    @app.route("/fascicoli/<id_fasc>")
    def dettaglio_fascicolo(id_fasc: str):
        return render_react_shell_response(f"fascicoli/{id_fasc}")

    @app.route("/fascicoli/<id_fasc>/attivita/aggiungi", methods=["POST"])
    def aggiungi_attivita(id_fasc: str):
        form = request.form
        try:
            get_fascicoli().aggiungi_attivita(
                id_fasc,
                tipo=TipoAttivita(form["tipo"]),
                data=form["data"],
                titolo=form["titolo"],
                descrizione=form.get("descrizione", ""),
                luogo=form.get("luogo", ""),
                esito=EsitoAttivita(form.get("esito", "IN_ATTESA")),
                note=form.get("note", ""),
                avvocato=form.get("avvocato", ""),
                id_appuntamento=form.get("id_appuntamento", ""),
            )
            flash("Attivita' aggiunta.", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        return _redirect_to_fascicolo_section(id_fasc)

    @app.route("/fascicoli/<id_fasc>/attivita/<id_att>/esito", methods=["POST"])
    def aggiorna_esito_attivita(id_fasc: str, id_att: str):
        try:
            fascicolo = get_fascicoli().get(id_fasc)
            attivita = next((item for item in getattr(fascicolo, "attivita", []) if item.id == id_att), None)
            if _attivita_derivata_da_documento(attivita):
                raise ValueError("L'attività è una rilevazione documentale: consulta la fonte senza alterarne lo stato.")
            get_fascicoli().aggiorna_attivita(
                id_fasc,
                id_att,
                esito=EsitoAttivita(request.form["esito"]),
                note=request.form.get("note", ""),
            )
            flash("Esito aggiornato.", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        return _redirect_to_fascicolo_section(id_fasc)

    @app.route("/fascicoli/<id_fasc>/attivita/<id_att>/elimina", methods=["POST"])
    def elimina_attivita_fascicolo(id_fasc: str, id_att: str):
        try:
            fascicolo = get_fascicoli().get(id_fasc)
            attivita = next((item for item in getattr(fascicolo, "attivita", []) if item.id == id_att), None)
            if _attivita_derivata_da_documento(attivita):
                raise ValueError("L'attività è una rilevazione documentale: la fonte e l'evento restano nel fascicolo.")
            get_fascicoli().rimuovi_attivita(id_fasc, id_att)
            flash("Attivita' rimossa dal fascicolo.", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        return _redirect_to_fascicolo_section(id_fasc)
