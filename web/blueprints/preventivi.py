"""
web/blueprints/preventivi.py — Preventivi e conferimenti di incarico.

URL base: /preventivi/
Richiede autenticazione tramite g.utente_corrente (gestita da app.py).
"""
from __future__ import annotations

import io
import json
from html import escape
from datetime import date, timedelta

from flask import (Blueprint, abort, flash, g, redirect,
                   render_template, request, send_file, url_for, current_app)

from web.helpers import get_clienti, get_fascicoli, get_scadenziario, get_preventivi as _shared_get_preventivi
from pct.economico_context import (
    costruisci_contesto_economico,
    dump_log_calcolo,
    riepilogo_contesto_economico,
    sincronizza_contesto_economico,
)
from pct.compensi_a_tempo import (
    COMPENSO_A_TEMPO_CODE,
    calcola_compenso_a_tempo_art22bis,
    descrizione_voce_compenso_a_tempo,
    is_compenso_a_tempo,
    normalizza_tipo_compenso,
)
from pct.preventivi import (
    CLAUSOLA_CONTROVERSIE_TUTELA_CLIENTE,
    _normalizza_classificazioni_tassonomiche,
    catalogo_clausola_controversie,
    fonte_modello_clausola_controversie,
    label_modello_clausola_controversie,
    normalizza_modello_clausola_controversie,
    testo_predefinito_clausola_controversie,
)
from pct.tariffario import parse_numero_locale
from pct.workflow_commerciale import apri_fascicolo_automatico, build_workflow_summary
from web.services.mediazione_dm150_runtime import (
    calcola_mediazione_odm_da_context,
    is_mediazione_practice,
    mediazione_odm_context_for_prefill,
    parse_mediazione_odm_context,
)

preventivi = Blueprint("preventivi", __name__, url_prefix="/preventivi")


# ---------------------------------------------------------------- helpers


def _parse_numero(value, default: float = 0.0) -> float:
    return parse_numero_locale(value, default)


def _get_gp():
    return _shared_get_preventivi()


def _get_portale_mgr():
    from pct.portale import GestionePortale
    return GestionePortale(
        db_path=current_app.config.get("PORTALE_DB", "./portale/portali.json"),
        uploads_dir=current_app.config.get("PORTALE_UPLOADS", "./portale/uploads"),
    )


def _studio_forense_context() -> dict:
    """Dati dell'avvocato titolare usati per precompilare incarichi e atti."""
    dati = {
        "avvocato": current_app.config.get("STUDIO_AVVOCATO", ""),
        "numero_iscrizione_albo": current_app.config.get("STUDIO_NUMERO_ISCRIZIONE_ALBO", ""),
        "ordine_avvocati": current_app.config.get("STUDIO_ORDINE_AVVOCATI", ""),
    }
    try:
        from pct.config_studio import GestioneConfigStudio

        studio = GestioneConfigStudio(
            config_path=current_app.config.get("STUDIO_CONFIG", "./config/studio.json")
        ).config.studio
        dati["avvocato"] = getattr(studio, "avvocato", "") or dati["avvocato"]
        dati["numero_iscrizione_albo"] = (
            getattr(studio, "numero_iscrizione_albo", "") or dati["numero_iscrizione_albo"]
        )
        dati["ordine_avvocati"] = getattr(studio, "ordine_avvocati", "") or dati["ordine_avvocati"]
    except Exception:
        current_app.logger.debug("Dati forensi studio non disponibili per il prefill", exc_info=True)
    return dati


def _url_onboarding_fascicolo(id_cliente: str, *, id_preventivo: str = "", id_conferimento: str = "", from_page: str = "") -> str:
    params = {"id_cliente": id_cliente}
    if id_preventivo:
        params["source_preventivo"] = id_preventivo
    if id_conferimento:
        params["source_conferimento"] = id_conferimento
    if from_page:
        params["from_page"] = from_page
    return url_for("nuovo_fascicolo", **params)


def _url_completa_cliente(id_cliente: str, *, next_url: str = "") -> str:
    params = {}
    if next_url:
        params["next_url"] = next_url
    return url_for("modifica_cliente", id_cliente=id_cliente, **params)


def _url_nuovo_conferimento_preventivo(id_preventivo: str, id_cliente: str = "") -> str:
    params = {"id_preventivo": id_preventivo, "from_page": "preventivo"}
    if id_cliente:
        return url_for("preventivi.nuovo_conferimento", id_cliente=id_cliente, **params)
    return url_for("preventivi.nuovo_conferimento", **params)


def _cliente_da_completare(cliente) -> bool:
    return bool(cliente and not getattr(cliente, "profilo_completo_per_conferimento", True))


def _campi_cliente_mancanti(cliente) -> list[str]:
    if not cliente:
        return []
    return list(getattr(cliente, "campi_mancanti_per_conferimento", []) or [])


def _avvocato_referente_workflow(cliente=None, preventivo=None, conferimento=None) -> str:
    utente = g.get("utente_corrente")
    studio_forense = _studio_forense_context()
    return (
        getattr(conferimento, "avvocato_referente", "")
        or getattr(cliente, "avvocato_referente", "")
        or studio_forense.get("avvocato", "")
        or getattr(utente, "nome_completo", "")
        or getattr(utente, "username", "")
        or getattr(preventivo, "creato_da", "")
        or "Avv. referente"
    )


def _workflow_summary(cliente=None, preventivo=None, conferimento=None, fascicolo=None) -> dict:
    if not cliente or not (preventivo or conferimento):
        return {}
    try:
        return build_workflow_summary(
            cliente=cliente,
            preventivo=preventivo,
            conferimento=conferimento,
            fascicolo=fascicolo,
        )
    except Exception:
        current_app.logger.exception("Errore riepilogo workflow commerciale")
        return {}


def _apri_fascicolo_da_workflow(cliente, *, preventivo=None, conferimento=None) -> dict:
    gp = _get_gp()
    gf = get_fascicoli()
    gs = get_scadenziario()
    return apri_fascicolo_automatico(
        gp=gp,
        gf=gf,
        gs=gs,
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
        avvocato=_avvocato_referente_workflow(cliente=cliente, preventivo=preventivo, conferimento=conferimento),
    )


def _area_pratica_da_fascicolo(fascicolo) -> str:
    if not fascicolo:
        return ""
    tipo = getattr(getattr(fascicolo, "tipo", None), "value", "") or ""
    mapping = {
        "CIVILE": "Civile",
        "FAMIGLIA": "Civile",
        "SUCCESSIONI": "Civile",
        "LAVORO": "Civile",
        "PENALE": "Penale",
        "AMMINISTRATIVO": "Amministrativo",
        "TRIBUTARIO": "Tributario",
        "STRAGIUDIZIALE": "Stragiudiziale",
        "CONSULENZA": "Stragiudiziale",
        "ALTRO": "Speciali",
    }
    return mapping.get(str(tipo).upper(), "Speciali")


def _clausola_controversie_catalogo_context() -> list[dict]:
    return catalogo_clausola_controversie()


def _clausola_controversie_form_state(source=None) -> dict:
    attiva = bool(getattr(source, "clausola_controversie_attiva", False))
    modello_raw = getattr(source, "clausola_controversie_modello", "") if source else ""
    default_model = CLAUSOLA_CONTROVERSIE_TUTELA_CLIENTE
    modello = normalizza_modello_clausola_controversie(
        modello_raw or (default_model if attiva else default_model)
    )
    testo = (getattr(source, "clausola_controversie_testo", "") or "").strip()
    if attiva and not testo:
        testo = testo_predefinito_clausola_controversie(modello)
    return {
        "attiva": attiva,
        "modello": modello,
        "testo": testo,
        "trattativa_individuale": bool(
            getattr(source, "clausola_controversie_trattativa_individuale", False)
        ),
        "fonte": (getattr(source, "clausola_controversie_fonte", "") or "").strip()
        or (fonte_modello_clausola_controversie(modello) if attiva else ""),
    }


def _risolvi_prefill_conferimento(gc, gp, id_cliente: str = "", id_preventivo: str = "") -> dict:
    """Allinea il form conferimento al cliente realmente collegato al preventivo.

    Il link può arrivare da vecchie pagine, email o sessioni con un id cliente
    non più valido. In quel caso il preventivo resta la fonte autorevole del
    rapporto commerciale e impediamo che il form parta con dati incoerenti.
    """
    requested_cliente_id = (id_cliente or "").strip()
    id_preventivo = (id_preventivo or "").strip()
    preventivo_pre = gp.get_preventivo(id_preventivo) if id_preventivo else None

    resolved_cliente_id = requested_cliente_id
    cliente_sel = gc.get(resolved_cliente_id) if resolved_cliente_id else None
    warning = ""

    if id_preventivo and not preventivo_pre:
        warning = (
            "Il preventivo indicato non è più disponibile. "
            "Puoi comunque creare un conferimento selezionando il cliente corretto."
        )

    preventivo_cliente_id = ""
    if preventivo_pre:
        preventivo_cliente_id = str(getattr(preventivo_pre, "id_cliente", "") or "").strip()

    redirect_needed = False
    if preventivo_cliente_id and (
        not resolved_cliente_id
        or resolved_cliente_id != preventivo_cliente_id
        or cliente_sel is None
    ):
        resolved_cliente_id = preventivo_cliente_id
        cliente_sel = gc.get(resolved_cliente_id)
        redirect_needed = requested_cliente_id != resolved_cliente_id
        if requested_cliente_id and requested_cliente_id != resolved_cliente_id:
            warning = (
                "Ho riallineato il conferimento al cliente collegato al preventivo, "
                "evitando un collegamento anagrafico non coerente."
            )

    return {
        "id_cliente": resolved_cliente_id,
        "cliente": cliente_sel,
        "preventivo": preventivo_pre,
        "redirect_needed": redirect_needed,
        "warning": warning,
    }


def _contesto_fascicolo_wizard(fascicolo) -> dict:
    if not fascicolo:
        return {}
    rg_label = fascicolo.rg_completo or (f"RG {fascicolo.numero_rg}" if fascicolo.numero_rg else "")
    descrizione = (fascicolo.oggetto or fascicolo.titolo or "Pratica collegata").strip()
    context_label = f"{rg_label} — {descrizione}" if rg_label else descrizione
    return {
        "id": fascicolo.id,
        "titolo": fascicolo.titolo,
        "oggetto": fascicolo.oggetto or "",
        "numero": fascicolo.numero,
        "numero_rg": fascicolo.numero_rg or "",
        "anno_rg": fascicolo.anno_rg or "",
        "rg_label": rg_label,
        "tribunale": fascicolo.tribunale or "",
        "tipo_fascicolo": getattr(fascicolo.tipo, "value", ""),
        "area_pratica": _area_pratica_da_fascicolo(fascicolo),
        "context_label": context_label,
        "display_label": context_label,
    }


def _flag_from_form(form, key: str, default: bool = False) -> bool:
    values = form.getlist(key) if hasattr(form, "getlist") else []
    if values:
        normalized = [str(value or "").strip().lower() for value in values]
        if any(value in {"1", "true", "on", "si", "s", "yes"} for value in normalized):
            return True
        if any(value in {"0", "false", "off", "no"} for value in normalized):
            return False
    raw = str(form.get(key, "") or "").strip().lower()
    if raw in {"1", "true", "on", "si", "s", "yes"}:
        return True
    if raw in {"0", "false", "off", "no"}:
        return False
    return default


def _parse_intero(value, default: int = 0) -> int:
    try:
        return int(float(str(value or "").replace(",", ".").strip() or default))
    except (TypeError, ValueError):
        return default


def _compenso_a_tempo_da_form(form) -> tuple[str, dict]:
    tipo_compenso = normalizza_tipo_compenso(form.get("tipo_compenso", ""))
    if not is_compenso_a_tempo(tipo_compenso):
        return tipo_compenso, {}
    payload = calcola_compenso_a_tempo_art22bis(
        tariffa_oraria=_parse_numero(form.get("tariffa_oraria"), 0.0),
        ore_stimate=_parse_numero(form.get("ore_stimate"), 0.0),
        minuti_stimati=_parse_intero(form.get("minuti_stimati"), 0),
        criterio_arrotondamento=form.get("criterio_arrotondamento_orario", "").strip()
        or "ora_frazione_oltre_30",
        massimale_ore=_parse_numero(form.get("massimale_ore"), 0.0),
        soglia_preapprovazione_ore=_parse_numero(form.get("soglia_preapprovazione_ore"), 0.0),
    )
    return COMPENSO_A_TEMPO_CODE, payload


def _aggiungi_voce_compenso_a_tempo(voci: list, payload: dict) -> None:
    if not payload or payload.get("errors"):
        return
    from pct.preventivi import TipoVoce, VocePreventivo

    marker = "art. 22-bis"
    if any(marker in str(getattr(voce, "descrizione", "") or "").lower() for voce in voci):
        return
    voci.append(
        VocePreventivo(
            descrizione=descrizione_voce_compenso_a_tempo(payload),
            importo=float(payload.get("compenso_base") or 0.0),
            tipo=TipoVoce.ONORARIO,
        )
    )


def _sincronizza_log_compenso_a_tempo(raw_log: str, form, compenso_a_tempo: dict) -> str:
    data = sincronizza_contesto_economico(raw_log)
    if not data:
        data = costruisci_contesto_economico(
            source="preventivo_guidato",
            source_label="Preventivo guidato",
            oggetto=form.get("oggetto", "").strip(),
            tipo_compenso=normalizza_tipo_compenso(form.get("tipo_compenso", "")),
            tipo_procedimento=form.get("tipo_procedimento", "").strip(),
            valore_controversia=form.get("valore_controversia", "0"),
            applica_cpa=_flag_from_form(form, "applica_cassa", default=True),
            applica_iva=_flag_from_form(form, "applica_iva", default=True),
            anticipazioni_art15=_parse_numero(form.get("anticipazioni_art15"), 0.0),
        )
    if compenso_a_tempo:
        data["compenso_a_tempo"] = dict(compenso_a_tempo)
    return dump_log_calcolo(data)


def _arricchisci_log_cliente_anagrafico(raw_log: str, cliente) -> str:
    data = sincronizza_contesto_economico(raw_log)
    if not data or not cliente:
        return raw_log
    data["cliente_stato_anagrafico"] = str(
        getattr(getattr(cliente, "stato", ""), "value", getattr(cliente, "stato", ""))
        or ""
    )
    data["cliente_profilo_minimo_per_preventivo"] = bool(
        getattr(cliente, "profilo_minimo_per_preventivo", False)
    )
    data["cliente_profilo_completo_per_conferimento"] = bool(
        getattr(cliente, "profilo_completo_per_conferimento", False)
    )
    data["cliente_campi_mancanti_per_conferimento"] = list(
        getattr(cliente, "campi_mancanti_per_conferimento", []) or []
    )
    return dump_log_calcolo(data)


