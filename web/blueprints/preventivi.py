"""
web/blueprints/preventivi.py — Preventivi e conferimenti di incarico.

URL base: /preventivi/
Richiede autenticazione tramite g.utente_corrente (gestita da app.py).
"""
from __future__ import annotations

import io
import json
from datetime import date, timedelta

from flask import (Blueprint, abort, flash, g, redirect,
                   render_template, request, send_file, url_for, current_app)

from web.helpers import get_clienti, get_fascicoli

preventivi = Blueprint("preventivi", __name__, url_prefix="/preventivi")


# ---------------------------------------------------------------- helpers

def _get_gp():
    from pct.preventivi import GestionePreventivi
    return GestionePreventivi(
        db_path=current_app.config.get("PREVENTIVI_DB", "./preventivi/preventivi.json")
    )


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


def _cliente_da_completare(cliente) -> bool:
    return bool(cliente and not getattr(cliente, "profilo_completo_per_conferimento", True))


def _campi_cliente_mancanti(cliente) -> list[str]:
    if not cliente:
        return []
    return list(getattr(cliente, "campi_mancanti_per_conferimento", []) or [])


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
            return redirect(url_for("login"))
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

    tutti_prev = gp.tutti_preventivi()
    tutti_conf = gp.tutti_conferimenti()

    prev_anno = [p for p in tutti_prev if p.data_emissione.startswith(str(anno))]
    conf_anno = [c for c in tutti_conf if c.data_incarico.startswith(str(anno))]

    if stato_filtro:
        prev_anno = [p for p in prev_anno if p.stato.value == stato_filtro]
        conf_anno = [c for c in conf_anno if c.stato.value == stato_filtro]
    if cliente_filtro:
        prev_anno = [p for p in prev_anno if p.id_cliente == cliente_filtro]
        conf_anno = [c for c in conf_anno if c.id_cliente == cliente_filtro]

    clienti_map = {c.id: c for c in get_clienti().tutti()}

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
                    importo=float(imp or 0),
                    tipo=TipoVoce(tipo) if tipo else TipoVoce.ONORARIO,
                ))
            except (ValueError, TypeError):
                pass

        if not voci:
            flash("Aggiungi almeno una voce.", "danger")
            return redirect(request.url)

        try:
            valore_controversia = float(f.get("valore_controversia") or 0)
        except (ValueError, TypeError):
            valore_controversia = 0.0
        try:
            tariffa_oraria = float(f.get("tariffa_oraria") or 0)
        except (ValueError, TypeError):
            tariffa_oraria = 0.0
        try:
            ore_stimate = float(f.get("ore_stimate") or 0)
        except (ValueError, TypeError):
            ore_stimate = 0.0

        cfg = current_app.config
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
            anticipazioni_art15=float(f.get("anticipazioni_art15") or 0),
            note=f.get("note", "").strip(),
            tipo_compenso=f.get("tipo_compenso", "").strip(),
            tipo_procedimento=f.get("tipo_procedimento", "").strip(),
            valore_controversia=valore_controversia,
            tariffa_oraria=tariffa_oraria,
            ore_stimate=ore_stimate,
            complessita=f.get("complessita", "").strip(),
            studio_piva=cfg.get("STUDIO_PIVA", ""),
            studio_cf=cfg.get("STUDIO_CF", ""),
            studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
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
        abort(404)
    cliente = get_clienti().get(p.id_cliente)
    fascicolo = get_fascicoli().get(p.id_fascicolo) if p.id_fascicolo else None
    conferimenti = gp.conferimenti_per_preventivo(id_preventivo)
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
    return render_template(
        "preventivi/dettaglio_preventivo.html",
        p=p,
        cliente=cliente,
        fascicolo=fascicolo,
        conferimenti=conferimenti,
        url_crea_conferimento=url_crea_conferimento,
        url_apri_fascicolo=url_apri_fascicolo,
        url_completa_cliente=url_completa_cliente,
        suggerisci_conferimento=suggerisci_conferimento,
        suggerisci_fascicolo=suggerisci_fascicolo,
        cliente_da_completare=cliente_da_completare,
        campi_cliente_mancanti=campi_cliente_mancanti,
        studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
        oggi=date.today(),
    )


# ================================================================ CAMBIA STATO PREVENTIVO

