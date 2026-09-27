"""
web/blueprints/portale.py — Portale self-service per il cliente.

URL base: /portale/<token>
Nessuna autenticazione richiesta — l'accesso è garantito dal token sicuro.

Le pagine GET aprono la pagina React (`PortaleTokenApp`, dati da
`/api/v1/pubblico/portale/<token>/...`); con `?_legacy=1` resta la vista
classica. Verifica del token, dati e azioni sono nei servizi
`portale_cliente_legacy_*`, condivisi con le API JSON.
"""
from __future__ import annotations

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, send_file, url_for, current_app)

from web.helpers import get_fascicoli
from web.services.portale_cliente_legacy_azioni import (
    RisorsaNonTrovata,
    accetta_preventivo as _azione_accetta_preventivo,
    aggiorna_recapiti,
    carica_documenti,
    firma_conferimento as _azione_firma_conferimento,
    registra_consenso_privacy,
)
from web.services.portale_cliente_legacy_contesto import (
    REQUISITI_SEZIONE,
    AccessoPortaleNegato,
    fascicoli_cliente as _fascicoli_cliente,
    gestore_portale as _get_portale,
    richiedi_permessi,
    risolvi_studio_portale,
    verifica_contesto,
)
from web.services.portale_cliente_legacy_dati import (
    arricchisci_economici,
    conferimento_del_cliente,
    dati_home,
    documenti_economici_cliente as _documenti_economici_cliente,
    oggi_roma,
    parcella_del_cliente,
    preventivo_del_cliente,
)
from web.services.pubblico_token_shell import render_portale_token_shell, vista_classica_richiesta

portale = Blueprint("portale", __name__, url_prefix="/portale")

__all__ = ["_documenti_economici_cliente", "_fascicoli_cliente", "_get_portale", "portale"]

_TITOLI_SEZIONE = {
    "home": "Benvenuto",
    "privacy": "Consenso Privacy",
    "documenti": "Carica documenti",
    "economici": "Documenti economici",
    "anagrafica": "I miei dati",
}


# ---------------------------------------------------------------- studio del link

@portale.before_request
def _studio_dal_token():
    """Il cliente arriva senza sessione: lo studio si ricava dal token del link.

    Con più studi sulla stessa installazione, senza questo passo il portale
    leggeva l'archivio comune (`PORTALE_DB` globale) invece di quello dello
    studio che ha creato il link.
    """
    token = str((request.view_args or {}).get("token") or "").strip()
    if token:
        risolvi_studio_portale(token)
    return None


# ---------------------------------------------------------------- helper locale

def _studio_nome() -> str:
    return current_app.config.get("STUDIO_NOME", "IUSENTRA")


def _download_requested() -> bool:
    value = (request.args.get("download") or "").strip().lower()
    return value in {"1", "true", "yes", "download"}


def _carica_contesto(token: str):
    """Verifica token e carica portale + cliente. Abort 404/410 se non valido."""
    try:
        contesto = verifica_contesto(token)
    except AccessoPortaleNegato as exc:
        abort(exc.status)
    return contesto.gestore, contesto.portale, contesto


def _richiedi(contesto, *requisiti) -> None:
    try:
        richiedi_permessi(contesto, *requisiti)
    except AccessoPortaleNegato as exc:
        abort(exc.status)


def _shell_react(token: str, sezione: str):
    """Pagina React della sezione: stesso esito HTTP della vista classica (410/403)."""
    try:
        contesto = verifica_contesto(token, registra_accesso=False)
        richiedi_permessi(contesto, *REQUISITI_SEZIONE[sezione])
    except AccessoPortaleNegato as exc:
        if exc.status == 410:
            return render_portale_token_shell(
                token, sezione, titolo="Link non valido", studio_nome=_studio_nome(), status=410, stato="scaduto",
            )
        if exc.status == 403:
            return render_portale_token_shell(
                token, sezione, titolo=_TITOLI_SEZIONE[sezione], studio_nome=_studio_nome(), status=403, stato="negato",
            )
        abort(exc.status)
    return render_portale_token_shell(token, sezione, titolo=_TITOLI_SEZIONE[sezione], studio_nome=_studio_nome())


def _url_azione(token: str, azione: dict) -> str:
    if azione["kind"] == "preventivo":
        return url_for("portale.accetta_preventivo", token=token, id_preventivo=azione["id"])
    return url_for("portale.firma_conferimento", token=token, id_conferimento=azione["id"])


def _azioni_con_url(token: str, azioni: list[dict]) -> list[dict]:
    return [{**azione, "action_url": _url_azione(token, azione)} for azione in azioni]


def _enrich_economici_portale(portale_obj, cliente, dati):
    token = (request.view_args or {}).get("token")
    return _azioni_con_url(token, arricchisci_economici(portale_obj, cliente, dati))