def _contesto_log_wizard_da_form(form, compenso_a_tempo: dict | None = None) -> str:
    raw = (form.get("log_calcolo", "") or "").strip()
    parsed = sincronizza_contesto_economico(raw)
    riferimenti_tassonomia = []
    raw_fonti_tassonomia = (form.get("fonti_tassonomia_json", "") or "").strip()
    if raw_fonti_tassonomia:
        try:
            parsed_fonti = json.loads(raw_fonti_tassonomia)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed_fonti = []
        if isinstance(parsed_fonti, list):
            riferimenti_tassonomia = parsed_fonti
    classificazioni_tassonomiche = _classificazioni_tassonomiche_da_raw(
        form.get("classificazioni_tassonomiche_json", "")
    )
    anticipazioni_totali = _anticipazioni_totali_wizard(form)
    if parsed:
        if classificazioni_tassonomiche:
            parsed["classificazioni_tassonomiche"] = classificazioni_tassonomiche
        parsed["anticipazioni_art15"] = anticipazioni_totali
        if compenso_a_tempo:
            parsed["compenso_a_tempo"] = dict(compenso_a_tempo)
        return dump_log_calcolo(parsed)
    return dump_log_calcolo(
        costruisci_contesto_economico(
            source="preventivo_guidato",
            source_label="Preventivo guidato",
            oggetto=form.get("oggetto", "").strip(),
            id_pratica=form.get("id_pratica", "").strip(),
            area_pratica=form.get("area_pratica", "").strip(),
            area_tassonomica=form.get("area_tassonomica", "").strip(),
            macro_area_tassonomica=form.get("macro_area_tassonomica", "").strip(),
            sottobranca_tassonomica=form.get("sottobranca_tassonomica", "").strip(),
            tassonomia_codice=form.get("tassonomia_codice", "").strip(),
            procedura_operativa_codice=form.get("procedura_operativa_codice", "").strip(),
            procedura_operativa_nome=form.get("procedura_operativa_nome", "").strip(),
            subbranch_operativa_codice=form.get("subbranch_operativa_codice", "").strip(),
            workflow_operativo_codice=form.get("workflow_operativo_codice", "").strip(),
            copertura_operativa=form.get("copertura_operativa", "").strip(),
            canale_operativo=form.get("canale_operativo", "").strip(),
            registro_operativo=form.get("registro_operativo", "").strip(),
            tipo_compenso=normalizza_tipo_compenso(form.get("tipo_compenso", "")),
            tipo_procedimento=form.get("tipo_procedimento", "").strip(),
            grado_sede=form.get("grado_sede", "").strip(),
            regola_tariffaria=form.get("regola_tariffaria", "").strip(),
            regola_tariffaria_code=form.get("regola_tariffaria", "").strip(),
            complessita=form.get("complessita", "").strip(),
            valore_controversia=form.get("valore_controversia", "0"),
            bonus_telematico=_flag_from_form(form, "bonus_telematico"),
            spese_generali=_flag_from_form(form, "spese_generali", default=True),
            perc_spese_generali=form.get("perc_spese_generali", "15"),
            applica_cpa=_flag_from_form(form, "applica_cassa", default=True),
            applica_iva=_flag_from_form(form, "applica_iva", default=True),
            anticipazioni_art15=anticipazioni_totali,
            adr_accordo=_flag_from_form(form, "adr_accordo"),
            riferimenti_tassonomia=riferimenti_tassonomia,
            classificazioni_tassonomiche=classificazioni_tassonomiche,
            compenso_a_tempo=compenso_a_tempo,
        )
    )


def _anticipazioni_totali_wizard(form) -> float:
    totale_hidden = (form.get("anticipazioni_art15_totali", "") or "").strip()
    if totale_hidden:
        return _parse_numero(totale_hidden, 0.0)
    return _parse_numero(form.get("anticipazioni_art15"), 0.0)


def _classificazioni_tassonomiche_da_raw(raw: str | list | None) -> list[dict]:
    if isinstance(raw, list):
        return _normalizza_classificazioni_tassonomiche(raw)
    payload = (raw or "").strip()
    if not payload:
        return []
    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return _normalizza_classificazioni_tassonomiche(parsed if isinstance(parsed, list) else [])


def _wizard_log_story(evento: str, **context) -> None:
    parti = []
    utente = g.get("utente_corrente")
    username = getattr(utente, "username", "") or "anonimo"
    parti.append(f"utente={username}")
    for key, value in context.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, bool):
            rendered = "si" if value else "no"
        elif isinstance(value, float):
            rendered = f"{value:.2f}"
        elif isinstance(value, (list, tuple, set)):
            rendered = ",".join(str(item) for item in value if item not in (None, ""))
        else:
            rendered = str(value)
        parti.append(f"{key}={rendered}")
    current_app.logger.info("Preventivi wizard | %s | %s", evento, " | ".join(parti))


def _crea_cliente_rapido_da_wizard(form) -> tuple[str, str]:
    from pct.clienti import TipoCliente

    gc = get_clienti()
    tipo_raw = (form.get("cliente_rapido_tipo") or "PERSONA_FISICA").strip().upper()
    tipo = TipoCliente(tipo_raw)
    avvocato = (form.get("avvocato_referente") or "").strip()
    note = "Anagrafica essenziale creata dal preventivo guidato. Completare i dati prima del conferimento definitivo."
    codice_fiscale = (
        form.get("cliente_rapido_codice_fiscale", "")
        if tipo == TipoCliente.PERSONA_FISICA
        else (form.get("cliente_rapido_codice_fiscale_pg", "") or form.get("cliente_rapido_codice_fiscale", ""))
    )
    cliente, creato = gc.crea_o_recupera_potenziale(
        tipo=tipo,
        nome=form.get("cliente_rapido_nome", ""),
        cognome=form.get("cliente_rapido_cognome", ""),
        ragione_sociale=form.get("cliente_rapido_ragione_sociale", ""),
        codice_fiscale=codice_fiscale,
        partita_iva=form.get("cliente_rapido_partita_iva", ""),
        provenienza="Preventivo guidato",
        avvocato_referente=avvocato,
        note=note,
    )
    if creato:
        return cliente.id, f"Cliente potenziale '{cliente.nome_completo}' creato dal wizard."
    return cliente.id, f"Cliente già presente: ho riutilizzato l'anagrafica '{cliente.nome_completo}'."


def _richiedi_login(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return f(*args, **kwargs)
    return wrapper


# ================================================================ LISTA

@preventivi.route("/", methods=["GET"])
@_richiedi_login
def lista():
    gp = _get_gp()
    gp.aggiorna_scaduti()

    tab = request.args.get("tab", "preventivi")  # preventivi | conferimenti
    anno = int(request.args.get("anno", date.today().year))
    stato_filtro = request.args.get("stato", "")
    cliente_filtro = request.args.get("id_cliente", "")
    filtro_rapido = request.args.get("filtro", "")

    tutti_prev = gp.tutti_preventivi()
    tutti_conf = gp.tutti_conferimenti()

    prev_anno = [p for p in tutti_prev if p.data_emissione.startswith(str(anno))]
    conf_anno = [c for c in tutti_conf if c.data_incarico.startswith(str(anno))]

    clienti_map = {c.id: c for c in get_clienti().tutti()}
    ids_preventivi_con_conferimento = {c.id_preventivo for c in tutti_conf if c.id_preventivo}

    if stato_filtro:
        prev_anno = [p for p in prev_anno if p.stato.value == stato_filtro]
        conf_anno = [c for c in conf_anno if c.stato.value == stato_filtro]
    if cliente_filtro:
        prev_anno = [p for p in prev_anno if p.id_cliente == cliente_filtro]
        conf_anno = [c for c in conf_anno if c.id_cliente == cliente_filtro]
    if filtro_rapido == "bozze":
        prev_anno = [p for p in prev_anno if p.stato.value in {"BOZZA", "IN_CALCOLO", "GENERATO"}]
    elif filtro_rapido == "inviati":
        prev_anno = [p for p in prev_anno if p.stato.value in {"INVIATO", "APERTO"}]
    elif filtro_rapido == "accettati":
        prev_anno = [p for p in prev_anno if p.stato.value == "ACCETTATO"]
    elif filtro_rapido == "da_completare_anagrafica":
        prev_anno = [
            p for p in prev_anno
            if _cliente_da_completare(clienti_map.get(p.id_cliente))
        ]
    elif filtro_rapido == "clienti_potenziali":
        prev_anno = [
            p for p in prev_anno
            if str(getattr(clienti_map.get(p.id_cliente), "stato", "")).endswith("POTENZIALE")
        ]
    elif filtro_rapido == "senza_conferimento":
        prev_anno = [p for p in prev_anno if p.id not in ids_preventivi_con_conferimento]

    anni_disponibili = sorted({
        int(p.data_emissione[:4]) for p in tutti_prev
    } | {
        int(c.data_incarico[:4]) for c in tutti_conf
    } | {date.today().year}, reverse=True)

    return render_template(
        "preventivi/lista.html",
        tab=tab,
        prev_lista=prev_anno,
        conf_lista=conf_anno,
        clienti_map=clienti_map,
        anno=anno,
        anni_disponibili=anni_disponibili,
        stato_filtro=stato_filtro,
        cliente_filtro=cliente_filtro,
        filtro_rapido=filtro_rapido,
        ids_preventivi_con_conferimento=ids_preventivi_con_conferimento,
        oggi=date.today(),
    )


# ================================================================ NUOVO PREVENTIVO

@preventivi.route("/nuovo", methods=["GET", "POST"])
@preventivi.route("/nuovo/<id_cliente>", methods=["GET", "POST"])
@_richiedi_login
def nuovo_preventivo(id_cliente: str = ""):
    gc = get_clienti()
    gp = _get_gp()

    if request.method == "POST":
        from pct.preventivi import VocePreventivo, TipoVoce
        f = request.form

        id_cliente = f.get("id_cliente", "").strip()
        if not id_cliente:
            flash("Seleziona un cliente.", "danger")
            return redirect(request.url)

        oggetto = f.get("oggetto", "").strip()
        if not oggetto:
            flash("Inserisci l'oggetto del preventivo.", "danger")
            return redirect(request.url)

        # Raccogli voci
        descrizioni = f.getlist("voce_descr[]")
        importi     = f.getlist("voce_importo[]")
        tipi        = f.getlist("voce_tipo[]")
        voci = []
        for desc, imp, tipo in zip(descrizioni, importi, tipi):
            desc = desc.strip()
            if not desc:
                continue
            try:
                voci.append(VocePreventivo(
                    descrizione=desc,
                    importo=_parse_numero(imp, 0.0),
                    tipo=TipoVoce(tipo) if tipo else TipoVoce.ONORARIO,
                ))
            except (ValueError, TypeError):
                pass

        valore_controversia = _parse_numero(f.get("valore_controversia"), 0.0)
        tariffa_oraria = _parse_numero(f.get("tariffa_oraria"), 0.0)
        ore_stimate = _parse_numero(f.get("ore_stimate"), 0.0)
        tipo_compenso, compenso_a_tempo = _compenso_a_tempo_da_form(f)
        if compenso_a_tempo.get("errors"):
            flash(" ".join(compenso_a_tempo["errors"]), "danger")
            return redirect(request.url)
        _aggiungi_voce_compenso_a_tempo(voci, compenso_a_tempo)

        if not voci:
            flash("Aggiungi almeno una voce.", "danger")
            return redirect(request.url)

        if compenso_a_tempo.get("warnings"):
            for warning in compenso_a_tempo["warnings"]:
                flash(warning, "warning")

        cfg = current_app.config
        log_calcolo = _sincronizza_log_compenso_a_tempo(
            f.get("log_calcolo", ""),
            f,
            compenso_a_tempo,
        )
        log_calcolo = _arricchisci_log_cliente_anagrafico(log_calcolo, gc.get(id_cliente))
        p = gp.crea_preventivo(
            id_cliente=id_cliente,
            oggetto=oggetto,
            voci=voci,
            creato_da=g.utente_corrente.username if g.utente_corrente else "",
            id_fascicolo=f.get("id_fascicolo", "").strip() or None,
            data_emissione=f.get("data_emissione") or date.today().isoformat(),
            data_scadenza=f.get("data_scadenza", "").strip() or None,
            applica_cassa=bool(f.get("applica_cassa")),
            applica_iva=bool(f.get("applica_iva")),
            anticipazioni_art15=_parse_numero(f.get("anticipazioni_art15"), 0.0),
            note=f.get("note", "").strip(),
            tipo_compenso=tipo_compenso,
            tipo_procedimento=f.get("tipo_procedimento", "").strip(),
            valore_controversia=valore_controversia,
            tariffa_oraria=tariffa_oraria,
            ore_stimate=ore_stimate,
            criterio_arrotondamento_orario=f.get("criterio_arrotondamento_orario", "").strip() or "ora_frazione_oltre_30",
            minuti_stimati=_parse_intero(f.get("minuti_stimati"), 0),
            ore_fatturabili_calcolate=float(compenso_a_tempo.get("ore_fatturabili") or 0.0),
            compenso_orario_base=float(compenso_a_tempo.get("compenso_base") or 0.0),
            massimale_ore=_parse_numero(f.get("massimale_ore"), 0.0),
            soglia_preapprovazione_ore=_parse_numero(f.get("soglia_preapprovazione_ore"), 0.0),
            richiede_consenso_superamento_soglia=True,
            attivita_orarie_incluse=f.get("attivita_orarie_incluse", "").strip(),
            attivita_orarie_escluse=f.get("attivita_orarie_escluse", "").strip(),
            warning_compenso_orario=list(compenso_a_tempo.get("warnings") or []),
            complessita=f.get("complessita", "").strip(),
            log_calcolo=log_calcolo,
            studio_piva=cfg.get("STUDIO_PIVA", ""),
            studio_cf=cfg.get("STUDIO_CF", ""),
            studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
            clausola_controversie_attiva=bool(f.get("clausola_controversie_attiva")),
            clausola_controversie_modello=f.get("clausola_controversie_modello", "").strip(),
            clausola_controversie_testo=f.get("clausola_controversie_testo", "").strip(),
            clausola_controversie_trattativa_individuale=bool(
                f.get("clausola_controversie_trattativa_individuale")
            ),
            clausola_controversie_fonte=f.get("clausola_controversie_fonte", "").strip(),
        )
        flash(f"Preventivo {p.numero} creato.", "success")
        from_page = f.get("from_page", "")
        if from_page == "cliente":
            return redirect(url_for("cartella_cliente", id_cliente=id_cliente))
        if from_page == "fascicolo" and p.id_fascicolo:
            return redirect(url_for("dettaglio_fascicolo", id_fascicolo=p.id_fascicolo))
        return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=p.id))

    # GET
    clienti = gc.tutti()
    cliente_sel = gc.get(id_cliente) if id_cliente else None
    fascicoli = []
    if cliente_sel:
        fascicoli = [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]

    from_page = request.args.get("from_page", "")
    id_fascicolo_pre = request.args.get("id_fascicolo", "")

    return render_template(
        "preventivi/form_preventivo.html",
        clienti=clienti,
        cliente_sel=cliente_sel,
        fascicoli=fascicoli,
        clausola_state=_clausola_controversie_form_state(),
        clausola_catalogo=_clausola_controversie_catalogo_context(),
        oggi=date.today(),
        scadenza_default=(date.today() + timedelta(days=30)).isoformat(),
        from_page=from_page,
        id_fascicolo_pre=id_fascicolo_pre,
    )


