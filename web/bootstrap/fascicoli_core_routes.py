"""Core fascicoli routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, redirect, render_template, request, url_for

from pct.document_management import build_document_management_summary
from pct.economic_dashboard import build_fascicolo_economic_dashboard
from pct.fascicoli import EsitoAttivita, StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.reginde import ClientReGINde
from pct.soggetti import RuoloSoggetto
from pct.workflow_pipeline import build_fascicolo_workflow_pipeline


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

    @app.route("/fascicoli")
    def lista_fascicoli():
        gestore_fascicoli = get_fascicoli()
        testo = request.args.get("q", "").strip()
        stato_filtro = request.args.get("stato", "")
        tipo_filtro = request.args.get("tipo", "")
        filtro_dal = request.args.get("dal", "")
        filtro_al = request.args.get("al", "")
        stato = StatoFascicolo(stato_filtro) if stato_filtro else None
        tipo = TipoFascicolo(tipo_filtro) if tipo_filtro else None
        fascicoli = (
            gestore_fascicoli.cerca(testo=testo, stato=stato, tipo=tipo)
            if testo
            else gestore_fascicoli.tutti(stato=stato, tipo=tipo)
        )
        if filtro_dal:
            fascicoli = [fasc for fasc in fascicoli if getattr(fasc, "data_apertura", "") >= filtro_dal]
        if filtro_al:
            fascicoli = [fasc for fasc in fascicoli if getattr(fasc, "data_apertura", "") <= filtro_al]
        stats = gestore_fascicoli.statistiche()
        scadenze = gestore_fascicoli.fascicoli_con_scadenze_imminenti(entro_giorni=7)
        return render_template(
            "fascicoli/lista.html",
            fascicoli=fascicoli,
            stats=stats,
            scadenze=scadenze,
            q=testo,
            stato_filtro=stato_filtro,
            tipo_filtro=tipo_filtro,
            filtro_dal=filtro_dal,
            filtro_al=filtro_al,
            tipi=list(TipoFascicolo),
            stati=list(StatoFascicolo),
        )

    @app.route("/fascicoli/archivio")
    def lista_archivio():
        testo = request.args.get("q", "").strip()
        fascicoli = get_fascicoli().cerca(
            testo=testo,
            stato=StatoFascicolo.ARCHIVIATO,
            archiviati=True,
        )
        return render_template("fascicoli/archivio.html", fascicoli=fascicoli, q=testo)

    @app.route("/fascicoli/nuovo", methods=["GET", "POST"])
    def nuovo_fascicolo():
        from pct.workflow_onboarding import build_fascicolo_onboarding

        gestore_clienti = get_clienti()
        gestore_fascicoli = get_fascicoli()
        gestore_preventivi = get_preventivi()
        if request.method == "POST":
            form = request.form
            id_cliente = form.get("id_cliente", "")
            source_preventivo = form.get("source_preventivo", "").strip()
            source_conferimento = form.get("source_conferimento", "").strip()
            nome_cliente = ""
            if id_cliente:
                cliente = gestore_clienti.get(id_cliente)
                nome_cliente = cliente.nome_completo if cliente else ""
            try:
                fascicolo = gestore_fascicoli.nuovo(
                    titolo=form["titolo"],
                    tipo=TipoFascicolo(form["tipo"]),
                    id_cliente=id_cliente,
                    nome_cliente=nome_cliente,
                    controparte=form.get("controparte", ""),
                    tribunale=form.get("tribunale", ""),
                    numero_rg=form.get("numero_rg", ""),
                    anno_rg=int(form.get("anno_rg") or 0),
                    giudice=form.get("giudice", ""),
                    sezione=form.get("sezione", ""),
                    data_prima_udienza=form.get("data_prima_udienza", ""),
                    data_notifica_citazione=form.get("data_notifica_citazione", ""),
                    avvocato_referente=form.get("avvocato_referente", ""),
                    avvocato_dominus=form.get("avvocato_dominus", ""),
                    oggetto=form.get("oggetto", ""),
                    valore_causa=float(form.get("valore_causa") or 0),
                    valore_preventivato=float(form.get("valore_preventivato") or 0),
                    tipo_procedimento=form.get("tipo_procedimento", ""),
                    id_pratica=form.get("id_pratica", ""),
                    area_pratica=form.get("area_pratica", ""),
                    compenso_pattuito=float(form.get("compenso_pattuito") or 0),
                    note=form.get("note", ""),
                )
                if source_preventivo or source_conferimento:
                    gestore_preventivi.collega_fascicolo(
                        fascicolo.id,
                        id_preventivo=source_preventivo or None,
                        id_conferimento=source_conferimento or None,
                        converti_preventivo=True,
                    )
                    onboarding_sources: list[str] = []
                    if source_preventivo:
                        preventivo_src = gestore_preventivi.get_preventivo(source_preventivo)
                        if preventivo_src:
                            onboarding_sources.append(f"Preventivo {preventivo_src.numero}")
                    if source_conferimento:
                        conferimento_src = gestore_preventivi.get_conferimento(source_conferimento)
                        if conferimento_src:
                            onboarding_sources.append(f"Conferimento {conferimento_src.numero}")
                    gestore_fascicoli.registra_onboarding(
                        fascicolo.id,
                        "Apertura guidata del fascicolo",
                        note=(
                            "Workflow origine: " + " - ".join(onboarding_sources)
                            if onboarding_sources
                            else ""
                        ),
                        avvocato=form.get("avvocato_referente", ""),
                    )
                flash(f"Fascicolo {fascicolo.numero} creato.", "success")
                sync_pubblica("crea", "fascicoli", fascicolo.id)
                if source_preventivo or source_conferimento:
                    return redirect(url_for("dettaglio_fascicolo", id_fasc=fascicolo.id))
                if id_cliente:
                    return redirect(url_for("cartella_cliente", id_cliente=id_cliente))
                return redirect(url_for("dettaglio_fascicolo", id_fasc=fascicolo.id))
            except (ValueError, KeyError) as exc:
                flash(str(exc), "danger")

        source_preventivo = request.args.get("source_preventivo", "").strip()
        source_conferimento = request.args.get("source_conferimento", "").strip()
        from_page = request.args.get("from_page", "").strip()
        id_cliente_pre = request.args.get("id_cliente", "").strip()
        preventivo_src = (
            gestore_preventivi.get_preventivo(source_preventivo) if source_preventivo else None
        )
        conferimento_src = (
            gestore_preventivi.get_conferimento(source_conferimento)
            if source_conferimento
            else None
        )
        if not id_cliente_pre:
            id_cliente_pre = (
                (conferimento_src.id_cliente if conferimento_src else "")
                or (preventivo_src.id_cliente if preventivo_src else "")
            )
        cliente_src = gestore_clienti.get(id_cliente_pre) if id_cliente_pre else None
        workflow_prefill = None
        if cliente_src and (preventivo_src or conferimento_src):
            workflow_prefill = build_fascicolo_onboarding(
                cliente=cliente_src,
                preventivo=preventivo_src,
                conferimento=conferimento_src,
            )

        return render_template(
            "fascicoli/form.html",
            fascicolo=None,
            clienti=gestore_clienti.tutti(stato=None),
            tipi=list(TipoFascicolo),
            stati=list(StatoFascicolo),
            id_cliente_pre=id_cliente_pre,
            workflow_prefill=workflow_prefill,
            source_preventivo=source_preventivo,
            source_conferimento=source_conferimento,
            from_page=from_page,
            correction_context=fascicolo_form_correction_context(),
            oggi=date.today(),
        )

    @app.route("/fascicoli/<id_fasc>")
    def dettaglio_fascicolo(id_fasc: str):
        from pct.checklist_atti import TUTTI_I_TEMPLATE

        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))

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
            flash("Attivita aggiunta.", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/attivita/<id_att>/esito", methods=["POST"])
    def aggiorna_esito_attivita(id_fasc: str, id_att: str):
        try:
            get_fascicoli().aggiorna_attivita(
                id_fasc,
                id_att,
                esito=EsitoAttivita(request.form["esito"]),
                note=request.form.get("note", ""),
            )
            flash("Esito aggiornato.", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
