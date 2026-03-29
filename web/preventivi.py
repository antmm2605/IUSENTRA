"""
web/blueprints/pagamenti.py — Gestione pagamenti digitali.

URL base:
  /impostazioni/pagamenti  — pannello configurazione provider (avvocato)
  /paga/<token>            — pagina checkout cliente (no auth)
  /webhooks/stripe         — webhook Stripe
  /webhooks/paypal         — webhook PayPal
  /webhooks/sumup          — webhook SumUp
"""
from __future__ import annotations

from flask import (Blueprint, abort, flash, g, jsonify, redirect,
                   render_template, request, url_for, current_app)

pagamenti = Blueprint("pagamenti", __name__)


# ---------------------------------------------------------------- helpers

def _get_gp():
    from pct.pagamenti import GestionePagamenti
    return GestionePagamenti(
        db_dir=current_app.config.get("PAGAMENTI_DIR", "./pagamenti")
    )


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
    try:
        from pct.fatturazione import GestioneFatturazione, StatoParcella
        db_path = current_app.config.get("FATTURAZIONE_DB", "./fatturazione/parcelle.json")
        gf = GestioneFatturazione(db_path=db_path)
        gf.cambia_stato(id_parcella, StatoParcella.PAGATA, metodo_pagamento=metodo)
    except Exception:
        pass


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

    cfg = gp.config
    link_recenti = gp.tutti_link()[:20]
    return render_template(
        "pagamenti/impostazioni.html",
        cfg=cfg,
        link_recenti=link_recenti,
        provider_attivi=cfg.provider_attivi(),
    )


# ================================================================ CREA LINK PAGAMENTO

@pagamenti.route("/fatturazione/<id_parcella>/link-pagamento", methods=["POST"])
@_richiedi_login
def crea_link_pagamento(id_parcella: str):
    from pct.fatturazione import GestioneFatturazione
    gp = _get_gp()
    gf = GestioneFatturazione(
        db_path=current_app.config.get("FATTURAZIONE_DB", "./fatturazione/parcelle.json")
    )
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
        descrizione=f"Parcella {p.numero} — {current_app.config.get('STUDIO_NOME', 'Studio Legale PCT')}",
        giorni_validita=giorni,
    )
    link = request.host_url.rstrip("/") + url_for("pagamenti.checkout", token=lp.token)
    flash(f"Link di pagamento creato. Scade tra {giorni} giorni.", "success")
    # Salva in sessione per mostrarlo subito
    from flask import session
    session["pagamento_link_pending"] = {"link": link, "numero": p.numero, "totale": p.totale}
    return redirect(url_for("fatturazione.dettaglio", id_parcella=id_parcella))


# ================================================================ CHECKOUT CLIENTE (no auth)