# ================================================================ DETTAGLIO PREVENTIVO

@preventivi.route("/p/<id_preventivo>", methods=["GET"])
@_richiedi_login
def dettaglio_preventivo(id_preventivo: str):
    from pct.preventivi import StatoPreventivo
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        flash("Preventivo non trovato o non piu' disponibile.", "warning")
        return redirect(url_for("preventivi.lista"))
    cliente = get_clienti().get(p.id_cliente)
    fascicolo = get_fascicoli().get(p.id_fascicolo) if p.id_fascicolo else None
    conferimenti = gp.conferimenti_per_preventivo(id_preventivo)
    conferimento_principale = conferimenti[0] if conferimenti else None
    portale_obj = _get_portale_mgr().get_by_cliente(cliente.id) if cliente else None
    url_crea_conferimento = url_for(
        "preventivi.nuovo_conferimento",
        id_cliente=p.id_cliente,
    ) + f"?id_preventivo={p.id}&from_page=preventivo"
    url_apri_fascicolo = _url_onboarding_fascicolo(
        p.id_cliente,
        id_preventivo=p.id,
        id_conferimento=conferimenti[0].id if conferimenti else "",
        from_page="preventivo",
    )
    url_crea_parcella = url_for("fatturazione.da_preventivo", id_preventivo=p.id)
    url_invia_cliente = url_for("preventivi.workflow_invia_cliente", id_preventivo=p.id)
    url_accetta_studio = url_for("preventivi.workflow_accetta_studio", id_preventivo=p.id)
    suggerisci_conferimento = (
        p.stato in {StatoPreventivo.ACCETTATO, StatoPreventivo.CONVERTITO}
        and not conferimenti
    )
    suggerisci_fascicolo = bool(
        not fascicolo and (conferimenti or p.stato in {StatoPreventivo.ACCETTATO, StatoPreventivo.CONVERTITO})
    )
    cliente_da_completare = _cliente_da_completare(cliente)
    campi_cliente_mancanti = _campi_cliente_mancanti(cliente)
    url_completa_cliente = ""
    if cliente:
        url_completa_cliente = _url_completa_cliente(
            cliente.id,
            next_url=url_crea_conferimento if suggerisci_conferimento else url_for("cartella_cliente", id_cliente=cliente.id),
        )
    workflow_summary = _workflow_summary(
        cliente=cliente,
        preventivo=p,
        conferimento=conferimento_principale,
        fascicolo=fascicolo,
    )
    return render_template(
        "preventivi/dettaglio_preventivo.html",
        p=p,
        cliente=cliente,
        fascicolo=fascicolo,
        conferimenti=conferimenti,
        conferimento_principale=conferimento_principale,
        portale_obj=portale_obj,
        url_crea_conferimento=url_crea_conferimento,
        url_crea_parcella=url_crea_parcella,
        url_apri_fascicolo=url_apri_fascicolo,
        url_invia_cliente=url_invia_cliente,
        url_accetta_studio=url_accetta_studio,
        url_completa_cliente=url_completa_cliente,
        suggerisci_conferimento=suggerisci_conferimento,
        suggerisci_fascicolo=suggerisci_fascicolo,
        cliente_da_completare=cliente_da_completare,
        campi_cliente_mancanti=campi_cliente_mancanti,
        workflow_summary=workflow_summary,
        calc_summary=riepilogo_contesto_economico(p.log_calcolo),
        clausola_modello_label=label_modello_clausola_controversie(p.clausola_controversie_modello),
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
        oggi=date.today(),
    )


# ================================================================ CAMBIA STATO PREVENTIVO

@preventivi.route("/p/<id_preventivo>/stato", methods=["GET", "POST"])
@_richiedi_login
def cambia_stato_preventivo(id_preventivo: str):
    from pct.preventivi import StatoPreventivo
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        flash("Preventivo non trovato o non piu' disponibile.", "warning")
        return redirect(url_for("preventivi.lista"))
    if request.method == "GET":
        flash("Per aggiornare lo stato usa i pulsanti del dettaglio preventivo.", "info")
        return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))
    stato_str = request.form.get("stato", "")
    try:
        nuovo_stato = StatoPreventivo(stato_str)
    except ValueError:
        flash("Stato non valido.", "danger")
        return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))
    try:
        if nuovo_stato == StatoPreventivo.ACCETTATO:
            gp.registra_accettazione_preventivo(
                id_preventivo,
                workflow_channel=p.workflow_channel or "STUDIO",
                via="STUDIO",
                ip=request.remote_addr or "",
                user_agent=request.headers.get("User-Agent", ""),
                creato_da=getattr(g.get("utente_corrente"), "username", ""),
                auto_crea_conferimento=False,
            )
        else:
            gp.cambia_stato_preventivo(id_preventivo, nuovo_stato)
    except Exception as exc:
        current_app.logger.exception("Errore cambio stato preventivo %s: %s", id_preventivo, exc)
        flash(
            "Non ho potuto aggiornare lo stato del preventivo. Riprova dal dettaglio o dalla scheda cliente.",
            "danger",
        )
        return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))
    flash(f"Stato aggiornato: {nuovo_stato.value}.", "success")
    if nuovo_stato == StatoPreventivo.ACCETTATO:
        flash(
            "Preventivo accettato: il prossimo passo consigliato e creare il conferimento di incarico e aprire il fascicolo guidato.",
            "success",
        )
    return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))


# ================================================================ WORKFLOW PREVENTIVO

@preventivi.route("/p/<id_preventivo>/workflow/invia", methods=["POST"])
@_richiedi_login
def workflow_invia_cliente(id_preventivo: str):
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        abort(404)
    cliente = get_clienti().get(p.id_cliente)
    portale_obj = _get_portale_mgr().get_by_cliente(cliente.id) if cliente else None
    channel = "ONLINE" if portale_obj and portale_obj.is_attivo else "STUDIO"
    gp.registra_invio_preventivo(id_preventivo, workflow_channel=channel)
    if portale_obj and portale_obj.is_attivo:
        flash(
            "Preventivo inviato al cliente. Il cliente può ora accettarlo dal portale e proseguire con il conferimento.",
            "success",
        )
    else:
        flash(
            "Preventivo marcato come inviato. Per l'accettazione online attiva anche il portale cliente; in alternativa registra l'accettazione in studio.",
            "success",
        )
    return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))


@preventivi.route("/p/<id_preventivo>/workflow/accetta-studio", methods=["POST"])
@_richiedi_login
def workflow_accetta_studio(id_preventivo: str):
    from pct.preventivi import StatoPreventivo
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        abort(404)
    cliente = get_clienti().get(p.id_cliente)
    conferimento_esistente = gp.get_conferimento_principale_preventivo(id_preventivo)
    if conferimento_esistente:
        gp.cambia_stato_preventivo(id_preventivo, StatoPreventivo.ACCETTATO)
        flash("Preventivo già accettato: il conferimento è pronto per la firma cliente.", "success")
        return redirect(url_for("preventivi.dettaglio_conferimento", id_conferimento=conferimento_esistente.id))
    if not cliente:
        gp.cambia_stato_preventivo(id_preventivo, StatoPreventivo.ACCETTATO)
        flash(
            "Preventivo accettato, ma il cliente collegato non e' piu' disponibile: "
            "riallinea l'anagrafica prima del conferimento.",
            "warning",
        )
        return redirect(_url_nuovo_conferimento_preventivo(id_preventivo, p.id_cliente))
    if _cliente_da_completare(cliente):
        gp.cambia_stato_preventivo(id_preventivo, StatoPreventivo.ACCETTATO)
        missing = ", ".join(_campi_cliente_mancanti(cliente)) or "dati anagrafici obbligatori"
        flash(
            "Preventivo accettato, ma il conferimento e' sospeso: completa prima l'anagrafica cliente. "
            f"Campi mancanti: {missing}.",
            "warning",
        )
        return redirect(
            _url_completa_cliente(
                p.id_cliente,
                next_url=url_for(
                    "preventivi.nuovo_conferimento",
                    id_cliente=p.id_cliente,
                    id_preventivo=id_preventivo,
                    from_page="preventivo",
                ),
            )
        )

    studio_forense = _studio_forense_context()
    try:
        _, conferimento = gp.registra_accettazione_preventivo(
            id_preventivo,
            workflow_channel="STUDIO",
            via="STUDIO",
            ip=request.remote_addr or "",
            user_agent=request.headers.get("User-Agent", ""),
            creato_da=getattr(g.get("utente_corrente"), "username", ""),
            avvocato_referente=_avvocato_referente_workflow(cliente=cliente, preventivo=p),
            auto_crea_conferimento=True,
            studio_piva=current_app.config.get("STUDIO_PIVA", ""),
            studio_cf=current_app.config.get("STUDIO_CF", ""),
            studio_indirizzo=current_app.config.get("STUDIO_INDIRIZZO", ""),
            numero_iscrizione_albo=studio_forense.get("numero_iscrizione_albo", ""),
            ordine_avvocati=studio_forense.get("ordine_avvocati", ""),
        )
    except Exception as exc:
        current_app.logger.exception("Errore accettazione preventivo %s: %s", id_preventivo, exc)
        try:
            gp.cambia_stato_preventivo(id_preventivo, StatoPreventivo.ACCETTATO)
        except Exception:
            current_app.logger.debug("Impossibile marcare il preventivo come accettato", exc_info=True)
        flash(
            "Accettazione registrata. Non ho potuto creare automaticamente il conferimento, "
            "ma ho aperto la maschera guidata con i dati disponibili gia' precompilati.",
            "warning",
        )
        return redirect(_url_nuovo_conferimento_preventivo(id_preventivo, p.id_cliente))
    flash("Accettazione cliente registrata in studio.", "success")
    if conferimento:
        flash("Conferimento creato automaticamente. Il prossimo passo è la firma del cliente.", "success")
        return redirect(url_for("preventivi.dettaglio_conferimento", id_conferimento=conferimento.id))
    return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))


# ================================================================ ELIMINA PREVENTIVO

@preventivi.route("/p/<id_preventivo>/elimina", methods=["POST"])
@_richiedi_login
def elimina_preventivo(id_preventivo: str):
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        abort(404)
    gp.elimina_preventivo(id_preventivo)
    flash("Preventivo eliminato.", "success")
    return redirect(url_for("preventivi.lista"))


# ================================================================ PDF PREVENTIVO

@preventivi.route("/p/<id_preventivo>/pdf", methods=["GET"])
@_richiedi_login
def pdf_preventivo(id_preventivo: str):
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        abort(404)
    cliente = get_clienti().get(p.id_cliente)
    fascicolo = get_fascicoli().get(p.id_fascicolo) if p.id_fascicolo else None
    buf = _genera_pdf_preventivo(p, cliente, fascicolo, current_app.config)
    nome_file = f"preventivo_{p.numero.replace('/', '-')}.pdf"
    download = (request.args.get("download") or "").strip().lower() in {"1", "true", "yes", "download"}
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=download, download_name=nome_file)


# ================================================================ NUOVO CONFERIMENTO

