"""
web/blueprints/pagamenti.py — Gestione pagamenti digitali.

URL base:
  /impostazioni/pagamenti  — pannello configurazione provider (avvocato)
  /paga/<token>            — pagina checkout cliente (no auth)
  /webhooks/stripe         — webhook Stripe
  /webhooks/paypal         — webhook PayPal
  /webhooks/satispay       — webhook Satispay
  /webhooks/sumup          — webhook SumUp
  /webhooks/<gestore>/<slug> — webhook con lo studio nell'indirizzo (solo con più studi)
"""
from __future__ import annotations

import json

from flask import (Blueprint, abort, flash, g, jsonify, redirect,
                   render_template, request, url_for, current_app)
from pct.pagamenti_verifica import (
    paypal_pagamento_confermato,
    satispay_pagamento_confermato,
    sumup_pagamento_confermato,
)
from web.helpers import get_fatturazione as _shared_get_fatturazione, get_pagamenti as _shared_get_pagamenti
from web.services.pagamenti_link_azioni import (
    aggiorna_parcella_pagata,
    avvia_pagamento as _avvia_presso_gestore,
    entra_studio_webhook,
    indirizzo_webhook,
    risolvi_studio_pagamento,
    risolvi_studio_webhook,
    verifica_ritorno,
    vista_link,
)
from web.services.pubblico_token_shell import render_pagamento_shell, vista_classica_richiesta

pagamenti = Blueprint("pagamenti", __name__)

# Pagine del cliente raggiunte con il token del link (i webhook restano esclusi).
_ENDPOINT_CON_TOKEN = {"pagamenti.checkout", "pagamenti.avvia_pagamento", "pagamenti.successo"}


@pagamenti.before_request
def _studio_dal_link():
    """Con più studi, lo studio si ricava dal token del link (come nel portale)."""
    if request.endpoint not in _ENDPOINT_CON_TOKEN:
        return None
    token = str((request.view_args or {}).get("token") or "").strip()
    if token:
        risolvi_studio_pagamento(token)
    return None


# ---------------------------------------------------------------- helpers

def _get_gp():
    return _shared_get_pagamenti()


def _richiedi_login(f):
    from functools import wraps
    @wraps(f)
    def w(*a, **kw):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


def _update_parcella_pagata(id_parcella: str, metodo: str):
    """Segna la parcella come PAGATA nel modulo fatturazione."""
    aggiorna_parcella_pagata(id_parcella, metodo)


# ================================================================ PANNELLO IMPOSTAZIONI

@pagamenti.route("/impostazioni/pagamenti", methods=["GET", "POST"])
@_richiedi_login
def impostazioni_pagamenti():
    from pct.pagamenti import (ConfigPagamenti, StripeConfig, PayPalConfig,
                                SatispayConfig, SumUpConfig, BonificoConfig)
    gp = _get_gp()

    if request.method == "POST":
        f = request.form
        cfg = ConfigPagamenti(
            stripe=StripeConfig(
                abilitato=bool(f.get("stripe_abilitato")),
                modo=f.get("stripe_modo", "test"),
                pk_test=f.get("stripe_pk_test", "").strip(),
                sk_test=f.get("stripe_sk_test", "").strip(),
                pk_live=f.get("stripe_pk_live", "").strip(),
                sk_live=f.get("stripe_sk_live", "").strip(),
                webhook_secret=f.get("stripe_webhook_secret", "").strip(),
            ),
            paypal=PayPalConfig(
                abilitato=bool(f.get("paypal_abilitato")),
                modo=f.get("paypal_modo", "sandbox"),
                client_id=f.get("paypal_client_id", "").strip(),
                client_secret=f.get("paypal_client_secret", "").strip(),
            ),
            satispay=SatispayConfig(
                abilitato=bool(f.get("satispay_abilitato")),
                modo=f.get("satispay_modo", "sandbox"),
                key_id=f.get("satispay_key_id", "").strip(),
                private_key_pem=f.get("satispay_private_key", "").strip(),
            ),
            sumup=SumUpConfig(
                abilitato=bool(f.get("sumup_abilitato")),
                api_key=f.get("sumup_api_key", "").strip(),
                merchant_code=f.get("sumup_merchant_code", "").strip(),
            ),
            bonifico=BonificoConfig(
                abilitato=bool(f.get("bonifico_abilitato")),
                iban=f.get("bonifico_iban", "").strip(),
                intestazione=f.get("bonifico_intestazione", "").strip(),
                banca=f.get("bonifico_banca", "").strip(),
                note_aggiuntive=f.get("bonifico_note", "").strip(),
            ),
        )
        gp.aggiorna_config(cfg)
        flash("Impostazioni pagamenti salvate.", "success")
        return redirect(url_for("pagamenti.impostazioni_pagamenti"))

    if (request.args.get("_legacy") or "").strip().lower() not in {"1", "true", "si", "yes", "on"}:
        # Le impostazioni dei pagamenti stanno nella sezione Pagamenti di Impostazioni (React).
        return redirect("/impostazioni?tab=pagamenti")
    cfg = gp.config
    link_recenti = gp.tutti_link()[:20]
    return render_template(
        "pagamenti/impostazioni.html",
        cfg=cfg,
        link_recenti=link_recenti,
        provider_attivi=cfg.provider_attivi(),
        url_webhook_stripe=request.host_url.rstrip("/") + indirizzo_webhook("stripe"),
    )