def _documento_o_404(trovato):
    documento, gestore = trovato
    if documento is None:
        abort(404)
    return documento, gestore


# ================================================================ HOME

@portale.route("/<token>")
def home(token: str):
    if not vista_classica_richiesta():
        return _shell_react(token, "home")
    gp, p, contesto = _carica_contesto(token)
    dati = dati_home(contesto)
    return render_template(
        "portale/home.html",
        token=token,
        p=p,
        cliente=contesto.cliente,
        fascicoli=dati["fascicoli"],
        tracker_map=dati["tracker_map"],
        appuntamenti=dati["appuntamenti"],
        scadenze=dati["scadenze"],
        economici=dati["economici"],
        azioni_richieste=_azioni_con_url(token, dati["azioni_richieste"]),
        oggi=dati["oggi"],
        studio_nome=_studio_nome(),
    )


# ================================================================ PRIVACY

@portale.route("/<token>/privacy", methods=["GET", "POST"])
def privacy(token: str):
    if request.method == "GET" and not vista_classica_richiesta():
        return _shell_react(token, "privacy")
    gp, p, contesto = _carica_contesto(token)
    _richiedi(contesto, *REQUISITI_SEZIONE["privacy"])

    if request.method == "POST":
        esito = registra_consenso_privacy(contesto, request.form.get("consenso") == "1")
        if not esito.ok:
            return render_template(
                "portale/privacy.html",
                token=token, p=p, cliente=contesto.cliente,
                errore=esito.errore,
                studio_nome=_studio_nome(),
            )
        return render_template(
            "portale/privacy_ok.html",
            token=token, p=p, cliente=contesto.cliente,
            studio_nome=_studio_nome(),
        )

    return render_template(
        "portale/privacy.html",
        token=token, p=p, cliente=contesto.cliente,
        errore=None,
        studio_nome=_studio_nome(),
    )


# ================================================================ DOCUMENTI

def _pagina_documenti(token, p, contesto, fascicoli, *, errore=None):
    return render_template(
        "portale/documenti.html",
        token=token, p=p, cliente=contesto.cliente,
        fascicoli=fascicoli,
        max_mb=p.permessi.max_upload_mb,
        studio_nome=_studio_nome(),
        errore=errore,
    )


@portale.route("/<token>/documenti", methods=["GET"])
def documenti(token: str):
    if not vista_classica_richiesta():
        return _shell_react(token, "documenti")
    gp, p, contesto = _carica_contesto(token)
    _richiedi(contesto, *REQUISITI_SEZIONE["documenti"])
    fascicoli = _fascicoli_cliente(contesto.cliente.id) if p.permessi.vedi_fascicoli else []
    return _pagina_documenti(token, p, contesto, fascicoli)


@portale.route("/<token>/documenti/carica", methods=["POST"])
def carica_documento(token: str):
    gp, p, contesto = _carica_contesto(token)
    _richiedi(contesto, *REQUISITI_SEZIONE["documenti"])

    esito = carica_documenti(
        contesto,
        request.files.getlist("files[]"),
        request.form.get("id_fascicolo", ""),
        request.form.get("note", ""),
    )
    if esito.errore:
        pagina = _pagina_documenti(token, p, contesto, _fascicoli_cliente(contesto.cliente.id), errore=esito.errore)
        return (pagina, esito.status) if esito.status != 200 else pagina

    return render_template(
        "portale/documenti_ok.html",
        token=token, p=p, cliente=contesto.cliente,
        caricati=esito.caricati, errori=esito.errori,
        studio_nome=_studio_nome(),
    )


# ================================================================ ECONOMICI

@portale.route("/<token>/economici", methods=["GET"])
def economici(token: str):
    if not vista_classica_richiesta():
        return _shell_react(token, "economici")
    gp, p, contesto = _carica_contesto(token)
    _richiedi(contesto, *REQUISITI_SEZIONE["economici"])

    dati = _documenti_economici_cliente(contesto.cliente.id)
    azioni_richieste = _enrich_economici_portale(p, contesto.cliente, dati)
    return render_template(
        "portale/economici.html",
        token=token,
        p=p,
        cliente=contesto.cliente,
        preventivi=dati["preventivi"],
        conferimenti=dati["conferimenti"],
        parcelle=dati["parcelle"],
        timeline=dati["timeline"],
        stats=dati["stats"],
        azioni_richieste=azioni_richieste,
        oggi=oggi_roma(),
        studio_nome=_studio_nome(),
    )


def _flash_esito(esito) -> None:
    for categoria, messaggio in esito.messaggi:
        flash(messaggio, categoria)


def _url_sezione(token: str, sezione: str) -> str:
    endpoint = "portale.home" if sezione == "home" else "portale.economici"
    return url_for(endpoint, token=token)