@preventivi.route("/conferimento/nuovo", methods=["GET", "POST"])
@preventivi.route("/conferimento/nuovo/<id_cliente>", methods=["GET", "POST"])
@_richiedi_login
def nuovo_conferimento(id_cliente: str = ""):
    gc = get_clienti()
    gp = _get_gp()

    if request.method == "POST":
        f = request.form
        studio_forense = _studio_forense_context()
        id_cliente = f.get("id_cliente", "").strip()
        if not id_cliente:
            flash("Seleziona un cliente.", "danger")
            return redirect(request.url)
        cliente_corrente = gc.get(id_cliente)

        oggetto = f.get("oggetto", "").strip()
        if not oggetto:
            flash("Inserisci l'oggetto dell'incarico.", "danger")
            return redirect(request.url)

        avvocato = f.get("avvocato_referente", "").strip() or studio_forense.get("avvocato", "")
        if not avvocato:
            flash("Inserisci il nome dell'avvocato referente.", "danger")
            return redirect(request.url)

        compenso = _parse_numero(f.get("compenso_pattuito"), 0.0)
        tariffa_oraria_c = _parse_numero(f.get("tariffa_oraria"), 0.0)
        quota_palmario = _parse_numero(f.get("quota_palmario_pct"), 0.0)
        id_preventivo = f.get("id_preventivo", "").strip()
        id_fascicolo = f.get("id_fascicolo", "").strip()
        apri_fascicolo_guidato = bool(f.get("apri_fascicolo_guidato")) and not id_fascicolo
        from pct.clienti import StatoCliente

        if (
            cliente_corrente
            and getattr(cliente_corrente, "stato", None) == StatoCliente.POTENZIALE
            and getattr(cliente_corrente, "profilo_completo_per_conferimento", False)
        ):
            note_cliente = str(getattr(cliente_corrente, "note", "") or "").strip()
            nota_conversione = "Cliente convertito da POTENZIALE ad ATTIVO in fase di conferimento incarico."
            if nota_conversione not in note_cliente:
                note_cliente = f"{note_cliente}\n{nota_conversione}".strip()
            gc.aggiorna(id_cliente, stato=StatoCliente.ATTIVO, note=note_cliente)

        cfg = current_app.config
        c = gp.crea_conferimento(
            id_cliente=id_cliente,
            oggetto=oggetto,
            avvocato_referente=avvocato,
            creato_da=g.utente_corrente.username if g.utente_corrente else "",
            id_preventivo=id_preventivo or None,
            id_fascicolo=id_fascicolo or None,
            data_incarico=f.get("data_incarico") or date.today().isoformat(),
            compenso_pattuito=compenso,
            note=f.get("note", "").strip(),
            id_pratica=f.get("id_pratica", "").strip(),
            area_pratica=f.get("area_pratica", "").strip(),
            numero_iscrizione_albo=(
                f.get("numero_iscrizione_albo", "").strip()
                or studio_forense.get("numero_iscrizione_albo", "")
            ),
            ordine_avvocati=(
                f.get("ordine_avvocati", "").strip()
                or studio_forense.get("ordine_avvocati", "")
            ),
            tipo_compenso=f.get("tipo_compenso", "").strip(),
            tipo_procedimento=f.get("tipo_procedimento", "").strip(),
            tariffa_oraria=tariffa_oraria_c,
            criterio_arrotondamento_orario=f.get("criterio_arrotondamento_orario", "").strip() or "ora_frazione_oltre_30",
            massimale_ore=_parse_numero(f.get("massimale_ore"), 0.0),
            soglia_preapprovazione_ore=_parse_numero(f.get("soglia_preapprovazione_ore"), 0.0),
            richiede_consenso_superamento_soglia=True,
            attivita_orarie_incluse=f.get("attivita_orarie_incluse", "").strip(),
            attivita_orarie_escluse=f.get("attivita_orarie_escluse", "").strip(),
            warning_compenso_orario=[],
            patto_palmario=bool(f.get("patto_palmario")),
            quota_palmario_pct=quota_palmario,
            informativa_art13_resa=bool(f.get("informativa_art13_resa")),
            clausola_adr_resa=bool(f.get("clausola_adr_resa")),
            clausola_controversie_attiva=bool(f.get("clausola_controversie_attiva")),
            clausola_controversie_modello=f.get("clausola_controversie_modello", "").strip(),
            clausola_controversie_testo=f.get("clausola_controversie_testo", "").strip(),
            clausola_controversie_trattativa_individuale=bool(
                f.get("clausola_controversie_trattativa_individuale")
            ),
            clausola_controversie_fonte=f.get("clausola_controversie_fonte", "").strip(),
            studio_piva=cfg.get("STUDIO_PIVA", ""),
            studio_cf=cfg.get("STUDIO_CF", ""),
            studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
        )
        if id_preventivo:
            from pct.preventivi import StatoPreventivo
            gp.aggiorna_preventivo(
                id_preventivo,
                stato=StatoPreventivo.CONVERTITO,
            )
        if apri_fascicolo_guidato:
            flash(
                f"Conferimento incarico {c.numero} creato. Completa ora l'apertura guidata del fascicolo.",
                "success",
            )
            return redirect(
                _url_onboarding_fascicolo(
                    id_cliente,
                    id_preventivo=id_preventivo,
                    id_conferimento=c.id,
                    from_page=f.get("from_page", "") or "conferimento",
                )
            )
        flash(f"Conferimento incarico {c.numero} creato.", "success")
        from_page = f.get("from_page", "")
        if from_page == "preventivo":
            if id_preventivo:
                return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))
        if from_page == "cliente":
            return redirect(url_for("cartella_cliente", id_cliente=id_cliente))
        return redirect(url_for("preventivi.dettaglio_conferimento", id_conferimento=c.id))

    id_preventivo_pre = request.args.get("id_preventivo", "")
    from_page = request.args.get("from_page", "")
    id_fascicolo_pre = request.args.get("id_fascicolo", "")
    prefill = _risolvi_prefill_conferimento(gc, gp, id_cliente, id_preventivo_pre)
    id_cliente = prefill["id_cliente"]
    cliente_sel = prefill["cliente"]
    preventivo_pre = prefill["preventivo"]
    if prefill["warning"]:
        flash(prefill["warning"], "warning")
    if prefill["redirect_needed"] and id_cliente:
        return redirect(
            url_for(
                "preventivi.nuovo_conferimento",
                id_cliente=id_cliente,
                **request.args.to_dict(flat=True),
            )
        )

    # GET
    studio_forense = _studio_forense_context()
    clienti = gc.tutti()
    fascicoli = []
    if cliente_sel:
        fascicoli = [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]

    cliente_da_completare = _cliente_da_completare(cliente_sel)
    campi_cliente_mancanti = _campi_cliente_mancanti(cliente_sel)
    url_completa_cliente = ""
    if cliente_sel:
        url_completa_cliente = _url_completa_cliente(
            cliente_sel.id,
            next_url=request.full_path.rstrip("?"),
        )

    # Preventivi del cliente per il select
    preventivi_cliente = []
    if cliente_sel:
        preventivi_cliente = gp.preventivi_per_cliente(id_cliente)

    return render_template(
        "preventivi/form_conferimento.html",
        clienti=clienti,
        cliente_sel=cliente_sel,
        fascicoli=fascicoli,
        preventivo_pre=preventivo_pre,
        preventivi_cliente=preventivi_cliente,
        clausola_state=_clausola_controversie_form_state(preventivo_pre),
        clausola_catalogo=_clausola_controversie_catalogo_context(),
        cliente_da_completare=cliente_da_completare,
        campi_cliente_mancanti=campi_cliente_mancanti,
        url_completa_cliente=url_completa_cliente,
        oggi=date.today(),
        from_page=from_page,
        id_fascicolo_pre=id_fascicolo_pre,
        studio_forense=studio_forense,
        apri_fascicolo_default=bool(preventivo_pre and not id_fascicolo_pre and not preventivo_pre.id_fascicolo),
    )


# ================================================================ DETTAGLIO CONFERIMENTO

@preventivi.route("/conferimento/<id_conferimento>", methods=["GET"])
@_richiedi_login
def dettaglio_conferimento(id_conferimento: str):
    gp = _get_gp()
    c = gp.get_conferimento(id_conferimento)
    if not c:
        abort(404)
    cliente = get_clienti().get(c.id_cliente)
    fascicolo = get_fascicoli().get(c.id_fascicolo) if c.id_fascicolo else None
    preventivo = gp.get_preventivo(c.id_preventivo) if c.id_preventivo else None
    url_apri_fascicolo = _url_onboarding_fascicolo(
        c.id_cliente,
        id_preventivo=c.id_preventivo or "",
        id_conferimento=c.id,
        from_page="conferimento",
    )
    cliente_da_completare = _cliente_da_completare(cliente)
    campi_cliente_mancanti = _campi_cliente_mancanti(cliente)
    url_completa_cliente = ""
    if cliente:
        url_completa_cliente = _url_completa_cliente(
            cliente.id,
            next_url=url_apri_fascicolo if not fascicolo else url_for("preventivi.dettaglio_conferimento", id_conferimento=c.id),
        )
    workflow_summary = _workflow_summary(
        cliente=cliente,
        preventivo=preventivo,
        conferimento=c,
        fascicolo=fascicolo,
    )
    return render_template(
        "preventivi/dettaglio_conferimento.html",
        c=c,
        cliente=cliente,
        fascicolo=fascicolo,
        preventivo=preventivo,
        url_apri_fascicolo=url_apri_fascicolo,
        url_firma_studio=url_for("preventivi.workflow_firma_conferimento_studio", id_conferimento=c.id),
        url_completa_cliente=url_completa_cliente,
        cliente_da_completare=cliente_da_completare,
        campi_cliente_mancanti=campi_cliente_mancanti,
        workflow_summary=workflow_summary,
        clausola_modello_label=label_modello_clausola_controversie(c.clausola_controversie_modello),
        studio_nome=current_app.config.get("STUDIO_NOME", "IUSENTRA"),
        oggi=date.today(),
    )


# ================================================================ CAMBIA STATO CONFERIMENTO

@preventivi.route("/conferimento/<id_conferimento>/stato", methods=["POST"])
@_richiedi_login
def cambia_stato_conferimento(id_conferimento: str):
    from pct.preventivi import StatoConferimento
    gp = _get_gp()
    c = gp.get_conferimento(id_conferimento)
    if not c:
        abort(404)
    stato_str = request.form.get("stato", "")
    try:
        nuovo_stato = StatoConferimento(stato_str)
    except ValueError:
        flash("Stato non valido.", "danger")
        return redirect(url_for("preventivi.dettaglio_conferimento", id_conferimento=id_conferimento))
    gp.cambia_stato_conferimento(id_conferimento, nuovo_stato)
    flash(f"Stato aggiornato: {nuovo_stato.value}.", "success")
    return redirect(url_for("preventivi.dettaglio_conferimento", id_conferimento=id_conferimento))


@preventivi.route("/conferimento/<id_conferimento>/workflow/firma-studio", methods=["POST"])
@_richiedi_login
def workflow_firma_conferimento_studio(id_conferimento: str):
    gp = _get_gp()
    c = gp.get_conferimento(id_conferimento)
    if not c:
        abort(404)
    cliente = get_clienti().get(c.id_cliente)
    preventivo = gp.get_preventivo(c.id_preventivo) if c.id_preventivo else None
    fascicolo = get_fascicoli().get(c.id_fascicolo) if c.id_fascicolo else None
    gp.registra_firma_conferimento(
        id_conferimento,
        via="STUDIO",
        workflow_channel=getattr(c, "workflow_channel", "") or getattr(preventivo, "workflow_channel", "") or "STUDIO",
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", ""),
    )
    if fascicolo:
        flash("Firma cliente registrata. Il fascicolo era già attivo.", "success")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=fascicolo.id))
    if cliente and _cliente_da_completare(cliente):
        flash(
            "Firma cliente registrata. Completa l'anagrafica per aprire il fascicolo automaticamente.",
            "warning",
        )
        return redirect(url_for("preventivi.dettaglio_conferimento", id_conferimento=id_conferimento))

    result = _apri_fascicolo_da_workflow(cliente, preventivo=preventivo, conferimento=gp.get_conferimento(id_conferimento))
    fasc = result["fascicolo"]
    flash(
        f"Firma cliente registrata. Fascicolo {fasc.numero} aperto automaticamente con {result['attivita_create']} attività iniziali e {result['scadenze_create']} scadenze.",
        "success",
    )
    return redirect(url_for("dettaglio_fascicolo", id_fasc=fasc.id))


# ================================================================ ELIMINA CONFERIMENTO

@preventivi.route("/conferimento/<id_conferimento>/elimina", methods=["POST"])
@_richiedi_login
def elimina_conferimento(id_conferimento: str):
    gp = _get_gp()
    c = gp.get_conferimento(id_conferimento)
    if not c:
        abort(404)
    gp.elimina_conferimento(id_conferimento)
    flash("Conferimento incarico eliminato.", "success")
    return redirect(url_for("preventivi.lista", tab="conferimenti"))


# ================================================================ PDF CONFERIMENTO

@preventivi.route("/conferimento/<id_conferimento>/pdf", methods=["GET"])
@_richiedi_login
def pdf_conferimento(id_conferimento: str):
    gp = _get_gp()
    c = gp.get_conferimento(id_conferimento)
    if not c:
        abort(404)
    cliente = get_clienti().get(c.id_cliente)
    fascicolo = get_fascicoli().get(c.id_fascicolo) if c.id_fascicolo else None
    preventivo = gp.get_preventivo(c.id_preventivo) if c.id_preventivo else None
    buf = _genera_pdf_conferimento(c, cliente, fascicolo, preventivo, current_app.config)
    nome_file = f"conferimento_incarico_{c.numero.replace('/', '-')}.pdf"
    download = (request.args.get("download") or "").strip().lower() in {"1", "true", "yes", "download"}
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=download, download_name=nome_file)


# ================================================================ AJAX fascicoli per cliente

@preventivi.route("/ajax/fascicoli/<id_cliente>")
@_richiedi_login
def ajax_fascicoli(id_cliente: str):
    from flask import jsonify
    fascicoli = [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]
    return jsonify([_contesto_fascicolo_wizard(f) for f in fascicoli])


@preventivi.route("/ajax/cliente-rapido", methods=["POST"])
@_richiedi_login
def ajax_cliente_rapido():
    from flask import jsonify

    try:
        id_cliente, msg_cliente = _crea_cliente_rapido_da_wizard(request.form)
        cliente = get_clienti().get(id_cliente)
        _wizard_log_story(
            "cliente rapido collegato",
            id_cliente=id_cliente,
            cliente=getattr(cliente, "nome_completo", "") or id_cliente,
            stato="creato" if "creat" in msg_cliente.lower() else "riutilizzato",
        )
        return jsonify(
            {
                "ok": True,
                "id_cliente": id_cliente,
                "label": getattr(cliente, "nome_completo", "") or id_cliente,
                "messaggio": msg_cliente,
                "creato": "creat" in msg_cliente.lower(),
            }
        )
    except ValueError as exc:
        _wizard_log_story("cliente rapido non completato", motivo=str(exc))
        return jsonify({"ok": False, "errore": str(exc)}), 200
    except Exception as exc:
        _wizard_log_story("cliente rapido fallito", motivo=str(exc))
        current_app.logger.exception("Errore creazione cliente rapido wizard: %s", exc)
        return jsonify({"ok": False, "errore": "Impossibile creare il cliente rapido."}), 200


@preventivi.route("/ajax/preventivi/<id_cliente>")
@_richiedi_login
def ajax_preventivi(id_cliente: str):
    from flask import jsonify
    gp = _get_gp()
    prev = gp.preventivi_per_cliente(id_cliente)
    return jsonify([{"id": p.id, "numero": p.numero,
                     "oggetto": p.oggetto, "totale": p.totale} for p in prev])