# ================================================================ CREA LINK PAGAMENTO

@pagamenti.route("/fatturazione/<id_parcella>/link-pagamento", methods=["POST"])
@_richiedi_login
def crea_link_pagamento(id_parcella: str):
    gp = _get_gp()
    gf = _shared_get_fatturazione()
    p = gf.get(id_parcella)
    if not p:
        abort(404)
    giorni = int(request.form.get("giorni_validita", 30))
    # Revoca link precedente se esistente
    vecchio = gp.get_by_parcella(id_parcella)
    if vecchio:
        gp.segna_fallito(vecchio.id)
    lp = gp.crea_link(
        id_parcella=id_parcella,
        id_cliente=p.id_cliente,
        importo=p.totale,
        descrizione=f"Parcella {p.numero} — {current_app.config.get('STUDIO_NOME', 'IUSENTRA')}",
        giorni_validita=giorni,
    )
    link = request.host_url.rstrip("/") + url_for("pagamenti.checkout", token=lp.token)
    flash(f"Link di pagamento creato. Scade tra {giorni} giorni.", "success")
    # Salva in sessione per mostrarlo subito
    from flask import session
    session["pagamento_link_pending"] = {"link": link, "numero": p.numero, "totale": p.totale}
    return redirect(url_for("fatturazione.dettaglio", id_parcella=id_parcella))


# ================================================================ CHECKOUT CLIENTE (no auth)

def _studio_nome() -> str:
    return current_app.config.get("STUDIO_NOME", "IUSENTRA")


def _pagina_scaduto():
    return render_template("pagamenti/scaduto.html", studio_nome=_studio_nome()), 410


_TITOLI_VISTA = {"checkout": "Pagamento", "gia_pagato": "Già pagato", "scaduto": "Link scaduto"}


@pagamenti.route("/paga/<token>", methods=["GET"])
def checkout(token: str):
    gp = _get_gp()
    stato = vista_link(gp, token)
    if not vista_classica_richiesta():
        # Pagina React (PagamentoLinkApp): dati da /api/v1/pubblico/pagamenti/<token>.
        return render_pagamento_shell(
            token, stato.vista, titolo=_TITOLI_VISTA[stato.vista], studio_nome=_studio_nome(), status=stato.status,
        )
    if stato.vista == "scaduto":
        return _pagina_scaduto()
    if stato.vista == "gia_pagato":
        return render_template("pagamenti/gia_pagato.html", lp=stato.link, studio_nome=_studio_nome())

    lp = stato.link
    cfg = gp.config
    from web.helpers import get_clienti
    cliente = get_clienti().get(lp.id_cliente)

    return render_template(
        "pagamenti/checkout.html",
        lp=lp,
        cfg=cfg,
        cliente=cliente,
        studio_nome=_studio_nome(),
        provider_attivi=cfg.provider_attivi(),
    )


# ================================================================ AVVIA PAGAMENTO (POST dal checkout)