@portale.route("/<token>/preventivi/<id_preventivo>/accetta", methods=["POST"])
def accetta_preventivo(token: str, id_preventivo: str):
    _, p, contesto = _carica_contesto(token)
    _richiedi(contesto, ("vedi_economici", False), ("accetta_preventivi", True))
    try:
        esito = _azione_accetta_preventivo(contesto, id_preventivo)
    except RisorsaNonTrovata:
        abort(404)
    _flash_esito(esito)
    return redirect(_url_sezione(token, esito.sezione))


@portale.route("/<token>/conferimenti/<id_conferimento>/firma", methods=["POST"])
def firma_conferimento(token: str, id_conferimento: str):
    _, p, contesto = _carica_contesto(token)
    _richiedi(contesto, ("vedi_economici", False), ("firma_conferimenti", True))
    try:
        esito = _azione_firma_conferimento(contesto, id_conferimento)
    except RisorsaNonTrovata:
        abort(404)
    _flash_esito(esito)
    return redirect(_url_sezione(token, esito.sezione))


def _invia_pdf(buf, nome_file: str):
    return send_file(buf, mimetype="application/pdf", as_attachment=_download_requested(), download_name=nome_file)


@portale.route("/<token>/preventivi/<id_preventivo>/pdf", methods=["GET"])
def pdf_preventivo(token: str, id_preventivo: str):
    _, p, contesto = _carica_contesto(token)
    _richiedi(contesto, *REQUISITI_SEZIONE["economici"])

    preventivo, _ = _documento_o_404(preventivo_del_cliente(contesto.cliente.id, id_preventivo))
    fascicolo = get_fascicoli().get(preventivo.id_fascicolo) if preventivo.id_fascicolo else None
    from web.blueprints.preventivi import _genera_pdf_preventivo

    buf = _genera_pdf_preventivo(preventivo, contesto.cliente, fascicolo, current_app.config)
    return _invia_pdf(buf, f"preventivo_{preventivo.numero.replace('/', '-')}.pdf")


@portale.route("/<token>/conferimenti/<id_conferimento>/pdf", methods=["GET"])
def pdf_conferimento(token: str, id_conferimento: str):
    _, p, contesto = _carica_contesto(token)
    _richiedi(contesto, *REQUISITI_SEZIONE["economici"])

    conferimento, gp_prev = _documento_o_404(conferimento_del_cliente(contesto.cliente.id, id_conferimento))
    fascicolo = get_fascicoli().get(conferimento.id_fascicolo) if conferimento.id_fascicolo else None
    preventivo = gp_prev.get_preventivo(conferimento.id_preventivo) if conferimento.id_preventivo else None
    from web.blueprints.preventivi import _genera_pdf_conferimento

    buf = _genera_pdf_conferimento(conferimento, contesto.cliente, fascicolo, preventivo, current_app.config)
    return _invia_pdf(buf, f"conferimento_{conferimento.numero.replace('/', '-')}.pdf")


@portale.route("/<token>/parcelle/<id_parcella>/pdf", methods=["GET"])
def pdf_parcella(token: str, id_parcella: str):
    _, p, contesto = _carica_contesto(token)
    _richiedi(contesto, *REQUISITI_SEZIONE["economici"])

    parcella, _ = _documento_o_404(parcella_del_cliente(contesto.cliente.id, id_parcella))
    fascicolo = get_fascicoli().get(parcella.id_fascicolo) if parcella.id_fascicolo else None
    from web.blueprints.fatturazione import _genera_pdf

    buf = _genera_pdf(parcella, contesto.cliente, fascicolo, current_app.config)
    return _invia_pdf(buf, f"parcella_{parcella.numero.replace('/', '-')}.pdf")


# ================================================================ ANAGRAFICA

@portale.route("/<token>/anagrafica", methods=["GET", "POST"])
def anagrafica(token: str):
    if request.method == "GET" and not vista_classica_richiesta():
        return _shell_react(token, "anagrafica")
    gp, p, contesto = _carica_contesto(token)
    _richiedi(contesto, *REQUISITI_SEZIONE["anagrafica"])

    successo = False
    if request.method == "POST":
        _richiedi(contesto, ("modifica_anagrafica", False))
        aggiorna_recapiti(contesto, request.form)
        successo = True

    return render_template(
        "portale/anagrafica.html",
        token=token, p=p, cliente=contesto.cliente,
        errore=None, successo=successo,
        studio_nome=_studio_nome(),
    )


# ================================================================ 410 GONE

# Solo per il portale: prima il gestore valeva per ogni 410 dell'applicazione.
@portale.errorhandler(410)
def link_scaduto(e):
    return render_template(
        "portale/scaduto.html",
        studio_nome=_studio_nome(),
    ), 410
