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
    MESSAGGIO_LINK_DISCORDANTE,
    PaymentCheckoutReview,
    aggiorna_parcella_pagata,
    entra_studio_webhook,
    risolvi_studio_pagamento,
    risolvi_studio_webhook,
    verifica_ritorno,
    vista_link,
)
from pct.payment_links_sql import PaymentLinkConflict
from web.services.pubblico_token_shell import render_pagamento_shell

pagamenti = Blueprint("pagamenti", __name__)


@pagamenti.errorhandler(PaymentLinkConflict)
def _collegamento_discordante(exc):
    # Link discordante dalla fonte SQL: mai un 500. Lo studio trova l'anomalia nel log, il cliente
    # vede lo stato «da verificare» senza dettagli tecnici e senza alcun addebito avviato.
    token = str((request.view_args or {}).get("token") or "")
    current_app.logger.warning("Pagamenti: collegamento discordante (token ...%s): %s", token[-6:], exc)
    return render_pagamento_shell(token, "da_verificare", titolo="Pagamento da verificare",
        studio_nome=_studio_nome(), status=409, messaggio=MESSAGGIO_LINK_DISCORDANTE)


@pagamenti.errorhandler(PaymentCheckoutReview)
def _pagamento_da_riscontrare(exc):
    # Stato «da verificare» nella pagina React del link (stesso indirizzo), nessun addebito avviato.
    token = str((request.view_args or {}).get("token") or "")
    return render_pagamento_shell(token, "da_verificare", titolo="Pagamento da verificare",
        studio_nome=_studio_nome(), status=409, messaggio=str(exc))

# Pagine del cliente raggiunte con il token del link (i webhook restano esclusi).
_ENDPOINT_CON_TOKEN = {"pagamenti.checkout", "pagamenti.successo"}


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

    # Le impostazioni dei pagamenti stanno nella sezione Pagamenti di Impostazioni (React).
    return redirect("/impostazioni?tab=pagamenti")


# ================================================================ CREA LINK PAGAMENTO