@pagamenti.route("/paga/<token>/avvia", methods=["POST"])
def avvia_pagamento(token: str):
    gp = _get_gp()
    stato = vista_link(gp, token)
    if stato.vista != "checkout":
        return _pagina_scaduto()
    lp = stato.link

    esito = _avvia_presso_gestore(gp, lp, request.form.get("provider", ""))
    if esito.tipo == "redirect":
        return redirect(esito.url)
    if esito.tipo == "bonifico":
        return redirect(esito.url)
    if esito.tipo == "sumup":
        # Vista classica del widget SumUp: la chiave del gestore non serve al
        # browser (il widget usa solo l'identificativo del checkout).
        return render_template(
            "pagamenti/sumup_checkout.html",
            lp=lp,
            checkout_id=esito.checkout_id,
            success_url=esito.url,
            studio_nome=_studio_nome(),
        )
    if esito.tipo == "provider_non_valido":
        abort(400)
    # Solo il messaggio per il cliente: il dettaglio dell'errore del gestore è nel log.
    flash(esito.messaggio, "danger")
    return redirect(url_for("pagamenti.checkout", token=token, _legacy=1))


# ================================================================ SUCCESSO

@pagamenti.route("/paga/<token>/successo", methods=["GET"])
def successo(token: str):
    gp = _get_gp()
    provider = request.args.get("provider", "")
    # PayPal (cattura dell'ordine) e Stripe (sessione) si verificano qui, al ritorno.
    lp = verifica_ritorno(gp, token, provider, request.args)
    if not lp:
        abort(404)
    if not vista_classica_richiesta():
        return render_pagamento_shell(
            token, "esito", titolo="Pagamento", studio_nome=_studio_nome(), provider=provider,
        )
    return render_template(
        "pagamenti/successo.html",
        lp=lp,
        provider=provider or lp.provider_usato or "",
        cfg_bonifico=gp.config.bonifico if provider == "bonifico" else None,
        studio_nome=_studio_nome(),
    )


# ================================================================ WEBHOOKS
#
# Con più studi il webhook arriva senza sessione: lo studio si ricava dal
# riferimento del link inviato dal gestore (lo stesso usato finora per trovare
# il link) oppure dall'indirizzo `/webhooks/<gestore>/<slug>`. Solo dopo, nel
# contesto di quello studio, si verifica la firma (Stripe) o si chiede conferma
# al gestore (PayPal, Satispay, SumUp) con le chiavi dello studio. A studio
# singolo nulla cambia.

def _nessuno_studio():
    """Link di nessuno studio: nulla da verificare né da registrare.

    Risposta 200 come per un link sconosciuto a studio singolo, così il gestore
    non ripete la notifica all'infinito.
    """
    return jsonify({"received": True}), 200


def _riferimento_stripe() -> str:
    """`link_id` nei metadata della sessione, letto solo per scegliere lo studio."""
    try:
        evento = json.loads(request.get_data() or b"{}")
        oggetto = (evento.get("data") or {}).get("object") or {}
        return str((oggetto.get("metadata") or {}).get("link_id") or "")
    except Exception:
        return ""


def _dati_json() -> dict:
    dati = request.get_json(silent=True)
    return dati if isinstance(dati, dict) else {}


def _riferimento_paypal() -> str:
    return str((_dati_json().get("resource") or {}).get("custom_id") or "")


def _riferimento_satispay() -> str:
    return str((_dati_json().get("metadata") or {}).get("link_id") or "")


def _riferimento_sumup() -> str:
    return str(_dati_json().get("checkout_reference") or "")


def _evento_stripe():
    gp = _get_gp()
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    if not gp.stripe_verifica_webhook(payload, sig_header):
        return jsonify({"error": "invalid signature"}), 400
    # Firma valida: il contenuto è quello dell'evento verificato. Si legge come
    # dizionario perché nelle librerie Stripe recenti l'evento non ha `.get`.
    event = json.loads(payload)
    if event.get("type") == "checkout.session.completed":
        sess = (event.get("data") or {}).get("object") or {}
        if sess.get("payment_status") == "paid":
            metadata = sess.get("metadata") or {}
            link_id = metadata.get("link_id", "")
            id_parcella = metadata.get("parcella", "")
            if link_id and link_id in {l.id for l in gp.tutti_link()}:
                gp.segna_pagato(link_id, "Stripe", tx_id=sess.get("id", ""))
                if id_parcella:
                    _update_parcella_pagata(id_parcella, "Stripe")
    return jsonify({"received": True}), 200


