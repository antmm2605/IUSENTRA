"""Webhook dei gestori di pagamento con più studi (revisione 2421).

Prima i webhook `/pagamenti/webhooks/<gestore>` cercavano il link e le chiavi
del gestore nell'archivio comune: con più studi un pagamento confermato dal
gestore non veniva mai registrato. Ora lo studio si ricava dal riferimento del
link inviato dal gestore (o dall'indirizzo `/webhooks/<gestore>/<slug>`) e la
firma si verifica con il segreto di quello studio.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest

from tests.test_revisione_2410_sicurezza import _app as _app_sessione

SEGRETO_A = "whsec_SEGRETO_STUDIO_A"
SEGRETO_B = "whsec_SEGRETO_STUDIO_B"
SK_STRIPE = "sk_test_SEGRETO_STRIPE_2421"


# ------------------------------------------------------------------ strumenti

def _firma_stripe(payload: bytes, segreto: str) -> str:
    istante = int(time.time())
    firma = hmac.new(segreto.encode(), f"{istante}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={istante},v1={firma}"


def _evento_stripe(link_id: str = "", *, tipo: str = "checkout.session.completed", sessione: str = "cs_test_1") -> bytes:
    metadata = {"link_id": link_id, "parcella": "parcella-x"} if link_id else {}
    return json.dumps({
        "id": "evt_2421",
        "object": "event",
        "type": tipo,
        "data": {"object": {
            "id": sessione,
            "object": "checkout.session",
            "payment_status": "paid",
            "amount_total": 9900,
            "metadata": metadata,
        }},
    }).encode()


def _invia_stripe(client, payload: bytes, segreto: str | None, url: str = "/pagamenti/webhooks/stripe"):
    intestazioni = {"Stripe-Signature": _firma_stripe(payload, segreto)} if segreto else {}
    return client.post(url, data=payload, content_type="application/json", headers=intestazioni)


def _config(segreto: str, *, paypal_secret: str = "", satispay: bool = False):
    from pct.pagamenti import ConfigPagamenti, PayPalConfig, SatispayConfig, StripeConfig

    return ConfigPagamenti(
        stripe=StripeConfig(abilitato=True, sk_test=SK_STRIPE, pk_test="pk_test_pubblica", webhook_secret=segreto),
        paypal=PayPalConfig(abilitato=bool(paypal_secret), client_id="paypal-id", client_secret=paypal_secret),
        satispay=SatispayConfig(abilitato=satispay, key_id="satispay-key" if satispay else "", private_key_pem="PEM" if satispay else ""),
    )


@pytest.fixture()
def due_studi(tmp_path):
    """Due studi, ciascuno con il proprio link di pagamento e i propri segreti."""
    from types import SimpleNamespace

    from pct.pagamenti import GestionePagamenti
    from pct.storage import StudioDB
    from pct.tenant import GestioneTenant
    from tests.test_web_bootstrap import _cfg_web, _write_studio_config
    from web.app import create_app
    from web.services import pagamenti_link_azioni
    from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data

    # Le cache impronta -> studio sono di processo: fra un test e l'altro i
    # registri degli studi cambiano.
    pagamenti_link_azioni._STUDIO_DEL_RIFERIMENTO.clear()
    pagamenti_link_azioni._STUDIO_DEL_LINK.clear()
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg_web(tmp_path), "MULTI_TENANT": True, "STORAGE_MODE_DEFAULT": "JSON"})
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studi = {}
    for slug, segreto, paypal in (("studio-pay-a", SEGRETO_A, "PAYPAL_A"), ("studio-pay-b", SEGRETO_B, "PAYPAL_B")):
        manager.crea(slug.replace("-", " ").title(), slug)
        bootstrap_legacy_tenant_runtime_data(app, tenant_slug=slug)
        percorsi = manager.percorsi_dati(slug, reconcile_aliases=False)

        def _gestore(percorsi=percorsi):
            return GestionePagamenti(db_dir=percorsi["PAGAMENTI_DIR"], studio_db=StudioDB.get(percorsi["STUDIO_DB"]))

        gp = _gestore()
        gp.aggiorna_config(_config(segreto, paypal_secret=paypal, satispay=True))
        lp = gp.crea_link(f"parcella-{slug}", "cliente-1", 99.0, f"Parcella {slug}")
        studi[slug] = SimpleNamespace(slug=slug, link=lp, segreto=segreto, gestore=_gestore)
    yield SimpleNamespace(app=app, a=studi["studio-pay-a"], b=studi["studio-pay-b"])
    pagamenti_link_azioni._STUDIO_DEL_RIFERIMENTO.clear()
    pagamenti_link_azioni._STUDIO_DEL_LINK.clear()


def _stato(studio) -> str:
    return next(lp.stato for lp in studio.gestore().tutti_link() if lp.id == studio.link.id)


# ------------------------------------------------------------------ più studi: Stripe

def test_webhook_stripe_registrato_solo_nello_studio_del_link(due_studi):
    payload = _evento_stripe(due_studi.b.link.id, sessione="cs_test_b")
    with due_studi.app.test_client() as client:
        risposta = _invia_stripe(client, payload, SEGRETO_B)
    assert risposta.status_code == 200, risposta.get_data(as_text=True)
    assert _stato(due_studi.b) == "PAGATO"
    pagato = next(lp for lp in due_studi.b.gestore().tutti_link() if lp.id == due_studi.b.link.id)
    assert pagato.provider_usato == "Stripe" and pagato.provider_tx_id == "cs_test_b"
    assert _stato(due_studi.a) == "ATTESO"


def test_webhook_stripe_con_segreto_di_un_altro_studio_respinto(due_studi):
    payload = _evento_stripe(due_studi.b.link.id)
    with due_studi.app.test_client() as client:
        # Firmato con il segreto dello studio A ma per il link dello studio B.
        assert _invia_stripe(client, payload, SEGRETO_A).status_code == 400
        # Senza firma.
        assert _invia_stripe(client, payload, None).status_code == 400
        # Firma valida ma contenuto alterato dopo la firma.
        intestazione = _firma_stripe(payload, SEGRETO_B)
        alterato = payload.replace(b"9900", b"100")
        assert client.post(
            "/pagamenti/webhooks/stripe", data=alterato, content_type="application/json",
            headers={"Stripe-Signature": intestazione},
        ).status_code == 400
    assert _stato(due_studi.b) == "ATTESO"
    assert _stato(due_studi.a) == "ATTESO"


def test_webhook_stripe_link_di_nessuno_studio(due_studi):
    with due_studi.app.test_client() as client:
        # Nessuno studio ha il link: nulla si verifica o si registra; 200 per
        # non far ripetere la notifica al gestore.
        for payload in (_evento_stripe("link-inesistente"), _evento_stripe(), b"non json"):
            risposta = _invia_stripe(client, payload, SEGRETO_B)
            assert risposta.status_code == 200 and risposta.get_json() == {"received": True}
    assert _stato(due_studi.a) == "ATTESO" and _stato(due_studi.b) == "ATTESO"


def test_webhook_stripe_con_lo_studio_nell_indirizzo(due_studi):
    b, a = due_studi.b, due_studi.a
    with due_studi.app.test_client() as client:
        # Evento senza riferimento del link: verificato con il segreto dello studio.
        altro = _evento_stripe(tipo="payment_intent.succeeded")
        assert _invia_stripe(client, altro, SEGRETO_B, f"/pagamenti/webhooks/stripe/{b.slug}").status_code == 200
        assert _invia_stripe(client, altro, SEGRETO_A, f"/pagamenti/webhooks/stripe/{b.slug}").status_code == 400
        # Indirizzo dello studio A con il link dello studio B: il link non è di A.
        payload = _evento_stripe(b.link.id)
        assert _invia_stripe(client, payload, SEGRETO_A, f"/pagamenti/webhooks/stripe/{a.slug}").status_code == 200
        assert _stato(b) == "ATTESO"
        assert _invia_stripe(client, payload, SEGRETO_B, f"/pagamenti/webhooks/stripe/{b.slug}").status_code == 200
        assert _stato(b) == "PAGATO"
        # Studio o gestore sconosciuti.
        assert _invia_stripe(client, payload, SEGRETO_B, "/pagamenti/webhooks/stripe/studio-inesistente").status_code == 404
        assert _invia_stripe(client, payload, SEGRETO_B, f"/pagamenti/webhooks/bitcoin/{b.slug}").status_code == 404
    assert _stato(a) == "ATTESO"


def test_webhook_studio_sospeso_non_risolto(due_studi):
    from pct.tenant import GestioneTenant

    GestioneTenant(due_studi.app.config["TENANTS_REGISTRY"]).sospendi(due_studi.b.slug)
    payload = _evento_stripe(due_studi.b.link.id)
    with due_studi.app.test_client() as client:
        assert _invia_stripe(client, payload, SEGRETO_B, f"/pagamenti/webhooks/stripe/{due_studi.b.slug}").status_code == 404
        assert _invia_stripe(client, payload, SEGRETO_B).get_json() == {"received": True}
    assert _stato(due_studi.b) == "ATTESO"


# ------------------------------------------------------------------ più studi: gestori senza firma

def test_webhook_paypal_confermato_con_le_credenziali_dello_studio(due_studi, monkeypatch):
    import web.blueprints.pagamenti as modulo

    chiamate = []

    def _conferma(gp, tx_id, lp):
        chiamate.append((gp.config.paypal.client_secret, tx_id, lp.id))
        return True

    monkeypatch.setattr(modulo, "paypal_pagamento_confermato", _conferma)
    notifica = {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "CAP-B", "custom_id": due_studi.b.link.id}}
    with due_studi.app.test_client() as client:
        risposta = client.post("/pagamenti/webhooks/paypal", json=notifica)
        assert risposta.get_json() == {"received": True, "verified": True}
        # Link di nessuno studio: nessuna chiamata al gestore.
        ignoto = client.post("/pagamenti/webhooks/paypal", json={**notifica, "resource": {"id": "X", "custom_id": "ignoto"}})
        assert ignoto.status_code == 200 and ignoto.get_json() == {"received": True}
    assert chiamate == [("PAYPAL_B", "CAP-B", due_studi.b.link.id)]
    assert _stato(due_studi.b) == "PAGATO" and _stato(due_studi.a) == "ATTESO"


def test_webhook_paypal_non_confermato_non_registra(due_studi, monkeypatch):
    import web.blueprints.pagamenti as modulo

    monkeypatch.setattr(modulo, "paypal_pagamento_confermato", lambda gp, tx_id, lp: False)
    notifica = {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "CAP-B", "custom_id": due_studi.b.link.id}}
    with due_studi.app.test_client() as client:
        assert client.post("/pagamenti/webhooks/paypal", json=notifica).get_json() == {"received": True, "verified": False}
    assert _stato(due_studi.b) == "ATTESO"


def test_callback_satispay_con_lo_studio_nell_indirizzo(due_studi, monkeypatch):
    from pct.pagamenti import GestionePagamenti

    indirizzi = []
    monkeypatch.setattr(
        GestionePagamenti, "satispay_crea_pagamento",
        lambda self, lp, callback_url: indirizzi.append(callback_url) or {"id": "S1", "redirect_url": "https://online.satispay.com/pay/S1"},
    )
    with due_studi.app.test_client() as client:
        risposta = client.post(f"/api/v1/pubblico/pagamenti/{due_studi.b.link.token}/avvia", json={"provider": "satispay"})
    assert risposta.status_code == 200, risposta.get_data(as_text=True)
    assert indirizzi and indirizzi[0].split("?")[0].endswith(f"/pagamenti/webhooks/satispay/{due_studi.b.slug}")
    # Satispay richiama con una GET: il link e il segnaposto del pagamento sono nell'indirizzo.
    assert f"link_id={due_studi.b.link.id}" in indirizzi[0] and indirizzi[0].endswith("payment_id={uuid}")


# ------------------------------------------------------------------ studio singolo

def _studio_singolo(tmp_path):
    from web.helpers import get_pagamenti

    app = _app_sessione(tmp_path)
    with app.test_request_context("/"):
        gp = get_pagamenti()
        gp.aggiorna_config(_config(SEGRETO_A))
        lp = gp.crea_link("parcella-1", "cliente-1", 99.0, "Parcella 1/2026")
    return app, lp


def _stato_singolo(app, lp) -> str:
    from web.helpers import get_pagamenti

    with app.test_request_context("/"):
        return next(x.stato for x in get_pagamenti().tutti_link() if x.id == lp.id)


def test_studio_singolo_webhook_stripe_invariato(tmp_path):
    app, lp = _studio_singolo(tmp_path)
    payload = _evento_stripe(lp.id)
    with app.test_client() as client:
        assert _invia_stripe(client, payload, SEGRETO_B).status_code == 400
        assert _invia_stripe(client, payload, None).status_code == 400
        assert _stato_singolo(app, lp) == "ATTESO"
        # Evento firmato senza link: ricevuto come prima.
        assert _invia_stripe(client, _evento_stripe(tipo="payment_intent.succeeded"), SEGRETO_A).get_json() == {"received": True}
        assert _invia_stripe(client, payload, SEGRETO_A).status_code == 200
        # L'indirizzo per studio esiste solo con più studi.
        assert _invia_stripe(client, payload, SEGRETO_A, "/pagamenti/webhooks/stripe/studio").status_code == 404
    assert _stato_singolo(app, lp) == "PAGATO"


def test_studio_singolo_callback_satispay_invariata(tmp_path):
    from web.services.pagamenti_link_azioni import indirizzi_ritorno

    app, lp = _studio_singolo(tmp_path)
    with app.test_request_context("/"):
        assert indirizzi_ritorno(lp.token)["callback_satispay"].endswith("/pagamenti/webhooks/satispay")


# ------------------------------------------------------------------ errore Stripe al cliente

def test_vista_classica_errore_stripe_generico(tmp_path, monkeypatch, caplog):
    from pct.pagamenti import GestionePagamenti

    app, lp = _studio_singolo(tmp_path)

    def _stripe_rotto(self, lp, success, cancel):
        raise RuntimeError(f"Invalid API Key provided: {SK_STRIPE}")

    monkeypatch.setattr(GestionePagamenti, "stripe_crea_sessione", _stripe_rotto)
    with app.test_client() as client:
        risposta = client.post(f"/pagamenti/paga/{lp.token}/avvia", data={"provider": "stripe"})
        assert risposta.status_code == 302
        with client.session_transaction() as sessione:
            messaggi = [testo for _categoria, testo in sessione.get("_flashes", [])]
        pagina = client.get(risposta.headers["Location"]).get_data(as_text=True)
    assert messaggi == ["Errore Stripe: pagamento non avviato. Riprova o scegli un altro metodo."]
    assert SK_STRIPE not in pagina and "Invalid API Key" not in pagina
    # Il dettaglio resta nel log del server.
    assert any(SK_STRIPE in (r.exc_text or "") or (r.exc_info and SK_STRIPE in str(r.exc_info[1])) for r in caplog.records)
