"""API JSON pubbliche dei link personali: portale del cliente e link di pagamento.

URL base: /api/v1/pubblico
  /portale/<token>/...    — dati e azioni del portale storico (`PortaleTokenApp`)
  /pagamenti/<token>/...  — checkout del link di pagamento (`PagamentoLinkApp`)

Il token nell'indirizzo è l'unica credenziale: ogni endpoint lo verifica come
le pagine storiche (410 se non valido o scaduto, stessi permessi della scheda
portale), ricava lo studio dal token, registra l'accesso e legge solo i dati
del cliente del link. Le scritture sono protette dal CSRF come quelle del
Portale Cliente pubblico (`security_runtime._CSRF_PROTECTED_ENDPOINTS`).
Dominio unico con le pagine classiche: `web/services/portale_cliente_legacy_*`
e `web/services/pagamenti_link_*`.
"""

from __future__ import annotations

from functools import wraps
from typing import Any

from flask import Blueprint, current_app, jsonify, request, url_for

from web.services.pagamenti_link_azioni import (
    avvia_pagamento,
    gestore_pagamenti,
    link_del_token,
    risolvi_studio_pagamento,
    vista_link,
)
from web.services.pagamenti_link_payload import payload_esito, payload_vista
from web.services.portale_cliente_legacy_azioni import (
    RisorsaNonTrovata,
    accetta_preventivo,
    aggiorna_recapiti,
    carica_documenti,
    firma_conferimento,
    registra_consenso_privacy,
)
from web.services.portale_cliente_legacy_contesto import (
    REQUISITI_SEZIONE,
    AccessoPortaleNegato,
    fascicoli_visibili,
    richiedi_permessi,
    risolvi_studio_portale,
    verifica_contesto,
)
from web.services.portale_cliente_legacy_dati import arricchisci_economici, dati_home, documenti_economici_cliente
from web.services.portale_cliente_legacy_payload import (
    payload_anagrafica,
    payload_documenti,
    payload_economici,
    payload_home,
    payload_privacy,
)

api_v1_portale_token = Blueprint("api_v1_portale_token", __name__)

PROVIDER_NOTI = {"stripe", "paypal", "satispay", "sumup", "bonifico"}
CAMPI_RECAPITI = ("cellulare", "telefono", "email")


def _errore(status: int, codice: str, messaggio: str):
    return jsonify({"ok": False, "code": codice, "message": messaggio}), status


@api_v1_portale_token.before_request
def _studio_del_link():
    token = str((request.view_args or {}).get("token") or "").strip()
    if not token:
        return None
    if str(request.endpoint or "").startswith("api_v1_portale_token.pagamento_"):
        risolvi_studio_pagamento(token)
    else:
        risolvi_studio_portale(token)
    return None


@api_v1_portale_token.after_request
def _senza_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@api_v1_portale_token.errorhandler(413)
def _file_troppo_grande(_errore_http):
    return _errore(413, "file_troppo_grande", "I file superano la dimensione massima accettata dal server.")


def _risposta_json(funzione):
    """Errori di accesso, risorse di altri clienti e guasti come JSON, mai pagine HTML."""

    @wraps(funzione)
    def gestita(*args: Any, **kwargs: Any):
        try:
            return funzione(*args, **kwargs)
        except AccessoPortaleNegato as exc:
            return _errore(exc.status, exc.codice, exc.messaggio)
        except RisorsaNonTrovata:
            return _errore(404, "non_trovato", "Documento non disponibile per questo accesso.")
        except Exception:
            current_app.logger.exception("API pubblica %s non completata", request.endpoint)
            return _errore(500, "errore_interno", "Operazione non completata. Riprova o contatta lo studio.")

    return gestita


def _contesto(token: str, sezione: str, *altri: tuple[str, bool]):
    contesto = verifica_contesto(token)
    richiedi_permessi(contesto, *REQUISITI_SEZIONE[sezione], *altri)
    return contesto


def _dati_richiesta() -> dict[str, Any]:
    dati = request.get_json(silent=True)
    if isinstance(dati, dict):
        return dati
    return request.form.to_dict()


def _messaggi(esito) -> list[dict[str, str]]:
    return [{"categoria": categoria, "testo": testo} for categoria, testo in esito.messaggi]


# ================================================================ PORTALE

@api_v1_portale_token.get("/portale/<token>")
@_risposta_json
def portale_home(token: str):
    contesto = _contesto(token, "home")
    return jsonify(payload_home(contesto, token, dati_home(contesto)))


@api_v1_portale_token.get("/portale/<token>/privacy")
@_risposta_json
def portale_privacy(token: str):
    return jsonify(payload_privacy(_contesto(token, "privacy")))


@api_v1_portale_token.post("/portale/<token>/privacy")
@_risposta_json
def portale_privacy_consenso(token: str):
    contesto = _contesto(token, "privacy")
    valore = _dati_richiesta().get("consenso")
    esito = registra_consenso_privacy(contesto, valore is True or str(valore) == "1")
    if not esito.ok:
        return _errore(422, "consenso_mancante", esito.errore)
    return jsonify({**payload_privacy(contesto), "sezione": "privacy_ok", "message": "Consenso registrato."})