def _link_in_attesa(gp, link_id: str):
    link_id = str(link_id or "").strip()
    if not link_id:
        return None
    return next((l for l in gp.tutti_link() if l.id == link_id and l.stato == "ATTESO"), None)


def _registra_se_confermato(gp, lp, provider: str, tx_id: str, confermato: bool):
    """Segna pagata la parcella solo se il gestore ha confermato la transazione."""
    if lp is None:
        return jsonify({"received": True}), 200
    if not confermato:
        current_app.logger.warning(
            "Webhook %s non confermato dal gestore per il link %s: nessuna modifica.", provider, lp.id
        )
        return jsonify({"received": True, "verified": False}), 200
    gp.segna_pagato(lp.id, provider, tx_id=tx_id)
    _update_parcella_pagata(lp.id_parcella, provider)
    return jsonify({"received": True, "verified": True}), 200


def _evento_paypal():
    # La notifica PayPal non è firmata con un segreto dello studio: la cattura
    # si rilegge da PayPal con le credenziali dello studio prima di registrarla.
    data = _dati_json()
    if data.get("event_type") != "PAYMENT.CAPTURE.COMPLETED":
        return jsonify({"received": True}), 200
    resource = data.get("resource") or {}
    gp = _get_gp()
    lp = _link_in_attesa(gp, resource.get("custom_id"))
    tx_id = str(resource.get("id") or "")
    confermato = lp is not None and paypal_pagamento_confermato(gp, tx_id, lp)
    return _registra_se_confermato(gp, lp, "PayPal", tx_id, confermato)


def _evento_satispay():
    data = _dati_json()
    payment_id = str(data.get("id") or request.args.get("payment_id") or "")
    gp = _get_gp()
    lp = _link_in_attesa(gp, (data.get("metadata") or {}).get("link_id"))
    confermato = lp is not None and satispay_pagamento_confermato(gp, payment_id, lp)
    return _registra_se_confermato(gp, lp, "Satispay", payment_id, confermato)


def _evento_sumup():
    data = _dati_json()
    checkout_id = str(data.get("id") or "")
    gp = _get_gp()
    lp = _link_in_attesa(gp, data.get("checkout_reference"))
    confermato = lp is not None and sumup_pagamento_confermato(gp, checkout_id, lp)
    return _registra_se_confermato(gp, lp, "SumUp", checkout_id, confermato)


# gestore -> (riferimento del link nella notifica, gestione nel contesto dello studio)
_WEBHOOK = {
    "stripe": (_riferimento_stripe, _evento_stripe),
    "paypal": (_riferimento_paypal, _evento_paypal),
    "satispay": (_riferimento_satispay, _evento_satispay),
    "sumup": (_riferimento_sumup, _evento_sumup),
}


def _webhook(gestore: str):
    riferimento, gestisci = _WEBHOOK[gestore]
    if not risolvi_studio_webhook(riferimento()):
        return _nessuno_studio()
    return gestisci()


@pagamenti.route("/webhooks/stripe", methods=["POST"])
def webhook_stripe():
    return _webhook("stripe")


@pagamenti.route("/webhooks/paypal", methods=["POST"])
def webhook_paypal():
    return _webhook("paypal")


@pagamenti.route("/webhooks/satispay", methods=["POST"])
def webhook_satispay():
    return _webhook("satispay")


@pagamenti.route("/webhooks/sumup", methods=["POST"])
def webhook_sumup():
    return _webhook("sumup")


@pagamenti.route("/webhooks/<gestore>/<slug>", methods=["POST"])
def webhook_studio(gestore: str, slug: str):
    """Webhook configurato presso il gestore con l'indirizzo dello studio.

    Lo studio è noto prima di leggere la notifica: la firma Stripe si verifica
    con il segreto dello studio anche per eventi senza riferimento del link.
    Studio sconosciuto o sospeso, o installazione a studio singolo: 404.
    """
    voce = _WEBHOOK.get(gestore)
    if voce is None or not entra_studio_webhook(slug):
        abort(404)
    return voce[1]()
