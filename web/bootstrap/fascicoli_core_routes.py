"""Core fascicoli routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
import re
from typing import Any

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from pct.document_management import build_document_management_summary
from pct.economic_dashboard import build_fascicolo_economic_dashboard
from pct.fascicoli import EsitoAttivita, StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.reginde import ClientReGINde
from pct.soggetti import RuoloSoggetto
from pct.workflow_pipeline import build_fascicolo_workflow_pipeline
from web.blueprints.react_shell import render_react_shell_response
from web.bootstrap.fascicoli_create_routes import register_fascicoli_create_routes
from web.services.telematico_document_catalog import sync_official_catalog_on_fascicolo


def _richiede_vista_classica() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


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
        if not _richiede_vista_classica():
            return render_react_shell_response(f"fascicoli/{id_fasc}")

        from pct.checklist_atti import TUTTI_I_TEMPLATE

        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))
        catalog_sync_report = sync_official_catalog_on_fascicolo(
            gestore_fascicoli=gestore_fascicoli,
            repo_telematico=get_telematico(),
            id_fasc=id_fasc,
        )
        repair_report = gestore_fascicoli.riconcilia_documenti_portale(id_fasc)
        if catalog_sync_report.get("depositi_allineati") or repair_report.get("documenti_allineati"):
            fascicolo = gestore_fascicoli.get(id_fasc)

        cliente = get_clienti().get(fascicolo.id_cliente) if fascicolo.id_cliente else None
        gestore_preventivi = get_preventivi()
        preventivi_fascicolo = gestore_preventivi.preventivi_per_fascicolo(id_fasc)
        conferimenti_fascicolo = gestore_preventivi.conferimenti_per_fascicolo(id_fasc)
        preventivo = preventivi_fascicolo[0] if preventivi_fascicolo else None
        conferimento = conferimenti_fascicolo[0] if conferimenti_fascicolo else None
        agenda = get_agenda()
        scadenziario = get_scadenziario()
        timesheet = get_timesheet()
        appuntamenti = agenda.cerca(testo=fascicolo.numero_rg) if fascicolo.numero_rg else []
        scadenze_fascicolo = scadenziario.tutte(id_fascicolo=id_fasc, solo_aperte=False)
        timesheet_entries = timesheet.per_fascicolo(id_fasc)
        track_recente(
            "fascicolo",
            id_fasc,
            f"{fascicolo.numero} - {fascicolo.titolo}",
            url_for("dettaglio_fascicolo", id_fasc=id_fasc),
            "bi-folder2-open",
        )
        pec_tribunale = ""
        if fascicolo.tribunale:
            ufficio = ClientReGINde().cerca_ufficio_giudiziario(fascicolo.tribunale)
            pec_tribunale = ufficio.pec if ufficio else ""
        parti = get_soggetti().parti_fascicolo(id_fasc)
        pst_import_dir = pst_import_dir_for_fascicolo(fascicolo)
        pst_import_dir.mkdir(parents=True, exist_ok=True)
        pst_import_pending = pst_import_pending_count(fascicolo)
        ha_documenti_portale = any(
            getattr(deposito, "documenti_portale", None) for deposito in (fascicolo.depositi_pct or [])
        )
        if ha_documenti_portale:
            portale_documenti_catalogo = catalogo_documenti_portale_fascicolo(fascicolo)
        else:
            portale_documenti_catalogo = []
        portale_documenti_per_deposito = gruppa_catalogo_documenti_portale(portale_documenti_catalogo)
        polisweb_importato = "Importato da PolisWeb" in (fascicolo.note or "")
        ha_udienza_importata = any(
            getattr(attivita.tipo, "value", attivita.tipo) == "UDIENZA"
            for attivita in (fascicolo.attivita or [])
        )
        ha_metadati_portale = any(
            getattr(deposito, "documenti_portale", None) for deposito in (fascicolo.depositi_pct or [])
        )
        polisweb_sync_needed = polisweb_importato and (
            not fascicolo.id_cliente
            or not parti
            or not fascicolo.attivita
            or not fascicolo.tribunale
            or not fascicolo.data_apertura
            or (ha_udienza_importata and not fascicolo.data_prima_udienza)
            or not ha_metadati_portale
        )
        responsabile_conformita = build_responsabile_conformita_fascicolo(
            fascicolo=fascicolo,
            cliente=cliente,
            preventivo=preventivo,
            conferimento=conferimento,
            parti=parti,
        )
        cfg_firma = get_config_studio().config.firma
        open_pst_nav = request.args.get("open_pst_nav") == "1"
        auto_pst_acquire = request.args.get("auto_pst_acquire") == "1"
        preserve_pst_tree = request.args.get("preserve_pst_tree") == "1"
        workspace_fascicolo = build_fascicolo_workspace(
            fascicolo,
            apps=appuntamenti,
            scadenze=scadenze_fascicolo,
        )
        intelligenza_fascicolo = get_workspace_intelligente().per_fascicolo(
            fascicolo,
            apps=appuntamenti,
            scadenze=scadenze_fascicolo,
        )
        parcelle_fascicolo = get_fatturazione().per_fascicolo(id_fasc)
        fascicolo_pipeline = build_fascicolo_workflow_pipeline(
            fascicolo=fascicolo,
            cliente=cliente,
            preventivo=preventivo,
            conferimento=conferimento,
            parcelle=parcelle_fascicolo,
            timesheet_entries=timesheet_entries,
        )
        economic_dashboard = build_fascicolo_economic_dashboard(
            fascicolo=fascicolo,
            parcelle=parcelle_fascicolo,
            timesheet_entries=timesheet_entries,
            preventivo=preventivo,
            conferimento=conferimento,
        )
        document_management = build_document_management_summary(
            fascicolo,
            indice=get_indice(),
            query=request.args.get("q_doc", ""),
        )
        return render_template(
            "fascicoli/dettaglio.html",
            fascicolo=fascicolo,
            cliente=cliente,
            preventivo=preventivo,
            conferimento=conferimento,
            apps=appuntamenti,
            scadenze_fascicolo=scadenze_fascicolo,
            workspace_fascicolo=workspace_fascicolo,
            intelligenza_fascicolo=intelligenza_fascicolo,
            fascicolo_pipeline=fascicolo_pipeline,
            economic_dashboard=economic_dashboard,
            document_management=document_management,
            timesheet_entries=timesheet_entries,
            tipi_doc=list(TipoDocumento),
            tipi_att=list(TipoAttivita),
            esiti=list(EsitoAttivita),
            pec_tribunale=pec_tribunale,
            checklist_templates=TUTTI_I_TEMPLATE,
            parti=parti,
            RuoloSoggetto=RuoloSoggetto,
            pst_import_pending=pst_import_pending,
            pst_portale_label=portale_ufficiale_label(fascicolo),
            pst_import_dir=str(pst_import_dir),
            portale_documenti_catalogo=portale_documenti_catalogo,
            portale_documenti_per_deposito=portale_documenti_per_deposito,
            polisweb_sync_needed=polisweb_sync_needed,
            responsabile_conformita=responsabile_conformita,
            pdp_penale_summary=pdp_penale_summary_for_fascicolo(fascicolo),
            cfg_firma=cfg_firma,
            firma_visibile_place=luogo_timbro_firma_visibile(),
            firma_visibile_mode=getattr(cfg_firma, "visible_signature_mode", "laterale"),
            open_pst_nav=open_pst_nav,
            auto_pst_acquire=auto_pst_acquire,
            preserve_pst_tree=preserve_pst_tree,
            oggi=date.today(),
        )

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
