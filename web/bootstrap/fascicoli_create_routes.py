"""Fascicolo creation routes extracted from the core fascicoli bootstrap."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
import os
from pathlib import Path
from typing import Any

from flask import Flask, current_app, flash, jsonify, redirect, render_template, request, url_for

from pct.clienti import Recapiti
from pct.fascicoli import StatoFascicolo, TipoDocumento, TipoFascicolo
from pct.guida_pratica import GuidaPraticaError, get_guida_pratica_service, normalize_codice_materia
from pct.pratiche_collegate_catalog import (
    codice_oggetto_pst_entry,
    looks_like_codice_oggetto_pst,
    resolve_codice_oggetto_pst_payload,
)
from pct.soggetti import RuoloSoggetto, TipoSoggetto
from pct.uffici_giudiziari import risolvi_ufficio
from web.blueprints.react_shell import render_react_shell_response


def _richiede_vista_classica() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def register_fascicoli_create_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    get_preventivi: Callable[[], Any],
    get_config_studio: Callable[[], Any],
    sync_pubblica: Callable[..., None],
    fascicolo_form_correction_context: Callable[[], dict[str, Any]],
) -> None:
    """Register the fascicolo creation workflow routes."""

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

    def _codice_oggetto_da_workflow(form: Any, gestore_preventivi: Any) -> str:
        source_conferimento = str(form.get("source_conferimento", "") or "").strip()
        if source_conferimento:
            try:
                conferimento = gestore_preventivi.get_conferimento(source_conferimento)
            except Exception:
                conferimento = None
            if conferimento:
                codice = str(getattr(conferimento, "codice_oggetto_pst", "") or "").strip()
                if codice:
                    return codice
                id_preventivo = str(getattr(conferimento, "id_preventivo", "") or "").strip()
                if id_preventivo:
                    try:
                        preventivo = gestore_preventivi.get_preventivo(id_preventivo)
                    except Exception:
                        preventivo = None
                    codice = str(getattr(preventivo, "codice_oggetto_pst", "") or "").strip() if preventivo else ""
                    if codice:
                        return codice

        source_preventivo = str(form.get("source_preventivo", "") or "").strip()
        if source_preventivo:
            try:
                preventivo = gestore_preventivi.get_preventivo(source_preventivo)
            except Exception:
                preventivo = None
            codice = str(getattr(preventivo, "codice_oggetto_pst", "") or "").strip() if preventivo else ""
            if codice:
                return codice
        return ""

    def _codice_oggetto_pst_da_form(form: Any, *, oggetto: str, gestore_preventivi: Any) -> dict[str, str]:
        explicit = str(form.get("codice_oggetto_pst", "") or "").strip()
        workflow = _codice_oggetto_da_workflow(form, gestore_preventivi)
        oggetto_candidate = str(oggetto or "").strip()
        candidate = explicit or workflow or (oggetto_candidate if looks_like_codice_oggetto_pst(oggetto_candidate) else "")
        if not candidate:
            return {
                "codice_oggetto_pst": "",
                "fonte_codice_oggetto": str(form.get("fonte_codice_oggetto", "") or "").strip(),
                "file_fonte_codice_oggetto": str(form.get("file_fonte_codice_oggetto", "") or "").strip(),
                "descrizione": "",
            }
        entry = codice_oggetto_pst_entry(candidate)
        if not entry:
            raise ValueError("Codice oggetto PST non valido. Scegli una voce del catalogo ufficiale.")
        resolved = resolve_codice_oggetto_pst_payload(candidate)
        return {
            "codice_oggetto_pst": resolved["codice_oggetto_pst"],
            "fonte_codice_oggetto": str(form.get("fonte_codice_oggetto", "") or resolved["fonte_codice_oggetto"]).strip(),
            "file_fonte_codice_oggetto": str(form.get("file_fonte_codice_oggetto", "") or resolved["file_fonte_codice_oggetto"]).strip(),
            "descrizione": str(entry.get("descrizione", "") or "").strip(),
        }

    def _codice_guida_pratica_da_form(form: Any, *, codice_oggetto_pst: str, context: dict[str, Any]) -> str:
        explicit = normalize_codice_materia(form.get("codice_guida_pratica", ""))
        if explicit:
            try:
                get_guida_pratica_service().get_guidance(explicit, fascicolo=context)
            except GuidaPraticaError as exc:
                raise ValueError("Codice Guida Pratica non valido. Scegli una scheda esistente.") from exc
            return explicit
        if codice_oggetto_pst:
            return ""
        try:
            match = get_guida_pratica_service().suggest_guidance_from_fascicolo(context)
        except Exception:
            return ""
        return normalize_codice_materia(match.get("codice")) if match else ""

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
                codice_oggetto = _codice_oggetto_pst_da_form(
                    form,
                    oggetto=oggetto,
                    gestore_preventivi=gestore_preventivi,
                )
                if codice_oggetto["codice_oggetto_pst"] and oggetto == codice_oggetto["codice_oggetto_pst"]:
                    oggetto = codice_oggetto["descrizione"] or oggetto
                codice_guida_pratica = _codice_guida_pratica_da_form(
                    form,
                    codice_oggetto_pst=codice_oggetto["codice_oggetto_pst"],
                    context={
                        "titolo": titolo,
                        "oggetto": oggetto,
                        "tipo": tipo_valore,
                        "tipo_procedimento": form.get("tipo_procedimento", ""),
                        "area_pratica": form.get("area_pratica", ""),
                        "procedura_operativa_nome": form.get("procedura_operativa_nome", ""),
                    },
                )
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
                    codice_oggetto_pst=codice_oggetto["codice_oggetto_pst"],
                    codice_guida_pratica=codice_guida_pratica,
                    fonte_codice_oggetto=codice_oggetto["fonte_codice_oggetto"],
                    file_fonte_codice_oggetto=codice_oggetto["file_fonte_codice_oggetto"],
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
                target = url_for("dettaglio_fascicolo", id_fasc=fascicolo.id)
                return _risposta_successo_form(messaggio_creazione, target, id_fascicolo=fascicolo.id)
            except (ValueError, KeyError) as exc:
                current_app.logger.warning(
                    "Creazione fascicolo non riuscita (%s): %s", type(exc).__name__, exc
                )
                # I ValueError di questo flusso portano messaggi di validazione
                # curati in italiano (campi mancanti, codici non validi): vanno
                # mostrati all'avvocato, non sostituiti dal testo generico.
                dettaglio = str(exc).strip() if isinstance(exc, ValueError) else ""
                failure = _risposta_errore_form(
                    dettaglio
                    or "Non è stato possibile creare il fascicolo: controlla i dati obbligatori e riprova.",
                    status=400,
                )
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
