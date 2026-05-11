"""Core fascicoli routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
import os
from pathlib import Path
from typing import Any

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from pct.clienti import Recapiti
from pct.document_management import build_document_management_summary
from pct.economic_dashboard import build_fascicolo_economic_dashboard
from pct.fascicoli import EsitoAttivita, StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.reginde import ClientReGINde
from pct.soggetti import RuoloSoggetto, TipoSoggetto
from pct.uffici_giudiziari import risolvi_ufficio
from pct.workflow_pipeline import build_fascicolo_workflow_pipeline
from web.blueprints.react_shell import render_react_shell_response
from web.services.telematico_document_catalog import sync_official_catalog_on_fascicolo


def _richiede_vista_classica() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


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

    def _avvocato_titolare_studio() -> str:
        try:
            config_manager = get_config_studio()
            studio = getattr(getattr(config_manager, "config", None), "studio", None)
            avvocato = str(getattr(studio, "avvocato", "") or "").strip()
            if avvocato:
                return avvocato
        except Exception:
            pass
        return str(
            app.config.get("STUDIO_AVVOCATO")
            or app.config.get("PCT_STUDIO_AVVOCATO")
            or ""
        ).strip()

    def _tipo_documento_upload_iniziale(nome_file: str, *, email: bool = False) -> TipoDocumento:
        if email:
            return TipoDocumento.COMUNICAZIONE
        nome = Path(nome_file or "").name.lower()
        if "procura" in nome:
            return TipoDocumento.PROCURA
        if "ricorso" in nome:
            return TipoDocumento.RICORSO
        if "citazione" in nome:
            return TipoDocumento.CITAZIONE
        if "comparsa" in nome:
            return TipoDocumento.COMPARSA
        if "memoria" in nome:
            return TipoDocumento.MEMORIA
        if "notifica" in nome or "relata" in nome:
            return TipoDocumento.NOTIFICA
        if nome.endswith((".eml", ".msg")) or "ricevuta" in nome:
            return TipoDocumento.COMUNICAZIONE
        if nome.endswith((".pdf", ".p7m")):
            return TipoDocumento.ATTO_GIUDIZIARIO
        return TipoDocumento.ALLEGATO

    def _salva_upload_fascicolo_veloce(gestore_fascicoli: Any, id_fasc: str) -> tuple[int, int, int]:
        documenti_caricati = 0
        email_caricate = 0
        email_scartate = 0

        for storage in request.files.getlist("documenti_fascicolo"):
            if not storage or not storage.filename:
                continue
            raw = storage.read()
            if not raw:
                continue
            gestore_fascicoli.aggiungi_documento(
                id_fasc,
                Path(storage.filename).name,
                _tipo_documento_upload_iniziale(storage.filename),
                raw,
                note="Caricato all'apertura con Fascicolo Veloce.",
                tags=["fascicolo-veloce", "documenti-iniziali"],
                fonte_documento="APERTURA_FASCICOLO_VELOCE",
                nome_originale=storage.filename,
            )
            documenti_caricati += 1

        for storage in request.files.getlist("email_fascicolo"):
            if not storage or not storage.filename:
                continue
            if not Path(storage.filename).name.lower().endswith(".eml"):
                email_scartate += 1
                continue
            raw = storage.read()
            if not raw:
                continue
            gestore_fascicoli.aggiungi_documento(
                id_fasc,
                Path(storage.filename).name,
                _tipo_documento_upload_iniziale(storage.filename, email=True),
                raw,
                note="Email EML caricata all'apertura con Fascicolo Veloce.",
                tags=["fascicolo-veloce", "email-iniziali", "eml"],
                fonte_documento="APERTURA_FASCICOLO_VELOCE",
                nome_originale=storage.filename,
            )
            email_caricate += 1

        return documenti_caricati, email_caricate, email_scartate

    def _richiede_json_form() -> bool:
        return (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in (request.headers.get("Accept") or "")
        )

    def _risposta_errore_form(messaggio: str, *, status: int = 400):
        if _richiede_json_form():
            return jsonify({"ok": False, "message": messaggio, "errore": messaggio}), status
        flash(messaggio, "danger")
        return None

    def _risposta_successo_form(messaggio: str, target: str, *, id_fascicolo: str):
        if _richiede_json_form():
            return jsonify(
                {
                    "ok": True,
                    "message": messaggio,
                    "redirect": target,
                    "redirect_url": target,
                    "id": id_fascicolo,
                }
            )
        flash(messaggio, "success")
        return redirect(target)

    def _form_bool(form: Any, name: str) -> bool:
        return form.get(name) in {"1", "true", "on", "si", "sì", "SI", "Si"}

    def _split_nome_persona(nome_completo: str) -> tuple[str, str]:
        parti = [parte for parte in str(nome_completo or "").strip().split() if parte]
        if not parti:
            return "", ""
        if len(parti) == 1:
            return parti[0], ""
        return parti[0], " ".join(parti[1:])

    def _tipo_soggetto_da_form(valore: str) -> TipoSoggetto:
        try:
            return TipoSoggetto(str(valore or "").strip() or "PERSONA_GIURIDICA")
        except ValueError:
            return TipoSoggetto.PERSONA_GIURIDICA

    def _uffici_cache_path() -> str:
        configured = str(os.getenv("PCT_UFFICI_DB", "") or "").strip()
        if configured:
            return configured
        repo_data = Path(__file__).resolve().parents[2] / "data" / "uffici" / "uffici_giudiziari.json"
        if repo_data.exists():
            return str(repo_data)
        return "/data/uffici/uffici_giudiziari.json"

    def _soggetto_esistente_per_identificativo(gestore_soggetti: Any, identificativo: str):
        valore = str(identificativo or "").strip().casefold()
        if not valore:
            return None
        for soggetto in gestore_soggetti.cerca(q=identificativo):
            if str(getattr(soggetto, "identificativo", "") or "").strip().casefold() == valore:
                return soggetto
        return None

    def _crea_o_riusa_controparte(gestore_soggetti: Any, form: Any, *, nome_base: str, identificativo_base: str):
        id_soggetto = str(form.get("id_soggetto_controparte", "") or "").strip()
        if id_soggetto:
            soggetto = gestore_soggetti.get(id_soggetto)
            if not soggetto:
                raise ValueError("La controparte selezionata non è più disponibile. Scegli un soggetto valido o inserisci i dati manualmente.")
            return soggetto

        nome_completo = str(form.get("nuovo_soggetto_nome_completo", "") or "").strip() or nome_base
        identificativo = str(form.get("nuovo_soggetto_identificativo", "") or "").strip() or identificativo_base
        if not nome_completo or not identificativo:
            return None

        esistente = _soggetto_esistente_per_identificativo(gestore_soggetti, identificativo)
        if esistente:
            return esistente

        tipo = _tipo_soggetto_da_form(form.get("nuovo_soggetto_tipo", "PERSONA_GIURIDICA"))
        recapiti = Recapiti(
            telefono=str(form.get("nuovo_soggetto_telefono", "") or "").strip(),
            email=str(form.get("nuovo_soggetto_email", "") or "").strip(),
            pec=str(form.get("nuovo_soggetto_pec", "") or "").strip(),
        )
        common = {
            "recapiti": recapiti,
            "note": "Creato durante l'apertura del fascicolo.",
            "tag": ["controparte"],
        }
        if tipo == TipoSoggetto.PERSONA_FISICA:
            nome, cognome = _split_nome_persona(nome_completo)
            return gestore_soggetti.crea(
                tipo=tipo,
                nome=nome,
                cognome=cognome,
                codice_fiscale=identificativo,
                **common,
            )
        partita_iva = identificativo if identificativo.isdigit() and len(identificativo) == 11 else ""
        return gestore_soggetti.crea(
            tipo=tipo,
            ragione_sociale=nome_completo,
            codice_fiscale="" if partita_iva else identificativo,
            partita_iva=partita_iva,
            **common,
        )

    def _risolvi_autorita_giudiziaria(valore: str, *, obbligatoria: bool) -> str:
        testo = str(valore or "").strip()
        if not testo:
            if obbligatoria:
                raise ValueError("Se usi Fascicolo Veloce devi scegliere l'autorità giudiziaria dall'elenco degli uffici.")
            return ""
        if not obbligatoria:
            return testo
        ufficio = risolvi_ufficio(testo, cache_path=_uffici_cache_path())
        if not ufficio:
            raise ValueError("Autorità giudiziaria non trovata nel registro. Cerca e seleziona una voce dell'elenco prima di creare il fascicolo veloce.")
        return str(ufficio.get("nome") or testo).strip()

    @app.route("/fascicoli")
    def lista_fascicoli():
        if not _richiede_vista_classica():
            return render_react_shell_response("fascicoli")

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
        if not _richiede_vista_classica():
            return render_react_shell_response("fascicoli/archivio")

        testo = request.args.get("q", "").strip()
        fascicoli = get_fascicoli().cerca(
            testo=testo,
            stato=StatoFascicolo.ARCHIVIATO,
            archiviati=True,
        )
        return render_template("fascicoli/archivio.html", fascicoli=fascicoli, q=testo)

    @app.route("/fascicoli/esporta")
    def esporta_fascicoli_view():
        if not _richiede_vista_classica():
            return render_react_shell_response("fascicoli/esporta")
        return redirect(url_for("lista_fascicoli"))

    @app.route("/fascicoli/nuovo", methods=["GET", "POST"])
    def nuovo_fascicolo():
        from pct.workflow_onboarding import build_fascicolo_onboarding

        gestore_clienti = get_clienti()
        gestore_fascicoli = get_fascicoli()
        gestore_preventivi = get_preventivi()
        if request.method == "GET" and not _richiede_vista_classica():
            return render_react_shell_response("fascicoli/nuovo")

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
                avvocato_referente = form.get("avvocato_referente", "").strip() or _avvocato_titolare_studio()
                fascicolo_veloce = _form_bool(form, "fascicolo_veloce")
                titolo = form.get("titolo", "").strip()
                tipo_valore = form.get("tipo", "").strip()
                oggetto = form.get("oggetto", "").strip()
                controparte = form.get("controparte", "").strip()
                cf_controparte = form.get("cf_controparte", "").strip()
                tribunale_input = form.get("tribunale", "").strip()
                gestore_soggetti = get_soggetti()
                id_soggetto_controparte = form.get("id_soggetto_controparte", "").strip()
                if id_soggetto_controparte:
                    soggetto_scelto = gestore_soggetti.get(id_soggetto_controparte)
                    if not soggetto_scelto:
                        raise ValueError("La controparte selezionata non è più disponibile. Scegli un soggetto valido o inserisci i dati manualmente.")
                    controparte = controparte or soggetto_scelto.nome_completo
                    cf_controparte = cf_controparte or soggetto_scelto.identificativo
                if _form_bool(form, "crea_soggetto_controparte"):
                    if not (form.get("nuovo_soggetto_nome_completo", "").strip() or controparte):
                        raise ValueError("Per creare la scheda soggetto della controparte serve il nome completo o la ragione sociale.")
                    if not (form.get("nuovo_soggetto_identificativo", "").strip() or cf_controparte):
                        raise ValueError("Per creare la scheda soggetto della controparte serve codice fiscale o partita IVA.")
                if fascicolo_veloce:
                    mancanti = []
                    if not titolo:
                        mancanti.append("titolo")
                    if not tipo_valore:
                        mancanti.append("tipo fascicolo")
                    if not oggetto:
                        mancanti.append("oggetto")
                    if not tribunale_input:
                        mancanti.append("autorità giudiziaria")
                    if not controparte:
                        mancanti.append("controparte")
                    if not cf_controparte:
                        mancanti.append("codice fiscale o partita IVA della controparte")
                    if mancanti:
                        raise ValueError("Per creare il fascicolo veloce mancano: " + ", ".join(mancanti) + ".")
                try:
                    tipo_fascicolo = TipoFascicolo(tipo_valore)
                except ValueError as exc:
                    raise ValueError("Tipo fascicolo non valido. Scegli una voce dell'elenco.") from exc
                tribunale = _risolvi_autorita_giudiziaria(tribunale_input, obbligatoria=fascicolo_veloce)
                fascicolo = gestore_fascicoli.nuovo(
                    titolo=titolo,
                    tipo=tipo_fascicolo,
                    id_cliente=id_cliente,
                    nome_cliente=nome_cliente,
                    controparte=controparte,
                    cf_controparte=cf_controparte,
                    tribunale=tribunale,
                    numero_rg=form.get("numero_rg", ""),
                    anno_rg=int(form.get("anno_rg") or 0),
                    giudice=form.get("giudice", "") or form.get("istruttore_pm_gip", ""),
                    sezione=form.get("sezione", ""),
                    data_prima_udienza=form.get("data_prima_udienza", ""),
                    data_notifica_citazione=form.get("data_notifica_citazione", ""),
                    avvocato_referente=avvocato_referente,
                    avvocato_dominus=form.get("avvocato_dominus", ""),
                    oggetto=oggetto,
                    valore_causa=float(form.get("valore_causa") or 0),
                    valore_preventivato=float(form.get("valore_preventivato") or 0),
                    tipo_procedimento=form.get("tipo_procedimento", ""),
                    id_pratica=form.get("id_pratica", ""),
                    area_pratica=form.get("area_pratica", ""),
                    procedura_operativa_codice=form.get("procedura_operativa_codice", "").strip(),
                    codice_oggetto_pst=form.get("codice_oggetto_pst", "").strip(),
                    fonte_codice_oggetto=form.get("fonte_codice_oggetto", "").strip(),
                    file_fonte_codice_oggetto=form.get("file_fonte_codice_oggetto", "").strip(),
                    riferimento_cartaceo=form.get("riferimento_cartaceo", "").strip(),
                    attore_principale=form.get("attore_principale", "").strip(),
                    istruttore_pm_gip=form.get("istruttore_pm_gip", "").strip(),
                    cancelliere=form.get("cancelliere", "").strip(),
                    ctu=form.get("ctu", "").strip(),
                    ctp=form.get("ctp", "").strip(),
                    stato_pratica_operativa=form.get("stato_pratica_operativa", "").strip(),
                    personalizzabile=_form_bool(form, "personalizzabile"),
                    data_apertura=form.get("data_apertura", "").strip() or date.today().isoformat(),
                    data_chiusura=form.get("data_chiusura", "").strip(),
                    compenso_pattuito=float(form.get("compenso_pattuito") or 0),
                    fascicolo_veloce=fascicolo_veloce,
                    note=form.get("note", ""),
                )
                soggetto_controparte = None
                if id_soggetto_controparte or _form_bool(form, "crea_soggetto_controparte") or (controparte and cf_controparte):
                    soggetto_controparte = _crea_o_riusa_controparte(
                        gestore_soggetti,
                        form,
                        nome_base=controparte,
                        identificativo_base=cf_controparte,
                    )
                if soggetto_controparte:
                    gestore_soggetti.aggiungi_parte(
                        fascicolo.id,
                        soggetto_controparte.id,
                        RuoloSoggetto.CONTROPARTE,
                        note="Aggiunta durante l'apertura del fascicolo.",
                    )
                documenti_iniziali = 0
                email_iniziali = 0
                email_scartate = 0
                if fascicolo_veloce:
                    documenti_iniziali, email_iniziali, email_scartate = _salva_upload_fascicolo_veloce(
                        gestore_fascicoli,
                        fascicolo.id,
                    )
                    gestore_fascicoli.aggiorna(
                        fascicolo.id,
                        documenti_iniziali_count=documenti_iniziali,
                        email_iniziali_count=email_iniziali,
                    )
                    if documenti_iniziali or email_iniziali:
                        gestore_fascicoli.registra_onboarding(
                            fascicolo.id,
                            "Fascicolo Veloce: caricamento iniziale",
                            note=f"Documenti: {documenti_iniziali}; email EML: {email_iniziali}.",
                            avvocato=avvocato_referente,
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
                        avvocato=avvocato_referente,
                    )
                messaggio_creazione = f"Fascicolo {fascicolo.numero} creato."
                if fascicolo_veloce and (documenti_iniziali or email_iniziali):
                    messaggio_creazione += f" Caricati {documenti_iniziali} documenti e {email_iniziali} email EML."
                if email_scartate:
                    messaggio_creazione += f" {email_scartate} file email non EML non sono stati importati."
                sync_pubblica("crea", "fascicoli", fascicolo.id)
                if fascicolo_veloce:
                    target = url_for("deposito_prepara", id_fasc=fascicolo.id)
                    messaggio_creazione += " Si apre il deposito assistito."
                    return _risposta_successo_form(messaggio_creazione, target, id_fascicolo=fascicolo.id)
                if source_preventivo or source_conferimento:
                    target = url_for("dettaglio_fascicolo", id_fasc=fascicolo.id)
                    return _risposta_successo_form(messaggio_creazione, target, id_fascicolo=fascicolo.id)
                if id_cliente:
                    target = url_for("cartella_cliente", id_cliente=id_cliente)
                    return _risposta_successo_form(messaggio_creazione, target, id_fascicolo=fascicolo.id)
                target = url_for("dettaglio_fascicolo", id_fasc=fascicolo.id)
                return _risposta_successo_form(messaggio_creazione, target, id_fascicolo=fascicolo.id)
            except (ValueError, KeyError) as exc:
                failure = _risposta_errore_form(str(exc), status=400)
                if failure is not None:
                    return failure

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
            studio_avvocato_titolare=_avvocato_titolare_studio(),
            correction_context=fascicolo_form_correction_context(),
            oggi=date.today(),
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
            get_fascicoli().rimuovi_attivita(id_fasc, id_att)
            flash("Attivita' rimossa dal fascicolo.", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        return _redirect_to_fascicolo_section(id_fasc)