@preventivi.route("/p/<id_preventivo>/stato", methods=["POST"])
@_richiedi_login
def cambia_stato_preventivo(id_preventivo: str):
    from pct.preventivi import StatoPreventivo
    gp = _get_gp()
    p = gp.get_preventivo(id_preventivo)
    if not p:
        abort(404)
    stato_str = request.form.get("stato", "")
    try:
        nuovo_stato = StatoPreventivo(stato_str)
    except ValueError:
        flash("Stato non valido.", "danger")
        return redirect(url_for("preventivi.dettaglio_preventivo", id_preventivo=id_preventivo))
    gp.cambia_stato_preventivo(id_preventivo, nuovo_stato)
    flash(f"Stato aggiornato: {nuovo_stato.value}.", "success")
    if nuovo_stato == StatoPreventivo.ACCETTATO:
        flash(
            "Preventivo accettato: il prossimo passo consigliato e creare il conferimento di incarico e aprire il fascicolo guidato.",
            "success",
        )
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
        id_cliente = f.get("id_cliente", "").strip()
        if not id_cliente:
            flash("Seleziona un cliente.", "danger")
            return redirect(request.url)

        oggetto = f.get("oggetto", "").strip()
        if not oggetto:
            flash("Inserisci l'oggetto dell'incarico.", "danger")
            return redirect(request.url)

        avvocato = f.get("avvocato_referente", "").strip()
        if not avvocato:
            flash("Inserisci il nome dell'avvocato referente.", "danger")
            return redirect(request.url)

        try:
            compenso = float(f.get("compenso_pattuito", 0) or 0)
        except (ValueError, TypeError):
            compenso = 0.0
        try:
            tariffa_oraria_c = float(f.get("tariffa_oraria") or 0)
        except (ValueError, TypeError):
            tariffa_oraria_c = 0.0
        try:
            quota_palmario = float(f.get("quota_palmario_pct") or 0)
        except (ValueError, TypeError):
            quota_palmario = 0.0
        id_preventivo = f.get("id_preventivo", "").strip()
        id_fascicolo = f.get("id_fascicolo", "").strip()
        apri_fascicolo_guidato = bool(f.get("apri_fascicolo_guidato")) and not id_fascicolo

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
            numero_iscrizione_albo=f.get("numero_iscrizione_albo", "").strip(),
            ordine_avvocati=f.get("ordine_avvocati", "").strip(),
            tipo_compenso=f.get("tipo_compenso", "").strip(),
            tipo_procedimento=f.get("tipo_procedimento", "").strip(),
            tariffa_oraria=tariffa_oraria_c,
            patto_palmario=bool(f.get("patto_palmario")),
            quota_palmario_pct=quota_palmario,
            informativa_art13_resa=bool(f.get("informativa_art13_resa")),
            clausola_adr_resa=bool(f.get("clausola_adr_resa")),
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

    # GET
    clienti = gc.tutti()
    cliente_sel = gc.get(id_cliente) if id_cliente else None
    fascicoli = []
    if cliente_sel:
        fascicoli = [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]

    id_preventivo_pre = request.args.get("id_preventivo", "")
    preventivo_pre = gp.get_preventivo(id_preventivo_pre) if id_preventivo_pre else None
    from_page = request.args.get("from_page", "")
    id_fascicolo_pre = request.args.get("id_fascicolo", "")
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
        cliente_da_completare=cliente_da_completare,
        campi_cliente_mancanti=campi_cliente_mancanti,
        url_completa_cliente=url_completa_cliente,
        oggi=date.today(),
        from_page=from_page,
        id_fascicolo_pre=id_fascicolo_pre,
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
    return render_template(
        "preventivi/dettaglio_conferimento.html",
        c=c,
        cliente=cliente,
        fascicolo=fascicolo,
        preventivo=preventivo,
        url_apri_fascicolo=url_apri_fascicolo,
        url_completa_cliente=url_completa_cliente,
        cliente_da_completare=cliente_da_completare,
        campi_cliente_mancanti=campi_cliente_mancanti,
        studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
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
      var_<nome_fase>     — variazione % per fase (es. var_attivazione=110 → +10%)
    """
    from flask import jsonify
    from pct.tariffario import calcola_compenso, Materia, Grado, Fase

    tipo_proc        = request.args.get("tipo_procedimento", "")
    tipo_mediazione  = request.args.get("tipo_mediazione", "mediazione")
    valore           = float(request.args.get("valore", 0) or 0)
    fasi_raw         = request.args.get("fasi", "")
    grado_raw        = request.args.get("grado", "Tribunale")
    bonus_tel        = request.args.get("bonus_telematico", "0") == "1"
    incl_spese       = request.args.get("spese_generali", "0") == "1"
    try:
        perc_sg = float(request.args.get("perc_spese_generali", "15") or "15") / 100.0
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
        "Corte d'Appello":   Grado.CORTE_APPELLO,
        "Corte di Cassazione": Grado.CASSAZIONE,
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
                variazioni_fasi[fase_label] = float(raw_val) / 100.0
            except (ValueError, TypeError):
                pass

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
        )
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
            "totale":            ris.totale_con_spese if incl_spese else ris.totale_base,
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
    from pct.motore_preventivo import AREE, catalogo_wizard
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
        "valore": request.args.get("valore", "").strip(),
        "grado": request.args.get("grado", "").strip(),
        "livello_compenso": request.args.get("livello_compenso", "base").strip() or "base",
        "fasi": fasi_prefill,
        "bonus_telematico": request.args.get("bonus_telematico", "0") == "1",
        "spese_generali": request.args.get("spese_generali", "1") == "1",
        "perc_spese_generali": request.args.get("perc_spese_generali", "15").strip() or "15",
        "applica_cpa": request.args.get("applica_cpa", "1") == "1",
        "applica_iva": request.args.get("applica_iva", "1") == "1",
        "anticipazioni": request.args.get("anticipazioni", "").strip(),
        "tariffa_oraria": request.args.get("tariffa_oraria", "").strip(),
        "ore_stimate": request.args.get("ore_stimate", "").strip(),
        "oggetto": request.args.get("oggetto", "").strip(),
        "note": request.args.get("note", "").strip(),
        "accessori": [],
        "esborsi": [],
        "manual_voci": [],
        "has_accessori_prefill": False,
        "has_esborsi_prefill": False,
        "has_manual_voci_prefill": False,
        "auto_calcola": request.args.get("auto_calcola", "").strip() == "1",
    }
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
    return render_template(
        "preventivi/wizard.html",
        catalogo_per_area=catalogo_wizard(),
        aree=AREE,
        clienti=gc.tutti(),
        cliente_sel=cliente_sel,
        id_cliente_pre=id_cliente,
        id_fascicolo_pre=id_fascicolo_pre,
        fascicolo_pre_context=_contesto_fascicolo_wizard(fascicolo_pre) if fascicolo_pre else None,
        wizard_prefill=wizard_prefill,
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
    from pct.tariffario import Fase, Grado, LivelloCompenso

    try:
        id_pratica = request.args.get("id_pratica", "")
        valore = float(request.args.get("valore", 0) or 0)
        grado_raw = request.args.get("grado", "")
        livello_raw = request.args.get("livello_compenso", "base")
        fasi_raw = request.args.get("fasi", "")
        bonus_tel = request.args.get("bonus_telematico", "0") == "1"
        incl_spese = request.args.get("spese_generali", "1") == "1"
        try:
            perc_sg = float(request.args.get("perc_spese_generali", "15") or "15") / 100.0
        except (ValueError, TypeError):
            perc_sg = 0.15
        applica_cpa = request.args.get("applica_cpa", "1") == "1"
        applica_iva = request.args.get("applica_iva", "1") == "1"
        anticipazioni = float(request.args.get("anticipazioni", 0) or 0)

        if not id_pratica:
            return jsonify({"errore": "id_pratica mancante"}), 200

        tp = get_tipo_pratica(id_pratica)
        if not tp:
            return jsonify({"errore": f"Tipologia non trovata: {id_pratica}"}), 200

        _mappa_grado = {
            "Giudice di Pace": Grado.GIUDICE_DI_PACE,
            "Tribunale": Grado.TRIBUNALE,
            "Corte d'Appello": Grado.CORTE_APPELLO,
            "Corte di Cassazione": Grado.CASSAZIONE,
            "TAR": Grado.TAR,
            "Consiglio di Stato": Grado.CONSIGLIO_DI_STATO,
            "CGT di primo grado": Grado.CGT_PRIMO_GRADO,
            "CGT di secondo grado": Grado.CGT_SECONDO_GRADO,
            "Fuori giudizio": Grado.FUORI_GIUDIZIO,
            "Procedura ADR": Grado.PROCEDURA_ADR,
        }
        grado = _mappa_grado.get(grado_raw) if grado_raw else None
        try:
            livello = LivelloCompenso(str(livello_raw or "base").lower())
        except ValueError:
            livello = LivelloCompenso.BASE

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
        fasi = [_mappa_fase[k] for k in fasi_raw.split(",") if k.strip() in _mappa_fase] or None

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
                    variazioni_fasi[fase_label] = float(raw_val) / 100.0
                except (ValueError, TypeError):
                    pass

        ris = motore_calcola(
            id_pratica=id_pratica,
            valore_controversia=valore,
            grado=grado,
            fasi=fasi,
            livello_compenso=livello,
            bonus_telematico=bonus_tel,
            includi_spese_generali=incl_spese,
            perc_spese_generali=perc_sg,
            variazioni_fasi=variazioni_fasi or None,
            applica_cpa=applica_cpa,
            applica_iva=applica_iva,
            anticipazioni=anticipazioni,
        )

        dm = ris.calcolo_dm55
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
            "bonus_telematico":      dm.bonus_telematico,
            "spese_generali":        dm.spese_generali,
            "perc_spese_generali":   int(round(dm.perc_spese_generali * 100)),
            "onorario_base":         ris.onorario_base,
            "onorario_selezionato":  ris.onorario_selezionato,
            "cpa":                   ris.cpa,
            "base_iva":              ris.base_iva,
            "iva":                   ris.iva,
            "anticipazioni":         ris.anticipazioni,
            "totale":                ris.totale,
            "applica_cpa":           ris.applica_cpa,
            "applica_iva":           ris.applica_iva,
            "livello_compenso":      ris.livello_compenso,
            "nota":                  dm.note,
            "base_normativa":        tp.base_normativa,
        })
    except Exception as e:
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
        if f.get("cliente_rapido_attivo"):
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
                importo=float(imp or 0),
                tipo=TipoVoce(tipo) if tipo else TipoVoce.ONORARIO,
            ))
        except (ValueError, TypeError):
            pass

    if not voci:
        flash("Aggiungi almeno una voce al preventivo.", "danger")
        return redirect(url_for("preventivi.wizard"))

    try:
        valore_controversia = float(f.get("valore_controversia") or 0)
    except (ValueError, TypeError):
        valore_controversia = 0.0
    try:
        tariffa_oraria = float(f.get("tariffa_oraria") or 0)
    except (ValueError, TypeError):
        tariffa_oraria = 0.0
    try:
        ore_stimate = float(f.get("ore_stimate") or 0)
    except (ValueError, TypeError):
        ore_stimate = 0.0
    try:
        anticipazioni = float(f.get("anticipazioni_art15") or 0)
    except (ValueError, TypeError):
        anticipazioni = 0.0

    cfg = current_app.config
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
        anticipazioni_art15=anticipazioni,
        note=f.get("note", "").strip(),
        id_pratica=f.get("id_pratica", "").strip(),
        area_pratica=f.get("area_pratica", "").strip(),
        tipo_compenso=f.get("tipo_compenso", "").strip(),
        tipo_procedimento=f.get("tipo_procedimento", "").strip(),
        valore_controversia=valore_controversia,
        tariffa_oraria=tariffa_oraria,
        ore_stimate=ore_stimate,
        complessita=f.get("complessita", "").strip(),
        studio_piva=cfg.get("STUDIO_PIVA", ""),
        studio_cf=cfg.get("STUDIO_CF", ""),
        studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
    )

    # Conferimento immediato?
    if f.get("genera_conferimento"):
        conferimento = None
        avvocato = f.get("avvocato_referente", "").strip() or cfg.get("STUDIO_NOME", "Studio Legale")
        try:
            compenso_pattuito = float(f.get("compenso_pattuito") or p.totale)
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
            tipo_compenso=f.get("tipo_compenso", "").strip(),
            tipo_procedimento=f.get("tipo_procedimento", "").strip(),
            informativa_art13_resa=bool(f.get("informativa_art13_resa")),
            clausola_adr_resa=bool(f.get("clausola_adr_resa")),
            studio_piva=cfg.get("STUDIO_PIVA", ""),
            studio_cf=cfg.get("STUDIO_CF", ""),
            studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
        )
        from pct.preventivi import StatoPreventivo
        gp.aggiorna_preventivo(p.id, stato=StatoPreventivo.CONVERTITO)
        if bool(f.get("apri_fascicolo_guidato")) and not p.id_fascicolo:
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
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    except ImportError:
        buf = io.BytesIO()
        buf.write(f"Preventivo {p.numero}\nTotale: € {p.totale:.2f}".encode())
        buf.seek(0)
        return buf

    PRIMARY   = colors.HexColor("#1a3a5c")
    ACCENT    = colors.HexColor("#c8972b")
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

    studio_nome = config.get("STUDIO_NOME", "Studio Legale PCT")
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
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT, TA_JUSTIFY
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

    studio_nome = config.get("STUDIO_NOME", "Studio Legale PCT")
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
        if c.tipo_compenso and "orari" in c.tipo_compenso.lower() and c.tariffa_oraria > 0:
            story.append(Paragraph(
                f"Il compenso professionale concordato è a <b>tariffa oraria di € {c.tariffa_oraria:,.2f}/ora</b> "
                f"(oltre Cassa Forense 4% ed IVA 22%), con importo base indicativo di "
                f"<b>€ {c.compenso_pattuito:,.2f}</b>.",
                style_just))
        else:
            story.append(Paragraph(
                f"Il compenso professionale concordato per la prestazione è pari a "
                f"<b>€ {c.compenso_pattuito:,.2f}</b> (oltre Cassa Forense 4% ed IVA 22%), "
                f"salvo adeguamento in ragione della complessità e dello sviluppo della pratica.",
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

    # Note
    if c.note:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(c.note, style_just))
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