@preventivi.route("/ajax/parametri_dm55")
@_richiedi_login
def ajax_parametri_dm55():
    """Calcola i parametri di riferimento D.M. 147/2022.

    Parametri query string:
      tipo_procedimento   — stringa tipo procedimento
      tipo_mediazione     — "mediazione" | "negoziazione" (solo se tipo è ADR)
      valore              — valore controversia in €
      fasi                — fasi separate da virgola (per procedure ordinarie)
      grado               — "Giudice di Pace"|"Tribunale"|"Corte d'Appello"|"Corte di Cassazione"
      bonus_telematico    — "1" | "0"
      spese_generali      — "1" | "0"
      perc_spese_generali — float es. "15" → 0.15
      var_<nome_fase>     — variazione % per fase (es. var_attivazione=10 → +10%)
    """
    from flask import jsonify
    from pct.tariffario import calcola_compenso, Materia, Grado, Fase, livello_compenso_da_complessita

    tipo_proc        = request.args.get("tipo_procedimento", "")
    tipo_mediazione  = request.args.get("tipo_mediazione", "mediazione")
    valore           = _parse_numero(request.args.get("valore", 0), 0.0)
    fasi_raw         = request.args.get("fasi", "")
    grado_raw        = request.args.get("grado", "Tribunale")
    bonus_tel        = request.args.get("bonus_telematico", "0") == "1"
    incl_spese       = request.args.get("spese_generali", "0") == "1"
    complessita      = request.args.get("complessita", "media").strip() or "media"
    try:
        perc_sg = _parse_numero(request.args.get("perc_spese_generali", "15"), 15.0) / 100.0
    except (ValueError, TypeError):
        perc_sg = 0.15

    # Mappa tipo_procedimento → Materia
    _mappa_materia = {
        "Civile — fase di cognizione":       Materia.CIVILE_COGN,
        "Civile — fase esecutiva":           Materia.ESEC_MOB,
        "Penale":                            Materia.PENALE,
        "Lavoro":                            Materia.LAVORO,
        "Previdenza / Assistenza":           Materia.PREVIDENZA,
        "Amministrativo (TAR/CdS)":          Materia.AMMINISTRATIVO,
        "Tributario / CGT":                  Materia.TRIBUTARIO,
        "Stragiudiziale / Consulenza":       Materia.STRAGIUD,
        "Arbitrato":                         Materia.STRAGIUD,
        "Contabile / Corte dei Conti":       Materia.CONTABILE,
        "Giurisdizioni superiori / europee": Materia.GIURISDIZIONI_SUPERIORI,
        "Iscrizione ipotecaria / affari tavolari": Materia.AFFARI_IPOTECARI,
        "Crisi d'impresa / concorsuale":     Materia.CRISI_IMPRESA,
    }
    # Per mediazione/negoziazione: sceglie in base a tipo_mediazione
    if tipo_proc == "Mediazione / Negoziazione assistita":
        materia = Materia.NEGOZIAZIONE_ASSISTITA if tipo_mediazione == "negoziazione" else Materia.MEDIAZIONE
    else:
        materia = _mappa_materia.get(tipo_proc, Materia.CIVILE_COGN)

    # Mappa grado
    _mappa_grado = {
        "Giudice di Pace":   Grado.GIUDICE_DI_PACE,
        "Tribunale":         Grado.TRIBUNALE,
        "Giudice competente": Grado.GIUDICE_COMPETENTE,
        "Giudice tutelare":  Grado.GIUDICE_TUTELARE,
        "GIP / GUP":         Grado.GIP_GUP,
        "Tribunale monocratico": Grado.TRIBUNALE_MONOCRATICO,
        "Tribunale collegiale": Grado.TRIBUNALE_COLLEGIALE,
        "Corte d'Assise":    Grado.CORTE_ASSISE,
        "Corte d'Appello":   Grado.CORTE_APPELLO,
        "Corte d'Appello penale": Grado.CORTE_APPELLO_PENALE,
        "Corte d'Assise d'Appello": Grado.CORTE_ASSISE_APPELLO,
        "Corte di Cassazione": Grado.CASSAZIONE,
        "Tribunale di Sorveglianza": Grado.TRIBUNALE_SORVEGLIANZA,
        "Magistrato di Sorveglianza": Grado.MAGISTRATO_SORVEGLIANZA,
        "TAR": Grado.TAR,
        "Consiglio di Stato": Grado.CONSIGLIO_DI_STATO,
        "Corte dei Conti": Grado.CORTE_DEI_CONTI,
        "Corte cost. / Corte europea / CGUE": Grado.CORTE_SUPERIORE_UE,
        "Conservatoria / tavolare": Grado.CONSERVATORIA_TAVOLARE,
        "Tribunale concorsuale": Grado.TRIBUNALE_CONCORSUALE,
        "CGT di primo grado": Grado.CGT_PRIMO_GRADO,
        "CGT di secondo grado": Grado.CGT_SECONDO_GRADO,
        "Fuori giudizio": Grado.FUORI_GIUDIZIO,
        "Procedura ADR": Grado.PROCEDURA_ADR,
    }
    grado = _mappa_grado.get(grado_raw, Grado.TRIBUNALE)

    # Mappa chiavi checkbox → Fase (procedure ordinarie)
    _mappa_fase = {
        "studio":       Fase.STUDIO,
        "introduttiva": Fase.INTRODUTTIVA,
        "istruttoria":  Fase.ISTRUTTORIA,
        "decisionale":  Fase.DECISIONALE,
        "esecutiva":    Fase.ESECUTIVA,
    }
    fasi_selezionate = [
        _mappa_fase[k] for k in fasi_raw.split(",")
        if k.strip() in _mappa_fase
    ]
    if not fasi_selezionate and materia not in {Materia.MEDIAZIONE, Materia.NEGOZIAZIONE_ASSISTITA, Materia.STRAGIUD}:
        fasi_selezionate = [Fase.STUDIO, Fase.INTRODUTTIVA,
                            Fase.ISTRUTTORIA, Fase.DECISIONALE]

    # Raccogli variazioni per fase (var_attivazione, var_rivitalizzazione, ecc.)
    _mappa_var_fasi = {
        "attivazione":      Fase.ATTIVAZIONE.value,
        "rivitalizzazione": Fase.RIVITALIZZAZIONE.value,
        "negoziazione":     Fase.NEGOZIAZIONE_TRATTAZIONE.value,
        "conciliazione":    Fase.CONCILIAZIONE.value,
        "studio":           Fase.STUDIO.value,
        "introduttiva":     Fase.INTRODUTTIVA.value,
        "istruttoria":      Fase.ISTRUTTORIA.value,
        "decisionale":      Fase.DECISIONALE.value,
        "esecutiva":        Fase.ESECUTIVA.value,
    }
    variazioni_fasi: dict = {}
    for k, fase_label in _mappa_var_fasi.items():
        raw_val = request.args.get(f"var_{k}")
        if raw_val is not None:
            try:
                variazioni_fasi[fase_label] = 1.0 + (_parse_numero(raw_val, 0.0) / 100.0)
            except (ValueError, TypeError):
                pass

    maggiorazioni_fasi: dict = {}
    if request.args.get("adr_accordo", "0") == "1":
        if materia == Materia.MEDIAZIONE:
            maggiorazioni_fasi[Fase.ATTIVAZIONE.value] = 1.30
            maggiorazioni_fasi[Fase.RIVITALIZZAZIONE.value] = 1.30
        elif materia == Materia.NEGOZIAZIONE_ASSISTITA:
            maggiorazioni_fasi[Fase.ATTIVAZIONE.value] = 1.30
            maggiorazioni_fasi[Fase.NEGOZIAZIONE_TRATTAZIONE.value] = 1.30

    try:
        ris = calcola_compenso(
            materia=materia,
            grado=grado,
            valore=valore,
            fasi=fasi_selezionate,
            bonus_telematico=bonus_tel,
            includi_spese_generali=incl_spese,
            perc_spese_generali=perc_sg,
            variazioni_fasi=variazioni_fasi or None,
            maggiorazioni_fasi=maggiorazioni_fasi or None,
            complessita=complessita,
        )
        livello = livello_compenso_da_complessita(complessita)
        totale_selezionato = ris.totale_compenso_livello(livello)
        # Costruisce la risposta con dettaglio min/base/max per fase
        fasi_out = {}
        for fase, (vmin, vbase, vmax) in ris.dettaglio.items():
            fasi_out[fase] = {"min": vmin, "base": vbase, "max": vmax}
        return jsonify({
            "materia":           ris.materia,
            "scaglione":         ris.scaglione,
            "fasi":              fasi_out,
            # Totali
            "totale_minimo":     ris.totale_minimo,
            "totale_base":       ris.totale_base,
            "totale_massimo":    ris.totale_massimo,
            "bonus_telematico":  ris.bonus_telematico,
            "spese_generali":    ris.spese_generali,
            "perc_spese_generali": int(round(ris.perc_spese_generali * 100)),
            "totale_con_spese":  ris.totale_con_spese,
            # Compat
            "totale":            totale_selezionato,
            "complessita":       complessita,
            "livello_compenso":  livello.value,
            "nota":              ris.note,
        })
    except Exception as e:
        current_app.logger.exception("Errore calcolo DM147: %s", e)
        return jsonify({"errore": str(e)}), 200


# ================================================================ WIZARD MOTORE PREVENTIVO

@preventivi.route("/wizard", methods=["GET"])
@_richiedi_login
def wizard():
    """Wizard step-by-step per la costruzione guidata del preventivo."""
    from pct.motore_preventivo import AREE_WIZARD, catalogo_wizard
    gc = get_clienti()
    gf = get_fascicoli()
    id_cliente = request.args.get("id_cliente", "").strip()
    id_fascicolo_pre = request.args.get("id_fascicolo", "").strip()
    fascicolo_pre = gf.get(id_fascicolo_pre) if id_fascicolo_pre else None
    if fascicolo_pre and not id_cliente:
        id_cliente = fascicolo_pre.id_cliente or ""
    cliente_sel = gc.get(id_cliente) if id_cliente else None
    area_raw = request.args.get("area", "").strip()
    area_prefill = {
        "CIVILE_COGN": "Civile",
        "ESEC_MOB": "Civile",
        "ESEC_IMMO": "Civile",
        "VOLONTARIA": "Civile",
        "LAVORO": "Civile",
        "PREVIDENZA": "Civile",
        "PENALE": "Penale",
        "AMMINISTRATIVO": "Amministrativo",
        "TRIBUTARIO": "Tributario",
        "STRAGIUD": "Stragiudiziale",
        "MEDIAZIONE": "Stragiudiziale",
        "NEGOZIAZIONE_ASSISTITA": "Stragiudiziale",
    }.get(area_raw.upper(), area_raw)
    fasi_prefill = [
        item.strip()
        for item in (request.args.get("fasi", "") or "").split(",")
        if item.strip()
    ]
    wizard_prefill = {
        "id_pratica": request.args.get("id_pratica", "").strip(),
        "area": area_prefill,
        "area_tassonomica": request.args.get("area_tassonomica", "").strip(),
        "macro_area_tassonomica": request.args.get("macro_area_tassonomica", "").strip(),
        "sottobranca_tassonomica": request.args.get("sottobranca_tassonomica", "").strip(),
        "procedura_operativa_codice": request.args.get("procedura_operativa_codice", "").strip(),
        "procedura_operativa_nome": request.args.get("procedura_operativa_nome", "").strip(),
        "subbranch_operativa_codice": request.args.get("subbranch_operativa_codice", "").strip(),
        "workflow_operativo_codice": request.args.get("workflow_operativo_codice", "").strip(),
        "copertura_operativa": request.args.get("copertura_operativa", "").strip(),
        "canale_operativo": request.args.get("canale_operativo", "").strip(),
        "registro_operativo": request.args.get("registro_operativo", "").strip(),
        "valore": request.args.get("valore", "").strip(),
        "grado": request.args.get("grado", "").strip(),
        "regola_tariffaria": request.args.get("regola_tariffaria", "").strip(),
        "complessita": request.args.get("complessita", "media").strip() or "media",
        "fasi": fasi_prefill,
        "variazioni_fasi": {
            key: (request.args.get(f"var_{key}", "") or "").strip()
            for key in ("attivazione", "rivitalizzazione", "negoziazione", "conciliazione")
            if (request.args.get(f"var_{key}", "") or "").strip()
        },
        "mediazione_odm": mediazione_odm_context_for_prefill(request.args),
        "adr_accordo": request.args.get("adr_accordo", "0") == "1",
        "bonus_telematico": request.args.get("bonus_telematico", "0") == "1",
        "spese_generali": request.args.get("spese_generali", "1") == "1",
        "perc_spese_generali": request.args.get("perc_spese_generali", "15").strip() or "15",
        "applica_cpa": request.args.get("applica_cpa", "1") == "1",
        "applica_iva": request.args.get("applica_iva", "1") == "1",
        "anticipazioni": request.args.get("anticipazioni", "").strip(),
        "tariffa_oraria": request.args.get("tariffa_oraria", "").strip(),
        "ore_stimate": request.args.get("ore_stimate", "").strip(),
        "minuti_stimati": request.args.get("minuti_stimati", "").strip(),
        "criterio_arrotondamento_orario": request.args.get("criterio_arrotondamento_orario", "").strip(),
        "massimale_ore": request.args.get("massimale_ore", "").strip(),
        "soglia_preapprovazione_ore": request.args.get("soglia_preapprovazione_ore", "").strip(),
        "attivita_orarie_incluse": request.args.get("attivita_orarie_incluse", "").strip(),
        "attivita_orarie_escluse": request.args.get("attivita_orarie_escluse", "").strip(),
        "oggetto": request.args.get("oggetto", "").strip(),
        "note": request.args.get("note", "").strip(),
        "accessori": [],
        "esborsi": [],
        "manual_voci": [],
        "classificazioni_tassonomiche": [],
        "has_accessori_prefill": False,
        "has_esborsi_prefill": False,
        "has_manual_voci_prefill": False,
        "has_classificazioni_tassonomiche_prefill": False,
        "auto_calcola": request.args.get("auto_calcola", "").strip() == "1",
    }
    clausola_state = {
        "attiva": request.args.get("clausola_controversie_attiva", "0") == "1",
        "modello": normalizza_modello_clausola_controversie(
            request.args.get("clausola_controversie_modello", "").strip() or CLAUSOLA_CONTROVERSIE_TUTELA_CLIENTE
        ),
        "testo": request.args.get("clausola_controversie_testo", "").strip(),
        "trattativa_individuale": request.args.get(
            "clausola_controversie_trattativa_individuale", "0"
        )
        == "1",
        "fonte": request.args.get("clausola_controversie_fonte", "").strip(),
    }
    if not clausola_state["fonte"]:
        clausola_state["fonte"] = fonte_modello_clausola_controversie(clausola_state["modello"])
    if clausola_state["attiva"] and not clausola_state["testo"]:
        clausola_state["testo"] = testo_predefinito_clausola_controversie(clausola_state["modello"])
    for key, field_name in (
        ("accessori_json", "accessori"),
        ("esborsi_json", "esborsi"),
        ("manual_voci_json", "manual_voci"),
    ):
        raw_value = (request.args.get(key, "") or "").strip()
        if not raw_value:
            continue
        try:
            parsed = json.loads(raw_value)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = []
        if isinstance(parsed, list):
            wizard_prefill[field_name] = parsed
            wizard_prefill[f"has_{field_name}_prefill"] = True
    wizard_prefill["classificazioni_tassonomiche"] = _classificazioni_tassonomiche_da_raw(
        request.args.get("classificazioni_tassonomiche_json", "")
    )
    wizard_prefill["has_classificazioni_tassonomiche_prefill"] = bool(
        wizard_prefill["classificazioni_tassonomiche"]
    )
    return render_template(
        "preventivi/wizard.html",
        catalogo_per_area=catalogo_wizard(),
        aree=AREE_WIZARD,
        clienti=gc.tutti(),
        cliente_sel=cliente_sel,
        id_cliente_pre=id_cliente,
        id_fascicolo_pre=id_fascicolo_pre,
        fascicolo_pre_context=_contesto_fascicolo_wizard(fascicolo_pre) if fascicolo_pre else None,
        wizard_prefill=wizard_prefill,
        clausola_state=clausola_state,
        clausola_catalogo=_clausola_controversie_catalogo_context(),
        from_page=request.args.get("from_page", "").strip(),
        entry_mode=request.args.get("entry", "").strip(),
        oggi=date.today(),
        scadenza_default=(date.today() + timedelta(days=30)).isoformat(),
    )