@pagamenti.route("/paga/<token>", methods=["GET"])
def checkout(token: str):
    gp = _get_gp()
    lp = gp.get_by_token(token)
    if not lp:
        return render_template("pagamenti/scaduto.html",
                               studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT")), 410
    if not lp.is_valido:
        if lp.stato == "PAGATO":
            return render_template("pagamenti/gia_pagato.html", lp=lp,
                                   studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"))
        return render_template("pagamenti/scaduto.html",
                               studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT")), 410

    cfg = gp.config
    from web.helpers import get_clienti
    cliente = get_clienti().get(lp.id_cliente)
    studio_nome = current_app.config.get("STUDIO_NOME", "Studio Legale PCT")

    return render_template(
        "pagamenti/checkout.html",
        lp=lp,
        cfg=cfg,
        cliente=cliente,
        studio_nome=studio_nome,
        provider_attivi=cfg.provider_attivi(),
    )


# ================================================================ AVVIA PAGAMENTO (POST dal checkout)

@pagamenti.route("/paga/<token>/avvia", methods=["POST"])
def avvia_pagamento(token: str):
    gp = _get_gp()
    lp = gp.get_by_token(token)
    if not lp or not lp.is_valido:
        abort(410)

    provider = request.form.get("provider", "").strip()
    base = request.host_url.rstrip("/")
    success_url = base + url_for("pagamenti.successo", token=token)
    cancel_url  = base + url_for("pagamenti.checkout", token=token)

    if provider == "stripe":
        try:
            url = gp.stripe_crea_sessione(lp, success_url, cancel_url)
            return redirect(url)
        except Exception as e:
            flash(f"Errore Stripe: {e}", "danger")
            return redirect(url_for("pagamenti.checkout", token=token))

    elif provider == "paypal":
        ordine = gp.paypal_crea_ordine(lp,
                                        return_url=success_url + "?provider=paypal",
                                        cancel_url=cancel_url)
        if ordine and ordine.get("approve_url"):
            # Salva order_id in sessione per la capture al ritorno
            from flask import session
            session[f"paypal_order_{lp.id}"] = ordine["id"]
            return redirect(ordine["approve_url"])
        flash("Errore nella creazione dell'ordine PayPal.", "danger")
        return redirect(url_for("pagamenti.checkout", token=token))

    elif provider == "sumup":
        checkout = gp.sumup_crea_checkout(lp, return_url=success_url)
        if checkout and checkout.get("checkout_id"):
            return render_template(
                "pagamenti/sumup_checkout.html",
                lp=lp,
                checkout_id=checkout["checkout_id"],
                sumup_api_key=gp.config.sumup.api_key,
                success_url=success_url,
                studio_nome=current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
            )
        flash("Errore SumUp.", "danger")
        return redirect(url_for("pagamenti.checkout", token=token))

    elif provider == "satispay":
        callback = base + url_for("pagamenti.webhook_satispay")
        risultato = gp.satispay_crea_pagamento(lp, callback_url=callback)
        if risultato and risultato.get("redirect_url"):
            return redirect(risultato["redirect_url"])
        flash("Errore Satispay.", "danger")
        return redirect(url_for("pagamenti.checkout", token=token))

    elif provider == "bonifico":
        return redirect(url_for("pagamenti.successo", token=token) + "?provider=bonifico")

    abort(400)


# ================================================================ SUCCESSO

@pagamenti.route("/paga/<token>/successo", methods=["GET"])
def successo(token: str):
    gp = _get_gp()
    lp = gp.get_by_token(token)
    if not lp:
        abort(404)

    provider = request.args.get("provider", "")
    studio_nome = current_app.config.get("STUDIO_NOME", "Studio Legale PCT")

    # PayPal: cattura ordine al ritorno
    if provider == "paypal" and lp.stato == "ATTESO":
        from flask import session
        order_id = request.args.get("token") or session.pop(f"paypal_order_{lp.id}", None)
        if order_id and gp.paypal_cattura_ordine(order_id):
            gp.segna_pagato(lp.id, "PayPal", tx_id=order_id)
            _update_parcella_pagata(lp.id_parcella, "PayPal")

    # Stripe: verifica via session_id
    session_id = request.args.get("session_id", "")
    if session_id and lp.stato == "ATTESO":
        try:
            import stripe
            stripe.api_key = gp.config.stripe.sk
            sess = stripe.checkout.Session.retrieve(session_id)
            if sess.payment_status == "paid":
                gp.segna_pagato(lp.id, "Stripe", tx_id=session_id)
                _update_parcella_pagata(lp.id_parcella, "Stripe")
        except Exception:
            pass

    # Bonifico: segna come "in attesa conferma"
    if provider == "bonifico":
        lp = gp.get_by_token(token)  # ricarica
        cfg_bonifico = gp.config.bonifico

    # Ricarica lp
    lp = gp.get_by_token(token)
    return render_template(
        "pagamenti/successo.html",
        lp=lp,
        provider=provider or lp.provider_usato or "",
        cfg_bonifico=gp.config.bonifico if provider == "bonifico" else None,
        studio_nome=studio_nome,
    )


# ================================================================ WEBHOOKS

@pagamenti.route("/webhooks/stripe", methods=["POST"])
def webhook_stripe():
    gp = _get_gp()
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    event = gp.stripe_verifica_webhook(payload, sig_header)
    if not event:
        return jsonify({"error": "invalid signature"}), 400
    if event["type"] == "checkout.session.completed":
        sess = event["data"]["object"]
        if sess.get("payment_status") == "paid":
            link_id = sess.get("metadata", {}).get("link_id", "")
            id_parcella = sess.get("metadata", {}).get("parcella", "")
            if link_id and link_id in {l.id for l in gp.tutti_link()}:
                gp.segna_pagato(link_id, "Stripe", tx_id=sess["id"])
                if id_parcella:
                    _update_parcella_pagata(id_parcella, "Stripe")
    return jsonify({"received": True}), 200


@pagamenti.route("/webhooks/paypal", methods=["POST"])
def webhook_paypal():
    # PayPal IPN / Webhook — verifica base
    data = request.get_json(silent=True) or {}
    if data.get("event_type") == "PAYMENT.CAPTURE.COMPLETED":
        resource = data.get("resource", {})
        custom_id = resource.get("custom_id", "")
        tx_id     = resource.get("id", "")
        if custom_id:
            gp = _get_gp()
            lp = next((l for l in gp.tutti_link() if l.id == custom_id), None)
            if lp and lp.stato == "ATTESO":
                gp.segna_pagato(lp.id, "PayPal", tx_id=tx_id)
                _update_parcella_pagata(lp.id_parcella, "PayPal")
    return jsonify({"received": True}), 200


@pagamenti.route("/webhooks/satispay", methods=["POST"])
def webhook_satispay():
    data = request.get_json(silent=True) or {}
    if data.get("status") == "ACCEPTED":
        metadata = data.get("metadata", {})
        link_id = metadata.get("link_id", "")
        if link_id:
            gp = _get_gp()
            lp = next((l for l in gp.tutti_link() if l.id == link_id), None)
            if lp and lp.stato == "ATTESO":
                gp.segna_pagato(lp.id, "Satispay", tx_id=data.get("id", ""))
                _update_parcella_pagata(lp.id_parcella, "Satispay")
    return jsonify({"received": True}), 200


@pagamenti.route("/webhooks/sumup", methods=["POST"])
def webhook_sumup():
    data = request.get_json(silent=True) or {}
    if data.get("status") == "PAID":
        ref = data.get("checkout_reference", "")
        if ref:
            gp = _get_gp()
            lp = next((l for l in gp.tutti_link() if l.id == ref), None)
            if lp and lp.stato == "ATTESO":
                gp.segna_pagato(lp.id, "SumUp", tx_id=data.get("id", ""))
                _update_parcella_pagata(lp.id_parcella, "SumUp")
    return jsonify({"received": True}), 200