@api_v1_portale_token.get("/portale/<token>/documenti")
@_risposta_json
def portale_documenti(token: str):
    contesto = _contesto(token, "documenti")
    return jsonify(payload_documenti(contesto, fascicoli_visibili(contesto)))


@api_v1_portale_token.post("/portale/<token>/documenti/upload")
@_risposta_json
def portale_documenti_upload(token: str):
    contesto = _contesto(token, "documenti")
    esito = carica_documenti(
        contesto,
        request.files.getlist("files[]"),
        request.form.get("id_fascicolo", ""),
        request.form.get("note", ""),
    )
    if esito.errore:
        codice = "pratica_non_disponibile" if esito.status == 403 else "nessun_file"
        return _errore(esito.status if esito.status != 200 else 422, codice, esito.errore)
    return jsonify({"ok": True, "sezione": "documenti_ok", "caricati": esito.caricati, "errori": esito.errori})


@api_v1_portale_token.get("/portale/<token>/economici")
@_risposta_json
def portale_economici(token: str):
    contesto = _contesto(token, "economici")
    dati = documenti_economici_cliente(contesto.cliente.id)
    azioni = arricchisci_economici(contesto.portale, contesto.cliente, dati)
    return jsonify(payload_economici(contesto, token, dati, azioni))


@api_v1_portale_token.post("/portale/<token>/preventivi/<id_preventivo>/accetta")
@_risposta_json
def portale_preventivo_accetta(token: str, id_preventivo: str):
    contesto = _contesto(token, "economici", ("accetta_preventivi", True))
    esito = accetta_preventivo(contesto, id_preventivo)
    return jsonify({"ok": esito.ok, "messaggi": _messaggi(esito), "sezione": esito.sezione}), (200 if esito.ok else 409)


@api_v1_portale_token.post("/portale/<token>/conferimenti/<id_conferimento>/firma")
@_risposta_json
def portale_conferimento_firma(token: str, id_conferimento: str):
    contesto = _contesto(token, "economici", ("firma_conferimenti", True))
    esito = firma_conferimento(contesto, id_conferimento)
    return jsonify({"ok": esito.ok, "messaggi": _messaggi(esito), "sezione": esito.sezione})


@api_v1_portale_token.get("/portale/<token>/anagrafica")
@_risposta_json
def portale_anagrafica(token: str):
    return jsonify(payload_anagrafica(_contesto(token, "anagrafica")))


@api_v1_portale_token.post("/portale/<token>/anagrafica")
@_risposta_json
def portale_anagrafica_aggiorna(token: str):
    contesto = _contesto(token, "anagrafica", ("modifica_anagrafica", False))
    dati = _dati_richiesta()
    if any(dati.get(campo) is not None and not isinstance(dati.get(campo), str) for campo in CAMPI_RECAPITI):
        return _errore(422, "recapiti_non_validi", "I recapiti devono essere testo.")
    aggiorna_recapiti(contesto, {campo: dati.get(campo) for campo in CAMPI_RECAPITI})
    return jsonify({**payload_anagrafica(contesto), "message": "Dati aggiornati con successo."})


# ================================================================ PAGAMENTI

@api_v1_portale_token.get("/pagamenti/<token>")
@_risposta_json
def pagamento_checkout(token: str):
    gp = gestore_pagamenti()
    stato = vista_link(gp, token)
    return jsonify(payload_vista(stato, gp)), stato.status


def _link_scaduto():
    return _errore(410, "link_non_valido", "Questo link di pagamento non è più valido o è scaduto. Contatta lo studio per richiederne uno nuovo.")


@api_v1_portale_token.post("/pagamenti/<token>/avvia")
@_risposta_json
def pagamento_avvia(token: str):
    gp = gestore_pagamenti()
    stato = vista_link(gp, token)
    if stato.vista != "checkout":
        return _link_scaduto()
    lp = stato.link
    esito = avvia_pagamento(gp, lp, str(_dati_richiesta().get("provider") or ""))
    if esito.tipo == "redirect":
        return jsonify({"ok": True, "tipo": "redirect", "url": esito.url})
    if esito.tipo == "sumup":
        # Il widget SumUp usa solo l'identificativo del checkout: nessuna chiave al browser.
        url_esito = url_for("pagamenti.successo", token=token) + "?provider=sumup"
        return jsonify({"ok": True, "tipo": "sumup", "checkout_id": esito.checkout_id, "url_esito": url_esito})
    if esito.tipo == "bonifico":
        return jsonify({"ok": True, "tipo": "bonifico", "url_esito": esito.url, "esito": payload_esito(lp, "bonifico", gp)})
    if esito.tipo == "provider_non_valido":
        return _errore(400, "provider_non_valido", esito.messaggio)
    return _errore(502, "gestore_non_disponibile", esito.messaggio)


@api_v1_portale_token.get("/pagamenti/<token>/esito")
@_risposta_json
def pagamento_esito(token: str):
    gp = gestore_pagamenti()
    lp = link_del_token(gp, token)
    if not lp:
        return _link_scaduto()
    provider = str(request.args.get("provider") or "").strip()
    return jsonify(payload_esito(lp, provider if provider in PROVIDER_NOTI else "", gp))


__all__ = ["api_v1_portale_token"]