@preventivi.route("/wizard/calcola", methods=["GET"])
@_richiedi_login
def wizard_calcola():
    """AJAX — calcola compenso dal motore preventivo.

    Parametri query string:
      id_pratica, valore, grado, fasi (comma-sep), bonus_telematico,
      spese_generali, perc_spese_generali, applica_cpa, applica_iva,
      anticipazioni, variazioni per fase (var_studio, var_introduttiva, ecc.)
    """
    from flask import jsonify
    from pct.motore_preventivo import get_tipo_pratica, motore_calcola
    from pct.tariffario import Fase, Grado, livello_compenso_da_complessita
    from pct.tariffario_catalogo import default_rule_for_practice, rule_lookup, rules_for_practice

    try:
        id_pratica = request.args.get("id_pratica", "")
        valore = _parse_numero(request.args.get("valore", 0), 0.0)
        grado_raw = request.args.get("grado", "")
        regola_tariffaria = request.args.get("regola_tariffaria", "").strip()
        complessita = request.args.get("complessita", "media").strip() or "media"
        fasi_raw = request.args.get("fasi", "")
        bonus_tel = request.args.get("bonus_telematico", "0") == "1"
        incl_spese = request.args.get("spese_generali", "1") == "1"
        mediazione_odm_context = parse_mediazione_odm_context(request.args)
        try:
            perc_sg = _parse_numero(request.args.get("perc_spese_generali", "15"), 15.0) / 100.0
        except (ValueError, TypeError):
            perc_sg = 0.15
        applica_cpa = request.args.get("applica_cpa", "1") == "1"
        applica_iva = request.args.get("applica_iva", "1") == "1"
        anticipazioni = _parse_numero(request.args.get("anticipazioni", 0), 0.0)

        if not id_pratica:
            return jsonify({"errore": "id_pratica mancante"}), 200

        tp = get_tipo_pratica(id_pratica)
        if not tp:
            return jsonify({"errore": f"Tipologia non trovata: {id_pratica}"}), 200
        if regola_tariffaria:
            regole_ammissibili = {
                str(row.get("rule_code", "") or "")
                for row in rules_for_practice(id_pratica)
            }
            if regola_tariffaria not in regole_ammissibili:
                regola_tariffaria = ""

        _mappa_grado = {
            "Giudice di Pace": Grado.GIUDICE_DI_PACE,
            "Tribunale": Grado.TRIBUNALE,
            "GIP / GUP": Grado.GIP_GUP,
            "Tribunale monocratico": Grado.TRIBUNALE_MONOCRATICO,
            "Tribunale collegiale": Grado.TRIBUNALE_COLLEGIALE,
            "Corte d'Assise": Grado.CORTE_ASSISE,
            "Corte d'Appello": Grado.CORTE_APPELLO,
            "Corte d'Appello penale": Grado.CORTE_APPELLO_PENALE,
            "Corte d'Assise d'Appello": Grado.CORTE_ASSISE_APPELLO,
            "Corte di Cassazione": Grado.CASSAZIONE,
            "Tribunale di Sorveglianza": Grado.TRIBUNALE_SORVEGLIANZA,
            "TAR": Grado.TAR,
            "Consiglio di Stato": Grado.CONSIGLIO_DI_STATO,
            "CGT di primo grado": Grado.CGT_PRIMO_GRADO,
            "CGT di secondo grado": Grado.CGT_SECONDO_GRADO,
            "Fuori giudizio": Grado.FUORI_GIUDIZIO,
            "Procedura ADR": Grado.PROCEDURA_ADR,
        }
        grado = _mappa_grado.get(grado_raw) if grado_raw else None
        livello = livello_compenso_da_complessita(complessita)

        regola_per_fasi = rule_lookup(regola_tariffaria) if regola_tariffaria else None
        if not regola_per_fasi:
            regola_per_fasi = default_rule_for_practice(id_pratica)
        profile_fasi = (regola_per_fasi or {}).get("profile", {}) or {}
        profilo_compenso_unico = (
            profile_fasi.get("calc_mode") == "compenso_unico"
            or "compenso_unico" in (profile_fasi.get("phase_keys") or [])
        )

        _mappa_fase = {
            "studio": Fase.STUDIO,
            "introduttiva": Fase.INTRODUTTIVA,
            "istruttoria": Fase.ISTRUTTORIA,
            "decisionale": Fase.DECISIONALE,
            "esecutiva": Fase.ESECUTIVA,
            "attivazione": Fase.ATTIVAZIONE,
            "rivitalizzazione": Fase.RIVITALIZZAZIONE,
            "negoziazione": Fase.NEGOZIAZIONE_TRATTAZIONE,
            "conciliazione": Fase.CONCILIAZIONE,
        }
        fasi_tokens = [k.strip() for k in fasi_raw.split(",") if k.strip()]
        fasi_parsed = [_mappa_fase[k] for k in fasi_tokens if k in _mappa_fase]
        fasi_esplicite = "fasi" in request.args
        compenso_unico_attivo = "compenso_unico" in fasi_tokens
        if profilo_compenso_unico and compenso_unico_attivo:
            fasi = fasi_parsed or [Fase.STUDIO]
        elif fasi_parsed:
            fasi = fasi_parsed
        elif fasi_esplicite:
            fasi = []
        else:
            fasi = None
        profile_code_override = None
        if fasi_esplicite and profilo_compenso_unico and not compenso_unico_attivo and fasi_parsed:
            profile_code_override = ""

        _mappa_var_fasi = {
            "attivazione": Fase.ATTIVAZIONE.value,
            "rivitalizzazione": Fase.RIVITALIZZAZIONE.value,
            "negoziazione": Fase.NEGOZIAZIONE_TRATTAZIONE.value,
            "conciliazione": Fase.CONCILIAZIONE.value,
            "studio": Fase.STUDIO.value,
            "introduttiva": Fase.INTRODUTTIVA.value,
            "istruttoria": Fase.ISTRUTTORIA.value,
            "decisionale": Fase.DECISIONALE.value,
            "esecutiva": Fase.ESECUTIVA.value,
        }
        variazioni_fasi: dict = {}
        for k, fase_label in _mappa_var_fasi.items():
            raw_val = request.args.get(f"var_{k}")
            if raw_val is not None:
                try:
                    variazioni_fasi[fase_label] = 1.0 + (_parse_numero(raw_val, 0.0) / 100.0)
                except (ValueError, TypeError):
                    pass

        maggiorazioni_fasi: dict = {}
        variation_policy = dict(getattr(tp, "variation_policy", {}) or {})
        agreement_bonus = dict(variation_policy.get("agreement_bonus", {}) or {})
        if request.args.get("adr_accordo", "0") == "1" and agreement_bonus.get("enabled"):
            pct = float(agreement_bonus.get("pct", 0) or 0)
            multiplier = 1.0 + (pct / 100.0)
            phase_key_to_value = {
                "attivazione": Fase.ATTIVAZIONE.value,
                "rivitalizzazione": Fase.RIVITALIZZAZIONE.value,
                "negoziazione": Fase.NEGOZIAZIONE_TRATTAZIONE.value,
                "conciliazione": Fase.CONCILIAZIONE.value,
            }
            for key in agreement_bonus.get("phase_keys", []) or []:
                phase_value = phase_key_to_value.get(str(key))
                if phase_value:
                    maggiorazioni_fasi[phase_value] = multiplier

        ris = motore_calcola(
            id_pratica=id_pratica,
            valore_controversia=valore,
            grado=grado,
            regola_tariffaria=regola_tariffaria,
            profile_code_override=profile_code_override,
            fasi=fasi,
            livello_compenso=livello,
            complessita=complessita,
            bonus_telematico=bonus_tel,
            includi_spese_generali=incl_spese,
            perc_spese_generali=perc_sg,
            variazioni_fasi=variazioni_fasi or None,
            maggiorazioni_fasi=maggiorazioni_fasi or None,
            applica_cpa=applica_cpa,
            applica_iva=applica_iva,
            anticipazioni=anticipazioni,
        )
        mediazione_odm = (
            calcola_mediazione_odm_da_context(valore, mediazione_odm_context)
            if is_mediazione_practice(tp)
            else None
        )
        dm = ris.calcolo_dm55
        riepilogo_livello = dm.riepilogo_livello(livello)
        bonus_telematico_livello = round(float(riepilogo_livello.get("bonus_telematico", 0.0)), 2)
        spese_generali_livello = round(float(riepilogo_livello.get("spese_generali", 0.0)), 2)
        totale_compenso_livello = round(float(riepilogo_livello.get("totale_compenso", ris.onorario_selezionato)), 2)
        compenso_bozza = totale_compenso_livello
        anticipazioni_bozza = round(anticipazioni, 2)
        cpa_bozza = round(compenso_bozza * 0.04, 2) if applica_cpa else 0.0
        base_iva_bozza = round(compenso_bozza + cpa_bozza, 2)
        iva_bozza = round(base_iva_bozza * 0.22, 2) if applica_iva else 0.0
        totale_bozza = round(base_iva_bozza + iva_bozza + anticipazioni_bozza, 2)

        _wizard_log_story(
            "calcolo completato",
            pratica=id_pratica,
            regola=regola_tariffaria,
            grado=grado_raw,
            complessita=complessita,
            fasi=[fase.value for fase in fasi] if fasi else [],
            spese_generali=incl_spese,
            bonus_telematico=bonus_tel,
            mediazione_odm=bool(mediazione_odm),
            totale=ris.totale,
        )

        fasi_out = {fase: {"min": v[0], "base": v[1], "max": v[2]}
                    for fase, v in dm.dettaglio.items()}

        return jsonify({
            "tipo_pratica":          tp.to_dict(),
            "summary":               tp.summary,
            "when_to_use":           tp.when_to_use,
            "normative_references":  tp.normative_references,
            "materia":               dm.materia,
            "scaglione":             dm.scaglione,
            "fasi":                  fasi_out,
            "totale_minimo":         dm.totale_minimo,
            "totale_base":           dm.totale_base,
            "totale_massimo":        dm.totale_massimo,
            "bonus_telematico":      bonus_telematico_livello,
            "spese_generali":        spese_generali_livello,
            "perc_spese_generali":   int(round(dm.perc_spese_generali * 100)),
            "totale_con_spese":      totale_compenso_livello,
            "onorario_base":         ris.onorario_base,
            "onorario_selezionato":  ris.onorario_selezionato,
            "cpa":                   ris.cpa,
            "base_iva":              ris.base_iva,
            "iva":                   ris.iva,
            "anticipazioni":         ris.anticipazioni,
            "totale":                ris.totale,
            "compenso_bozza":        compenso_bozza,
            "spese_generali_bozza":  0.0,
            "spese_generali_in_compenso_bozza": True,
            "anticipazioni_bozza":   anticipazioni_bozza,
            "cpa_bozza":             cpa_bozza,
            "base_iva_bozza":        base_iva_bozza,
            "iva_bozza":             iva_bozza,
            "totale_bozza":          totale_bozza,
            "applica_cpa":           ris.applica_cpa,
            "applica_iva":           ris.applica_iva,
            "livello_compenso":      ris.livello_compenso,
            "complessita":           complessita,
            "regola_tariffaria":     regola_tariffaria,
            "nota":                  dm.note,
            "base_normativa":        tp.base_normativa,
            "mediazione_odm":        mediazione_odm,
        })
    except Exception as e:
        _wizard_log_story(
            "calcolo fallito",
            pratica=request.args.get("id_pratica", ""),
            motivo=str(e),
        )
        current_app.logger.exception("Errore wizard_calcola: %s", e)
        return jsonify({"errore": str(e)}), 200