@pagamenti.route("/fatturazione/<id_parcella>/link-pagamento", methods=["POST"])
@_richiedi_login
def crea_link_pagamento(id_parcella: str):
    gp = _get_gp()
    gf = _shared_get_fatturazione()
    p = gf.get(id_parcella)
    if not p:
        abort(404)
    from web.services.payment_confirmations_runtime import payment_link_amount
    amount = payment_link_amount(gp, p)
    giorni = int(request.form.get("giorni_validita", 30))
    from pct.fatturazione import parcella_revision
    lp = gp.crea_link(
        id_parcella=id_parcella,
        id_cliente=p.id_cliente,
        importo=amount,
        descrizione=f"Parcella {p.numero} — {current_app.config.get('STUDIO_NOME', 'IUSENTRA')}",
        giorni_validita=giorni,
        replace_pending=True, expected_invoice_revision=parcella_revision(p),
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


_TITOLI_VISTA = {"checkout": "Pagamento", "gia_pagato": "Già pagato", "scaduto": "Link scaduto"}


@pagamenti.route("/paga/<token>", methods=["GET"])
def checkout(token: str):
    gp = _get_gp()
    stato = vista_link(gp, token)
    # Pagina React (PagamentoLinkApp): dati e avvio da /api/v1/pubblico/pagamenti/<token>.
    return render_pagamento_shell(
        token, stato.vista, titolo=_TITOLI_VISTA[stato.vista], studio_nome=_studio_nome(), status=stato.status,
    )


# ================================================================ AVVIA PAGAMENTO (POST dal checkout)


# ================================================================ SUCCESSO

@pagamenti.route("/paga/<token>/successo", methods=["GET"])
def successo(token: str):
    gp = _get_gp()
    provider = request.args.get("provider", "")
    # PayPal (cattura dell'ordine) e Stripe (sessione) si verificano qui, al ritorno.
    lp = verifica_ritorno(gp, token, provider, request.args)
    if not lp:
        abort(404)
    return render_pagamento_shell(
        token, "esito", titolo="Pagamento", studio_nome=_studio_nome(), provider=provider,
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
    # La richiamata reale di Satispay è una GET con ?link_id=&payment_id=.
    return str((_dati_json().get("metadata") or {}).get("link_id") or request.args.get("link_id") or "")


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
    if event.get("type") in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        sess = (event.get("data") or {}).get("object") or {}
        if sess.get("payment_status") == "paid":
            metadata = sess.get("metadata") or {}
            link_id = metadata.get("link_id", "")
            id_parcella = metadata.get("parcella", "")
            lp = gp.get_by_id(link_id) if link_id else None
            if lp is not None and getattr(gp, '_studio_db', None) is not None:
                from pct.payment_evidence import stripe_facts
                from web.services.payment_confirmations_runtime import confirm_payment
                try:
                    facts = stripe_facts(sess, lp, verified_event_created=event.get('created'),
                        verified_event_id=event.get('id'), verified_event_type=event.get('type'))
                except ValueError:
                    return jsonify({'received': True, 'verified': False}), 400
                outcome = confirm_payment(gp, facts, verification_kind='signed_event')
                return jsonify({'received': True, 'verified': True, **outcome}), 200
            if lp is not None:
                gp.segna_pagato(link_id, "Stripe", tx_id=sess.get("id", ""))
                if id_parcella:
                    _update_parcella_pagata(id_parcella, "Stripe")
    return jsonify({"received": True}), 200


def _link_in_attesa(gp, link_id: str):
    link_id = str(link_id or "").strip()
    if not link_id:
        return None
    link = gp.get_by_id(link_id)
    return link if link is not None and (link.stato == "ATTESO" or getattr(gp, '_studio_db', None) is not None) else None


def _registra_se_confermato(gp, lp, provider: str, tx_id: str, confermato: bool):
    """Segna pagata la parcella solo se il gestore ha confermato la transazione."""
    if lp is None:
        return jsonify({"received": True}), 200
    if not confermato:
        current_app.logger.warning(
            "Webhook %s non confermato dal gestore per il link %s: nessuna modifica.", provider, lp.id
        )
        return jsonify({"received": True, "verified": False}), 200
    if getattr(gp, '_studio_db', None) is not None:
        from pct.payment_evidence import ProviderPaymentFacts
        from web.services.payment_confirmations_runtime import confirm_payment
        if not isinstance(confermato, ProviderPaymentFacts):
            raise ValueError('La conferma richiede la fonte autenticata del gestore.')
        outcome = confirm_payment(gp, confermato, verification_kind='authenticated_api')
        return jsonify({'received': True, 'verified': True, **outcome}), 200
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
    confermato = lp is not None and paypal_pagamento_confermato(gp, tx_id, lp,
        **({'evidence': True} if getattr(gp, '_studio_db', None) is not None else {}))
    return _registra_se_confermato(gp, lp, "PayPal", tx_id, confermato)


def _evento_satispay():
    data = _dati_json()
    payment_id = str(data.get("id") or request.args.get("payment_id") or "")
    gp = _get_gp()
    lp = _link_in_attesa(gp, (data.get("metadata") or {}).get("link_id") or request.args.get("link_id"))
    confermato = lp is not None and satispay_pagamento_confermato(gp, payment_id, lp,
        **({'evidence': True} if getattr(gp, '_studio_db', None) is not None else {}))
    return _registra_se_confermato(gp, lp, "Satispay", payment_id, confermato)


def _evento_sumup():
    data = _dati_json()
    checkout_id = str(data.get("id") or "")
    gp = _get_gp()
    lp = _link_in_attesa(gp, data.get("checkout_reference"))
    confermato = lp is not None and sumup_pagamento_confermato(gp, checkout_id, lp,
        **({'evidence': True} if getattr(gp, '_studio_db', None) is not None else {}))
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


@pagamenti.route("/webhooks/satispay", methods=["POST", "GET"])
def webhook_satispay():
    return _webhook("satispay")


@pagamenti.route("/webhooks/sumup", methods=["POST"])
def webhook_sumup():
    return _webhook("sumup")


@pagamenti.route("/webhooks/<gestore>/<slug>", methods=["POST", "GET"])
def webhook_studio(gestore: str, slug: str):
    """Webhook configurato presso il gestore con l'indirizzo dello studio.

    Lo studio è noto prima di leggere la notifica: la firma Stripe si verifica
    con il segreto dello studio anche per eventi senza riferimento del link.
    Studio sconosciuto o sospeso, o installazione a studio singolo: 404.
    """
    voce = _WEBHOOK.get(gestore)
    if request.method == "GET" and gestore != "satispay":
        abort(405)
    if voce is None or not entra_studio_webhook(slug):
        abort(404)
    return voce[1]()