@preventivi.route("/wizard/genera", methods=["POST"])
@_richiedi_login
def wizard_genera():
    """Genera preventivo (e opzionalmente conferimento) dai dati del wizard."""
    from pct.preventivi import VocePreventivo, TipoVoce
    f = request.form
    gp = _get_gp()

    id_cliente = f.get("id_cliente", "").strip()
    if not id_cliente:
        if _flag_from_form(f, "cliente_rapido_attivo"):
            try:
                id_cliente, msg_cliente = _crea_cliente_rapido_da_wizard(f)
                flash(msg_cliente, "success")
            except ValueError as e:
                flash(str(e), "danger")
                return redirect(url_for("preventivi.wizard", from_page=f.get("from_page", "").strip()))
        else:
            flash("Seleziona un cliente oppure inseriscine uno rapido.", "danger")
            return redirect(url_for("preventivi.wizard", from_page=f.get("from_page", "").strip()))

    oggetto = f.get("oggetto", "").strip()
    if not oggetto:
        flash("Inserisci l'oggetto del preventivo.", "danger")
        return redirect(url_for("preventivi.wizard"))

    # Voci dal wizard
    descrizioni = f.getlist("voce_descr[]")
    importi     = f.getlist("voce_importo[]")
    tipi        = f.getlist("voce_tipo[]")
    voci = []
    for desc, imp, tipo in zip(descrizioni, importi, tipi):
        desc = desc.strip()
        if not desc:
            continue
        try:
            voci.append(VocePreventivo(
                descrizione=desc,
                importo=_parse_numero(imp, 0.0),
                tipo=TipoVoce(tipo) if tipo else TipoVoce.ONORARIO,
            ))
        except (ValueError, TypeError):
            pass

    valore_controversia = _parse_numero(f.get("valore_controversia"), 0.0)
    tariffa_oraria = _parse_numero(f.get("tariffa_oraria"), 0.0)
    ore_stimate = _parse_numero(f.get("ore_stimate"), 0.0)
    anticipazioni = _anticipazioni_totali_wizard(f)
    tipo_compenso, compenso_a_tempo = _compenso_a_tempo_da_form(f)
    if compenso_a_tempo.get("errors"):
        flash(" ".join(compenso_a_tempo["errors"]), "danger")
        return redirect(url_for("preventivi.wizard"))
    _aggiungi_voce_compenso_a_tempo(voci, compenso_a_tempo)

    if not voci:
        flash("Aggiungi almeno una voce al preventivo.", "danger")
        return redirect(url_for("preventivi.wizard"))
    for warning in compenso_a_tempo.get("warnings") or []:
        flash(warning, "warning")

    cfg = current_app.config
    log_calcolo = _contesto_log_wizard_da_form(f, compenso_a_tempo)
    log_calcolo = _arricchisci_log_cliente_anagrafico(log_calcolo, get_clienti().get(id_cliente))
    raw_fonti_tassonomia = (f.get("fonti_tassonomia_json", "") or "").strip()
    try:
        fonti_tassonomia = json.loads(raw_fonti_tassonomia) if raw_fonti_tassonomia else []
    except (TypeError, ValueError, json.JSONDecodeError):
        fonti_tassonomia = []
    if not isinstance(fonti_tassonomia, list):
        fonti_tassonomia = []
    classificazioni_tassonomiche = _classificazioni_tassonomiche_da_raw(
        f.get("classificazioni_tassonomiche_json", "")
    )
    p = gp.crea_preventivo(
        id_cliente=id_cliente,
        oggetto=oggetto,
        voci=voci,
        creato_da=g.utente_corrente.username if g.utente_corrente else "",
        id_fascicolo=f.get("id_fascicolo", "").strip() or None,
        data_emissione=f.get("data_emissione") or date.today().isoformat(),
        data_scadenza=f.get("data_scadenza", "").strip() or None,
        applica_cassa=_flag_from_form(f, "applica_cassa", default=True),
        applica_iva=_flag_from_form(f, "applica_iva", default=True),
        anticipazioni_art15=anticipazioni,
        note=f.get("note", "").strip(),
        id_pratica=f.get("id_pratica", "").strip(),
        area_pratica=f.get("area_pratica", "").strip(),
        area_tassonomica=f.get("area_tassonomica", "").strip(),
        macro_area_tassonomica=f.get("macro_area_tassonomica", "").strip(),
        sottobranca_tassonomica=f.get("sottobranca_tassonomica", "").strip(),
        tassonomia_codice=f.get("tassonomia_codice", "").strip(),
        procedura_operativa_codice=f.get("procedura_operativa_codice", "").strip(),
        fonti_tassonomia=fonti_tassonomia,
        classificazioni_tassonomiche=classificazioni_tassonomiche,
        tipo_compenso=tipo_compenso,
        tipo_procedimento=f.get("tipo_procedimento", "").strip(),
        valore_controversia=valore_controversia,
        tariffa_oraria=tariffa_oraria,
        ore_stimate=ore_stimate,
        criterio_arrotondamento_orario=f.get("criterio_arrotondamento_orario", "").strip() or "ora_frazione_oltre_30",
        minuti_stimati=_parse_intero(f.get("minuti_stimati"), 0),
        ore_fatturabili_calcolate=float(compenso_a_tempo.get("ore_fatturabili") or 0.0),
        compenso_orario_base=float(compenso_a_tempo.get("compenso_base") or 0.0),
        massimale_ore=_parse_numero(f.get("massimale_ore"), 0.0),
        soglia_preapprovazione_ore=_parse_numero(f.get("soglia_preapprovazione_ore"), 0.0),
        richiede_consenso_superamento_soglia=True,
        attivita_orarie_incluse=f.get("attivita_orarie_incluse", "").strip(),
        attivita_orarie_escluse=f.get("attivita_orarie_escluse", "").strip(),
        warning_compenso_orario=list(compenso_a_tempo.get("warnings") or []),
        complessita=f.get("complessita", "").strip(),
        log_calcolo=log_calcolo,
        studio_piva=cfg.get("STUDIO_PIVA", ""),
        studio_cf=cfg.get("STUDIO_CF", ""),
        studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
        clausola_controversie_attiva=_flag_from_form(f, "clausola_controversie_attiva"),
        clausola_controversie_modello=f.get("clausola_controversie_modello", "").strip(),
        clausola_controversie_testo=f.get("clausola_controversie_testo", "").strip(),
        clausola_controversie_trattativa_individuale=_flag_from_form(
            f, "clausola_controversie_trattativa_individuale"
        ),
        clausola_controversie_fonte=f.get("clausola_controversie_fonte", "").strip(),
    )

    _wizard_log_story(
        "preventivo creato",
        numero=p.numero,
        cliente=id_cliente,
        id_pratica=f.get("id_pratica", "").strip(),
        voci=len(voci),
        classificazioni_extra=len(classificazioni_tassonomiche),
        totale=p.totale,
    )

    # Conferimento immediato?
    if _flag_from_form(f, "genera_conferimento"):
        cliente_corrente = get_clienti().get(id_cliente)
        if _cliente_da_completare(cliente_corrente):
            flash(
                "Preventivo creato. Prima del conferimento completa l'anagrafica cliente: "
                + ", ".join(_campi_cliente_mancanti(cliente_corrente)),
                "warning",
            )
            return redirect(
                _url_completa_cliente(
                    id_cliente,
                    next_url=url_for("preventivi.nuovo_conferimento", id_cliente=id_cliente, id_preventivo=p.id, from_page="preventivo"),
                )
            )
        conferimento = None
        avvocato = f.get("avvocato_referente", "").strip() or cfg.get("STUDIO_NOME", "Studio Legale")
        try:
            compenso_pattuito = _parse_numero(f.get("compenso_pattuito"), p.totale)
        except (ValueError, TypeError):
            compenso_pattuito = p.totale
        conferimento = gp.crea_conferimento(
            id_cliente=id_cliente,
            oggetto=oggetto,
            avvocato_referente=avvocato,
            creato_da=g.utente_corrente.username if g.utente_corrente else "",
            id_preventivo=p.id,
            id_fascicolo=f.get("id_fascicolo", "").strip() or None,
            compenso_pattuito=compenso_pattuito,
            id_pratica=f.get("id_pratica", "").strip(),
            area_pratica=f.get("area_pratica", "").strip(),
            area_tassonomica=f.get("area_tassonomica", "").strip(),
            macro_area_tassonomica=f.get("macro_area_tassonomica", "").strip(),
            sottobranca_tassonomica=f.get("sottobranca_tassonomica", "").strip(),
            tassonomia_codice=f.get("tassonomia_codice", "").strip(),
            procedura_operativa_codice=f.get("procedura_operativa_codice", "").strip(),
            fonti_tassonomia=fonti_tassonomia,
            classificazioni_tassonomiche=classificazioni_tassonomiche,
            tipo_compenso=tipo_compenso,
            tipo_procedimento=f.get("tipo_procedimento", "").strip(),
            tariffa_oraria=tariffa_oraria,
            criterio_arrotondamento_orario=f.get("criterio_arrotondamento_orario", "").strip() or "ora_frazione_oltre_30",
            massimale_ore=_parse_numero(f.get("massimale_ore"), 0.0),
            soglia_preapprovazione_ore=_parse_numero(f.get("soglia_preapprovazione_ore"), 0.0),
            richiede_consenso_superamento_soglia=True,
            attivita_orarie_incluse=f.get("attivita_orarie_incluse", "").strip(),
            attivita_orarie_escluse=f.get("attivita_orarie_escluse", "").strip(),
            warning_compenso_orario=list(compenso_a_tempo.get("warnings") or []),
            informativa_art13_resa=_flag_from_form(f, "informativa_art13_resa"),
            clausola_adr_resa=_flag_from_form(f, "clausola_adr_resa"),
            clausola_controversie_attiva=_flag_from_form(f, "clausola_controversie_attiva"),
            clausola_controversie_modello=f.get("clausola_controversie_modello", "").strip(),
            clausola_controversie_testo=f.get("clausola_controversie_testo", "").strip(),
            clausola_controversie_trattativa_individuale=_flag_from_form(
                f, "clausola_controversie_trattativa_individuale"
            ),
            studio_piva=cfg.get("STUDIO_PIVA", ""),
            studio_cf=cfg.get("STUDIO_CF", ""),
            studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
        )
        from pct.preventivi import StatoPreventivo
        gp.aggiorna_preventivo(p.id, stato=StatoPreventivo.CONVERTITO)
        _wizard_log_story(
            "conferimento creato dal wizard",
            numero_preventivo=p.numero,
            numero_conferimento=getattr(conferimento, "numero", ""),
            cliente=id_cliente,
            apri_fascicolo_guidato=_flag_from_form(f, "apri_fascicolo_guidato") and not p.id_fascicolo,
        )
        if _flag_from_form(f, "apri_fascicolo_guidato") and not p.id_fascicolo:
            flash(
                f"Preventivo {p.numero} e conferimento incarico creati. Completa ora l'apertura guidata del fascicolo.",
                "success",
            )
            return redirect(
                _url_onboarding_fascicolo(
                    id_cliente,
                    id_preventivo=p.id,
                    id_conferimento=conferimento.id if conferimento else "",
                    from_page=f.get("from_page", "").strip() or "wizard",
                )
            )
        flash(f"Preventivo {p.numero} e conferimento incarico creati.", "success")
    else:
        flash(f"Preventivo {p.numero} creato.", "success")

    return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=p.id))


# ================================================================ Generazione PDF preventivo

def _genera_pdf_preventivo(p, cliente, fascicolo, config) -> io.BytesIO:
    """Genera PDF professionale del preventivo con ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    except ImportError:
        buf = io.BytesIO()
        buf.write(f"Preventivo {p.numero}\nTotale: € {p.totale:.2f}".encode())
        buf.seek(0)
        return buf

    PRIMARY   = colors.HexColor("#1a3a5c")
    LIGHT_BG  = colors.HexColor("#f4f6fa")
    GRAY_TEXT = colors.HexColor("#6b7280")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=20*mm, rightMargin=20*mm,
                             topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    style_body  = ParagraphStyle("body",  parent=styles["Normal"], fontSize=9, leading=13)
    style_small = ParagraphStyle("small", parent=styles["Normal"], fontSize=7.5, leading=11, textColor=GRAY_TEXT)
    style_h1    = ParagraphStyle("h1",    parent=styles["Normal"], fontSize=18, leading=22, textColor=PRIMARY, fontName="Helvetica-Bold")
    style_h2    = ParagraphStyle("h2",    parent=styles["Normal"], fontSize=11, leading=14, textColor=PRIMARY, fontName="Helvetica-Bold")
    style_bold  = ParagraphStyle("bold",  parent=style_body, fontName="Helvetica-Bold")

    studio_nome = config.get("STUDIO_NOME", "IUSENTRA")
    studio_piva = p.studio_piva or config.get("STUDIO_PIVA", "")
    studio_cf   = p.studio_cf   or config.get("STUDIO_CF", "")
    studio_ind  = p.studio_indirizzo or config.get("STUDIO_INDIRIZZO", "")

    nome_cliente = cliente.nome_completo if cliente else "Cliente sconosciuto"

    story = []

    # Header
    header_data = [[
        Paragraph(f"<b>{studio_nome}</b>", style_h2),
        Paragraph("PREVENTIVO PROFESSIONALE", ParagraphStyle(
            "ptit", parent=style_h1, alignment=TA_RIGHT)),
    ]]
    ht = Table(header_data, colWidths=["60%", "40%"])
    ht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(ht)

    info_right_txt = f"<b>N. {p.numero}</b><br/>Data: {p.data_emissione}"
    if p.data_scadenza:
        info_right_txt += f"<br/>Valido fino al: {p.data_scadenza}"
    info_left_txt = studio_ind or ""
    if studio_piva:
        info_left_txt += f"<br/>P.IVA {studio_piva}"
    if studio_cf:
        info_left_txt += f"<br/>C.F. {studio_cf}"

    info_tbl = Table([[
        Paragraph(info_left_txt.strip("<br/>"), style_small),
        Paragraph(info_right_txt, ParagraphStyle("itr", parent=style_small, alignment=TA_RIGHT)),
    ]], colWidths=["60%", "40%"])
    info_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(Spacer(1, 4*mm))
    story.append(info_tbl)
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 4*mm))

    # Destinatario
    story.append(Paragraph("Spettabile", style_small))
    story.append(Paragraph(f"<b>{nome_cliente}</b>", style_h2))
    if fascicolo:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f"Rif. pratica: {fascicolo.titolo}" + (f" · RG {fascicolo.numero_rg}" if fascicolo.numero_rg else ""),
            style_small))
    story.append(Spacer(1, 4*mm))

    # Oggetto
    story.append(Paragraph(f"<b>Oggetto:</b> {p.oggetto}", style_body))
    story.append(Spacer(1, 4*mm))

    # Parametri incarico (se presenti)
    params = []
    if p.tipo_compenso:
        params.append(("Tipo di compenso", p.tipo_compenso))
    if p.tipo_procedimento:
        params.append(("Tipo procedimento", p.tipo_procedimento))
    if p.valore_controversia:
        params.append(("Valore controversia", f"€ {p.valore_controversia:,.2f}"))
    if p.tariffa_oraria:
        ore_txt = f" × {p.ore_stimate:.1f} ore = € {p.tariffa_oraria * p.ore_stimate:,.2f}" if p.ore_stimate else ""
        params.append(("Tariffa oraria", f"€ {p.tariffa_oraria:,.2f}/ora{ore_txt}"))
    if params:
        params_data = [[Paragraph(f"<b>{k}</b>", style_small),
                        Paragraph(v, style_small)] for k, v in params]
        pt = Table(params_data, colWidths=["40%", "60%"])
        pt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(pt)
        story.append(Spacer(1, 2*mm))
    if p.complessita:
        story.append(Paragraph(
            f"<i>Complessità stimata (art. 13 co. 5 L. 247/2012):</i> {p.complessita}",
            style_small))
        story.append(Spacer(1, 2*mm))
    story.append(Spacer(1, 4*mm))

    # Voci
    story.append(Paragraph("Voci del preventivo", style_h2))
    story.append(Spacer(1, 2*mm))

    voci_data = [[
        Paragraph("<b>Descrizione</b>", style_bold),
        Paragraph("<b>Tipo</b>", ParagraphStyle("tb", parent=style_bold, alignment=TA_RIGHT)),
        Paragraph("<b>Importo</b>", ParagraphStyle("ib", parent=style_bold, alignment=TA_RIGHT)),
    ]]
    for v in p.voci:
        voci_data.append([
            Paragraph(v.descrizione, style_body),
            Paragraph(v.tipo.value, ParagraphStyle("tv", parent=style_small, alignment=TA_RIGHT)),
            Paragraph(f"€ {v.importo:,.2f}", ParagraphStyle("iv", parent=style_body, alignment=TA_RIGHT)),
        ])

    voci_tbl = Table(voci_data, colWidths=["60%", "20%", "20%"])
    voci_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(voci_tbl)
    story.append(Spacer(1, 4*mm))

    # Riepilogo
    rows = [("Imponibile", f"€ {p.imponibile:,.2f}")]
    if p.applica_cassa:
        rows.append(("Contributo Previdenziale CPA (4%)", f"€ {p.cassa_forense:,.2f}"))
    if p.applica_iva:
        rows.append((f"IVA 22% su € {p.base_iva:,.2f}", f"€ {p.iva:,.2f}"))
    if p.anticipazioni_art15:
        rows.append((
            "Anticipazioni in nome e per conto (Art. 15 DPR 633/72)",
            f"€ {p.anticipazioni_art15:,.2f}"
        ))
    rows.append(("TOTALE", f"€ {p.totale:,.2f}"))

    rie_data = [
        [Paragraph(label, ParagraphStyle(
            "rl", parent=style_body,
            fontName="Helvetica-Bold" if "TOTALE" in label else "Helvetica",
            textColor=PRIMARY if "TOTALE" in label else colors.black,
            fontSize=11 if "TOTALE" in label else 9)),
         Paragraph(valore, ParagraphStyle(
            "rv", parent=style_body, alignment=TA_RIGHT,
            fontName="Helvetica-Bold" if "TOTALE" in label else "Helvetica",
            textColor=PRIMARY if "TOTALE" in label else colors.black,
            fontSize=11 if "TOTALE" in label else 9))]
        for label, valore in rows
    ]
    rie_tbl = Table(rie_data, colWidths=["75%", "25%"])
    rie_tbl.setStyle(TableStyle([
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, PRIMARY),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BG),
    ]))
    story.append(rie_tbl)
    story.append(Spacer(1, 6*mm))

    calc_summary = riepilogo_contesto_economico(p.log_calcolo)
    if calc_summary:
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("Tracciabilita del calcolo", style_h2))
        meta_rows = []
        if calc_summary.get("source_label"):
            meta_rows.append(f"<b>Origine:</b> {calc_summary['source_label']}")
        if calc_summary.get("pratica_label"):
            meta_rows.append(f"<b>Tipologia:</b> {calc_summary['pratica_label']}")
        regola_label = calc_summary.get("regola_tariffaria_label") or calc_summary.get("regola_tariffaria")
        if regola_label:
            meta_rows.append(f"<b>Regola:</b> {regola_label}")
        if calc_summary.get("grado_sede"):
            meta_rows.append(f"<b>Grado / sede:</b> {calc_summary['grado_sede']}")
        if calc_summary.get("scaglione"):
            meta_rows.append(f"<b>Scaglione:</b> {calc_summary['scaglione']}")
        if calc_summary.get("complessita"):
            meta_rows.append(f"<b>Complessita:</b> {calc_summary['complessita']}")
        audit = calc_summary.get("audit_tariffario") or {}
        if audit.get("compliance_label"):
            audit_parts = [f"<b>Conformita tariffaria:</b> {audit['compliance_label']}"]
            if audit.get("table_code"):
                table_label = str(audit.get("table_label") or "").strip()
                audit_parts.append(
                    f"Tabella {audit['table_code']}" + (f" - {table_label}" if table_label else "")
                )
            if audit.get("compliance_note"):
                audit_parts.append(str(audit["compliance_note"]))
            meta_rows.append(" - ".join(part for part in audit_parts if part))
        if calc_summary.get("adr_accordo"):
            meta_rows.append("<b>ADR:</b> accordo finale con maggiorazioni normative attive")
        elif calc_summary.get("adr_enabled"):
            meta_rows.append("<b>ADR:</b> procedura con variazioni di fase")
        if calc_summary.get("variazioni_fasi"):
            meta_rows.append(
                "<b>Variazioni:</b> "
                + " · ".join(row["label"] for row in calc_summary["variazioni_fasi"])
            )
        for row in meta_rows:
            story.append(Paragraph(row, style_small))
        story.append(Spacer(1, 3*mm))

    if p.clausola_controversie_attiva and p.clausola_controversie_testo:
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("Clausola proposta per il conferimento", style_h2))
        if p.clausola_controversie_fonte:
            story.append(Paragraph(
                f"<b>Fonte modello:</b> {escape(p.clausola_controversie_fonte)}",
                style_small,
            ))
            story.append(Spacer(1, 1*mm))
        story.append(Paragraph(
            escape(p.clausola_controversie_testo).replace("\n", "<br/>"),
            style_small,
        ))
        if p.clausola_controversie_trattativa_individuale:
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(
                "Trattativa individuale sulla clausola dichiarata come gia svolta.",
                style_small,
            ))
        story.append(Spacer(1, 3*mm))

    # Note + disclaimer
    if p.note:
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(p.note, style_small))
        story.append(Spacer(1, 3*mm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "Il presente preventivo ha valore indicativo ed è soggetto a variazioni in base all'effettivo sviluppo della pratica.",
        ParagraphStyle("disc", parent=style_small, alignment=TA_CENTER, fontName="Helvetica-Oblique")))
    story.append(Spacer(1, 4*mm))

    # Footer
    footer_txt = studio_nome
    if studio_piva:
        footer_txt += f" — P.IVA {studio_piva}"
    story.append(Paragraph(footer_txt, ParagraphStyle(
        "footer", parent=style_small, alignment=TA_CENTER)))

    doc.build(story)
    buf.seek(0)
    return buf


# ================================================================ Generazione PDF conferimento incarico

def _genera_pdf_conferimento(c, cliente, fascicolo, preventivo, config) -> io.BytesIO:
    """Genera lettera di conferimento di incarico in formato PDF."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_JUSTIFY
    except ImportError:
        buf = io.BytesIO()
        buf.write(f"Conferimento Incarico {c.numero}".encode())
        buf.seek(0)
        return buf

    PRIMARY   = colors.HexColor("#1a3a5c")
    LIGHT_BG  = colors.HexColor("#f4f6fa")
    GRAY_TEXT = colors.HexColor("#6b7280")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=25*mm, rightMargin=25*mm,
                             topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    style_body  = ParagraphStyle("body",  parent=styles["Normal"], fontSize=10, leading=15)
    style_just  = ParagraphStyle("just",  parent=style_body, alignment=TA_JUSTIFY)
    style_small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=11, textColor=GRAY_TEXT)
    style_h1    = ParagraphStyle("h1",    parent=styles["Normal"], fontSize=16, leading=20, textColor=PRIMARY, fontName="Helvetica-Bold")
    style_h2    = ParagraphStyle("h2",    parent=styles["Normal"], fontSize=11, leading=14, textColor=PRIMARY, fontName="Helvetica-Bold")
    style_bold  = ParagraphStyle("bold",  parent=style_body, fontName="Helvetica-Bold")

    studio_nome = config.get("STUDIO_NOME", "IUSENTRA")
    studio_piva = c.studio_piva or config.get("STUDIO_PIVA", "")
    studio_cf   = c.studio_cf   or config.get("STUDIO_CF", "")
    studio_ind  = c.studio_indirizzo or config.get("STUDIO_INDIRIZZO", "")

    nome_cliente = cliente.nome_completo if cliente else "Cliente sconosciuto"

    story = []

    # Header studio
    header_data = [[
        Paragraph(f"<b>{studio_nome}</b>", style_h2),
        Paragraph("CONFERIMENTO DI INCARICO", ParagraphStyle(
            "ctit", parent=style_h1, alignment=TA_RIGHT, fontSize=14)),
    ]]
    ht = Table(header_data, colWidths=["55%", "45%"])
    ht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(ht)

    info_left_txt = studio_ind or ""
    if studio_piva:
        info_left_txt += f"<br/>P.IVA {studio_piva}"
    if studio_cf:
        info_left_txt += f"<br/>C.F. {studio_cf}"
    info_right_txt = f"<b>N. {c.numero}</b><br/>Data: {c.data_incarico}"

    info_tbl = Table([[
        Paragraph(info_left_txt.strip("<br/>"), style_small),
        Paragraph(info_right_txt, ParagraphStyle("itr", parent=style_small, alignment=TA_RIGHT)),
    ]], colWidths=["55%", "45%"])
    info_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(Spacer(1, 3*mm))
    story.append(info_tbl)
    story.append(Spacer(1, 3*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 5*mm))

    # Destinatario
    story.append(Paragraph("Spettabile", style_small))
    story.append(Paragraph(f"<b>{nome_cliente}</b>", style_h2))
    story.append(Spacer(1, 6*mm))

    # Corpo lettera
    story.append(Paragraph(f"<b>Oggetto:</b> Conferimento incarico professionale — {c.oggetto}", style_bold))
    story.append(Spacer(1, 5*mm))

    # Dati avvocato (iscrizione albo)
    albo_txt = ""
    if c.numero_iscrizione_albo:
        albo_txt = f", iscritto all'Albo degli Avvocati n. {c.numero_iscrizione_albo}"
        if c.ordine_avvocati:
            albo_txt += f" dell'Ordine di {c.ordine_avvocati}"
    story.append(Paragraph(
        f"Con la presente il/la sottoscritto/a <b>{nome_cliente}</b> conferisce incarico professionale "
        f"all'<b>Avv. {c.avvocato_referente}</b>{albo_txt} dello {studio_nome} per la trattazione della seguente questione:",
        style_just))
    story.append(Spacer(1, 3*mm))

    # Riquadro oggetto
    obj_tbl = Table([[Paragraph(c.oggetto, style_body)]], colWidths=["100%"])
    obj_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("BOX",        (0, 0), (-1, -1), 0.5, PRIMARY),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(obj_tbl)
    story.append(Spacer(1, 5*mm))

    if fascicolo:
        story.append(Paragraph(
            f"Il presente incarico è riferito alla pratica: <b>{fascicolo.titolo}</b>" +
            (f" (RG {fascicolo.numero_rg})" if fascicolo.numero_rg else "") + ".",
            style_just))
        story.append(Spacer(1, 3*mm))

    # Tipo compenso + procedimento
    if c.tipo_compenso or c.tipo_procedimento:
        info_parts = []
        if c.tipo_compenso:
            info_parts.append(f"Modalità di compenso: <b>{c.tipo_compenso}</b>")
        if c.tipo_procedimento:
            info_parts.append(f"Tipo di procedimento: <b>{c.tipo_procedimento}</b>")
        story.append(Paragraph(" — ".join(info_parts) + ".", style_body))
        story.append(Spacer(1, 3*mm))

    # Compenso
    if c.compenso_pattuito > 0:
        if is_compenso_a_tempo(c.tipo_compenso) and c.tariffa_oraria > 0:
            criterio = c.criterio_arrotondamento_orario or "ora_frazione_oltre_30"
            incluse = escape(c.attivita_orarie_incluse or "attivita professionali necessarie allo svolgimento dell'incarico")
            escluse = escape(c.attivita_orarie_escluse or "spese vive, anticipazioni e attivita non espressamente incluse")
            soglia = f"{c.soglia_preapprovazione_ore:g} ore" if c.soglia_preapprovazione_ore else "la soglia concordata"
            massimale = f"{c.massimale_ore:g} ore" if c.massimale_ore else "il massimale concordato"
            story.append(Paragraph(
                "Le parti pattuiscono espressamente che il compenso professionale sia determinato a tempo, "
                "ai sensi dell'art. 22-bis D.M. 55/2014, sulla base della tariffa oraria di "
                f"<b>EUR {c.tariffa_oraria:,.2f}/ora</b>, oltre accessori di legge. "
                f"Il tempo e computato secondo il seguente criterio: <b>{escape(criterio)}</b>. "
                f"Sono incluse le seguenti attivita: {incluse}. Sono escluse: {escluse}. "
                f"Oltre la soglia di {soglia} o oltre il massimale di {massimale} sara richiesta preventiva "
                "approvazione del cliente, salvo urgenze motivate. "
                f"L'importo base indicativo dell'incarico e <b>EUR {c.compenso_pattuito:,.2f}</b>.",
                style_just))
        else:
            story.append(Paragraph(
                f"Il compenso professionale concordato per la prestazione e pari a "
                f"<b>EUR {c.compenso_pattuito:,.2f}</b> (oltre Cassa Forense 4% ed IVA 22%), "
                f"salvo adeguamento in ragione della complessita e dello sviluppo della pratica.",
                style_just))
    else:
        story.append(Paragraph(
            "Il compenso professionale sarà determinato al termine dell'incarico in conformità ai "
            "parametri forensi di cui al D.M. 55/2014 e successive modifiche, salvo preventivo concordato separatamente.",
            style_just))

    # Patto di palmario
    if c.patto_palmario and c.quota_palmario_pct:
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(
            f"Le parti convengono altresì un patto di palmario pari al "
            f"<b>{c.quota_palmario_pct:.1f}% del risultato utile conseguito</b>, "
            f"ai sensi dell'art. 13 co. 3 L. 247/2012.",
            style_just))

    story.append(Spacer(1, 3*mm))

    # Rif. preventivo
    if preventivo:
        story.append(Paragraph(
            f"Rif. preventivo n. <b>{preventivo.numero}</b> del {preventivo.data_emissione}.",
            style_small))
        story.append(Spacer(1, 3*mm))

    if c.clausola_controversie_attiva and c.clausola_controversie_testo:
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph("<b>Clausola di risoluzione delle controversie</b>", style_bold))
        story.append(Spacer(1, 2*mm))
        if c.clausola_controversie_fonte:
            story.append(Paragraph(
                f"<b>Fonte modello:</b> {escape(c.clausola_controversie_fonte)}",
                style_small,
            ))
            story.append(Spacer(1, 1*mm))
        story.append(Paragraph(
            escape(c.clausola_controversie_testo).replace("\n", "<br/>"),
            style_just,
        ))
        if c.clausola_controversie_trattativa_individuale:
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(
                "Le parti dichiarano che la clausola e stata oggetto di trattativa individuale documentabile.",
                style_small,
            ))
        story.append(Spacer(1, 3*mm))

    # Note
    if c.note:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(escape(c.note).replace("\n", "<br/>"), style_just))
        story.append(Spacer(1, 3*mm))

    # Obblighi informativi art. 13 L. 247/2012
    obbl = []
    if c.informativa_art13_resa:
        obbl.append("✓ Il professionista ha reso l'informativa di cui all'art. 13 co. 5 L. 247/2012 "
                    "(grado di complessità, oneri ipotizzabili, dati polizza RC).")
    if c.clausola_adr_resa:
        obbl.append("✓ Il professionista ha informato il cliente della possibilità di ricorrere "
                    "a procedure di mediazione / negoziazione assistita (art. 5 D.Lgs. 28/2010).")
    if obbl:
        story.append(Spacer(1, 4*mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph("<b>Obblighi informativi</b>", style_bold))
        story.append(Spacer(1, 2*mm))
        for o in obbl:
            story.append(Paragraph(o, style_small))

    story.append(Spacer(1, 8*mm))

    # Firme
    firme_data = [[
        Paragraph(f"<b>Per lo Studio</b><br/><br/><br/>Avv. {c.avvocato_referente}", style_body),
        Paragraph("<b>Il/La Cliente</b><br/><br/><br/>_________________________", style_body),
    ]]
    firme_tbl = Table(firme_data, colWidths=["50%", "50%"])
    firme_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    story.append(firme_tbl)
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(f"Luogo e data: ________________________, {c.data_incarico}", style_body))

    # Footer
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_TEXT))
    story.append(Spacer(1, 2*mm))
    footer_txt = studio_nome
    if studio_piva:
        footer_txt += f" — P.IVA {studio_piva}"
    story.append(Paragraph(footer_txt, ParagraphStyle(
        "footer", parent=style_small, alignment=TA_CENTER)))

    doc.build(story)
    buf.seek(0)
    return buf
