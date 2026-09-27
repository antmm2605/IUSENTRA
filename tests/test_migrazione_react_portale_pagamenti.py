"""Portale del cliente con link personale e link di pagamento: pagine React.

- `/portale/<token>/*` e `/pagamenti/paga/<token>` servono la shell React
  (vista classica con `?_legacy=1`), con lo stesso esito HTTP (410/403);
- le API `/api/v1/pubblico/...` usano la stessa verifica del token, gli
  stessi permessi, gli stessi limiti di caricamento e le stesse azioni delle
  pagine classiche, senza dati di altri clienti né segreti dei gestori;
- le scritture pubbliche chiedono la conferma CSRF della pagina;
- con più studi lo studio si ricava dal token anche per i pagamenti.
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.test_revisione_2410_sicurezza import _app as _app_sessione

API_PORTALE = "/api/v1/pubblico/portale"
API_PAGAMENTI = "/api/v1/pubblico/pagamenti"
SEGRETI = {
    "stripe": "sk_test_SEGRETO_STRIPE_123",
    "stripe_webhook": "whsec_SEGRETO_WEBHOOK",
    "paypal": "PAYPAL_CLIENT_SECRET_XYZ",
    "satispay": "-----BEGIN PRIVATE KEY-----SEGRETO",
    "sumup": "sup_sk_SEGRETO_SUMUP",
}


# ------------------------------------------------------------------ dati di prova

def _cliente_e_fascicolo(app, nome: str, **campi):
    from pct.clienti import TipoCliente
    from pct.fascicoli import TipoFascicolo
    from web.helpers import get_clienti, get_fascicoli

    with app.test_request_context("/"):
        cliente = get_clienti().nuovo(TipoCliente.PERSONA_FISICA, nome=nome, cognome="Prova", **campi)
        fascicolo = get_fascicoli().nuovo(f"{nome} c. Terzi", TipoFascicolo.CIVILE, nome_cliente=nome, id_cliente=cliente.id)
    return cliente, fascicolo


def _portale(app, id_cliente: str, **permessi):
    from pct.portale import PermessiPortale
    from web.services.portale_cliente_legacy_contesto import gestore_portale

    with app.test_request_context("/"):
        token, scheda = gestore_portale().crea(id_cliente, creato_da="test", permessi=PermessiPortale(**permessi))
    return token, scheda


def _scheda(app, id_portale: str):
    from web.services.portale_cliente_legacy_contesto import gestore_portale

    with app.test_request_context("/"):
        return gestore_portale().get(id_portale)


def _preventivo(app, id_cliente: str, stato: str = "INVIATO"):
    from pct.preventivi import StatoPreventivo, TipoVoce, VocePreventivo
    from web.helpers import get_preventivi

    with app.test_request_context("/"):
        gp = get_preventivi()
        preventivo = gp.crea_preventivo(
            id_cliente=id_cliente,
            oggetto="Assistenza recupero credito",
            voci=[VocePreventivo(descrizione="Fase stragiudiziale", importo=1200.0, tipo=TipoVoce.ONORARIO)],
        )
        gp.cambia_stato_preventivo(preventivo.id, StatoPreventivo(stato))
    return preventivo


def _configura_pagamenti(app, *, bonifico: bool = True, tutti: bool = True):
    from pct.pagamenti import BonificoConfig, ConfigPagamenti, PayPalConfig, SatispayConfig, StripeConfig, SumUpConfig
    from web.helpers import get_pagamenti

    with app.test_request_context("/"):
        gp = get_pagamenti()
        gp.aggiorna_config(ConfigPagamenti(
            stripe=StripeConfig(abilitato=tutti, sk_test=SEGRETI["stripe"], pk_test="pk_test_pubblica", webhook_secret=SEGRETI["stripe_webhook"]),
            paypal=PayPalConfig(abilitato=tutti, client_id="paypal-client-id", client_secret=SEGRETI["paypal"]),
            satispay=SatispayConfig(abilitato=tutti, key_id="satispay-key-id", private_key_pem=SEGRETI["satispay"]),
            sumup=SumUpConfig(abilitato=tutti, api_key=SEGRETI["sumup"], merchant_code="MC123"),
            bonifico=BonificoConfig(abilitato=bonifico, iban="IT60X0542811101000000123456", intestazione="Studio Prova", banca="Banca di Prova"),
        ))


def _link_pagamento(app, id_cliente: str = "cliente-1", *, giorni: int = 30):
    from web.helpers import get_pagamenti

    with app.test_request_context("/"):
        return get_pagamenti().crea_link("parcella-1", id_cliente, 250.5, "Parcella 1/2026 — Studio Prova", giorni_validita=giorni)


def _senza_segreti(testo: str) -> None:
    for segreto in SEGRETI.values():
        assert segreto not in testo


# ------------------------------------------------------------------ shell React

def test_shell_react_del_portale_e_vista_classica(tmp_path):
    app = _app_sessione(tmp_path)
    mario, _ = _cliente_e_fascicolo(app, "Mario")
    token, scheda = _portale(app, mario.id, carica_documenti=False)
    with app.test_client() as client:
        home = client.get(f"/portale/{token}")
        html = home.get_data(as_text=True)
        assert home.status_code == 200
        assert 'id="portale-token-react-root"' in html and f'data-token="{token}"' in html and 'data-sezione="home"' in html
        assert 'name="csrf-token"' in html
        assert home.headers["Cache-Control"] == "no-store"
        if "/static/react/assets/" in html:
            assert re.search(r'<script type="module" src="/static/react/assets/[^"]+\?v=', html)
        for sezione in ("privacy", "economici", "anagrafica"):
            risposta = client.get(f"/portale/{token}/{sezione}")
            assert risposta.status_code == 200 and f'data-sezione="{sezione}"' in risposta.get_data(as_text=True)
        # Stesso esito della vista classica: sezione non consentita e link non valido.
        negata = client.get(f"/portale/{token}/documenti")
        assert negata.status_code == 403 and 'data-stato="negato"' in negata.get_data(as_text=True)
        scaduto = client.get("/portale/token-inesistente/economici")
        assert scaduto.status_code == 410 and 'data-stato="scaduto"' in scaduto.get_data(as_text=True)
        assert "Link non valido" in scaduto.get_data(as_text=True)
        # La shell non registra accessi: li registrano le API che la pagina chiama.
        assert _scheda(app, scheda.id).n_accessi == 0
        classica = client.get(f"/portale/{token}?_legacy=1")
        assert classica.status_code == 200
        assert "Benvenuto, Prova Mario" in classica.get_data(as_text=True)
        assert "portale-token-react-root" not in classica.get_data(as_text=True)
        assert client.get(f"/portale/{token}/documenti?_legacy=1").status_code == 403
        assert client.get("/portale/token-inesistente?_legacy=1").status_code == 410
    # Vista classica: accesso registrato prima del controllo dei permessi (home + documenti).
    assert _scheda(app, scheda.id).n_accessi == 2


def test_shell_react_del_pagamento_e_vista_classica(tmp_path):
    app = _app_sessione(tmp_path)
    _configura_pagamenti(app)
    lp = _link_pagamento(app)
    with app.test_client() as client:
        pagina = client.get(f"/pagamenti/paga/{lp.token}")
        html = pagina.get_data(as_text=True)
        assert pagina.status_code == 200
        assert 'id="pagamento-react-root"' in html and f'data-token="{lp.token}"' in html and 'data-vista="checkout"' in html
        _senza_segreti(html)
        scaduto = client.get("/pagamenti/paga/token-inesistente")
        assert scaduto.status_code == 410 and 'data-vista="scaduto"' in scaduto.get_data(as_text=True)
        esito = client.get(f"/pagamenti/paga/{lp.token}/successo?provider=bonifico")
        assert esito.status_code == 200 and 'data-vista="esito"' in esito.get_data(as_text=True)
        assert 'data-provider="bonifico"' in esito.get_data(as_text=True)
        assert client.get("/pagamenti/paga/token-inesistente/successo").status_code == 404
        classica = client.get(f"/pagamenti/paga/{lp.token}?_legacy=1")
        assert classica.status_code == 200 and "Scegli il metodo di pagamento" in classica.get_data(as_text=True)
        _senza_segreti(classica.get_data(as_text=True))


# ------------------------------------------------------------------ API portale

ENDPOINT_PORTALE = (
    ("GET", ""),
    ("GET", "/privacy"),
    ("POST", "/privacy"),
    ("GET", "/documenti"),
    ("POST", "/documenti/upload"),
    ("GET", "/economici"),
    ("POST", "/preventivi/PREV/accetta"),
    ("POST", "/conferimenti/CONF/firma"),
    ("GET", "/anagrafica"),
    ("POST", "/anagrafica"),
)


def test_api_portale_token_non_valido_410(tmp_path):
    app = _app_sessione(tmp_path)
    mario, _ = _cliente_e_fascicolo(app, "Mario")
    token, scheda = _portale(app, mario.id)
    with app.test_request_context("/"):
        from web.services.portale_cliente_legacy_contesto import gestore_portale

        gestore_portale().revoca(scheda.id)
    with app.test_client() as client:
        for base in ("token-inesistente", token):
            for metodo, suffisso in ENDPOINT_PORTALE:
                risposta = client.open(f"{API_PORTALE}/{base}{suffisso}", method=metodo, json={})
                assert risposta.status_code == 410, (metodo, suffisso)
                payload = risposta.get_json()
                assert payload["ok"] is False and payload["code"] == "link_non_valido" and payload["message"]


def test_api_portale_dati_solo_del_cliente_del_link(tmp_path):
    app = _app_sessione(tmp_path)
    mario, pratica_mario = _cliente_e_fascicolo(app, "Mario", codice_fiscale="PRVMRA80A01H501U")
    luigi, pratica_luigi = _cliente_e_fascicolo(app, "Luigi")
    _preventivo(app, luigi.id)
    token, scheda = _portale(app, mario.id, vedi_appuntamenti=True, vedi_scadenze=True)
    with app.test_client() as client:
        home = client.get(f"{API_PORTALE}/{token}")
        assert home.status_code == 200
        dati = home.get_json()
        assert dati["cliente"]["nome_completo"] == "Prova Mario"
        assert [f["id"] for f in dati["fascicoli"]] == [pratica_mario.id]
        assert dati["economici"]["stats"]["preventivi"] == 0
        assert home.headers["Cache-Control"] == "no-store"
        anagrafica = client.get(f"{API_PORTALE}/{token}/anagrafica").get_json()
        assert anagrafica["anagrafica"]["codice_fiscale"] == "PRVMRA80A01H501U"
        documenti = client.get(f"{API_PORTALE}/{token}/documenti").get_json()
        assert [f["id"] for f in documenti["fascicoli"]] == [pratica_mario.id]
        testo = json.dumps([dati, anagrafica, documenti])
        for vietato in ("Luigi", pratica_luigi.id, scheda.token_hash, "token_hash", "ip_", "user_agent", "note_riservate"):
            assert vietato not in testo
        assert "token" not in dati
    # Ogni chiamata alle API registra l'accesso come le pagine classiche.
    assert _scheda(app, scheda.id).n_accessi == 3


@pytest.mark.parametrize(
    ("permessi", "metodo", "suffisso"),
    (
        ({"firma_privacy": False}, "GET", "/privacy"),
        ({"firma_privacy": False}, "POST", "/privacy"),
        ({"carica_documenti": False}, "GET", "/documenti"),
        ({"carica_documenti": False}, "POST", "/documenti/upload"),
        ({"vedi_economici": False}, "GET", "/economici"),
        ({"vedi_economici": False}, "POST", "/preventivi/X/accetta"),
        ({"accetta_preventivi": False}, "POST", "/preventivi/X/accetta"),
        ({"firma_conferimenti": False}, "POST", "/conferimenti/X/firma"),
        ({"vedi_anagrafica": False}, "GET", "/anagrafica"),
        ({"modifica_anagrafica": False}, "POST", "/anagrafica"),
    ),
)
def test_api_portale_rispetta_i_permessi(tmp_path, permessi, metodo, suffisso):
    app = _app_sessione(tmp_path)
    mario, _ = _cliente_e_fascicolo(app, "Mario")
    token, _scheda_portale = _portale(app, mario.id, **permessi)
    with app.test_client() as client:
        risposta = client.open(f"{API_PORTALE}/{token}{suffisso}", method=metodo, json={"cellulare": "333"})
    assert risposta.status_code == 403
    assert risposta.get_json()["code"] == "permesso_negato"


def test_api_portale_consenso_privacy(tmp_path):
    from web.helpers import get_clienti

    app = _app_sessione(tmp_path)
    mario, _ = _cliente_e_fascicolo(app, "Mario")
    token, scheda = _portale(app, mario.id)
    with app.test_client() as client:
        senza = client.post(f"{API_PORTALE}/{token}/privacy", json={})
        assert senza.status_code == 422 and senza.get_json()["message"] == "Devi spuntare la casella per procedere."
        con = client.post(f"{API_PORTALE}/{token}/privacy", json={"consenso": True})
        assert con.status_code == 200
        assert con.get_json()["sezione"] == "privacy_ok" and con.get_json()["privacy"]["firmata"] is True
    assert _scheda(app, scheda.id).privacy_firmata is True
    with app.test_request_context("/"):
        cliente = get_clienti().get(mario.id)
        assert cliente.consenso_trattamento is True and cliente.modalita_consenso == "digitale"


def test_api_portale_caricamento_solo_nelle_pratiche_del_cliente(tmp_path):
    from web.helpers import get_fascicoli

    app = _app_sessione(tmp_path)
    mario, pratica_mario = _cliente_e_fascicolo(app, "Mario")
    _luigi, pratica_luigi = _cliente_e_fascicolo(app, "Luigi")
    token, _scheda_portale = _portale(app, mario.id, max_upload_mb=1)
    url = f"{API_PORTALE}/{token}/documenti/upload"

    def _invia(client, **campi):
        return client.post(url, data=campi, content_type="multipart/form-data")

    with app.test_client() as client:
        estranea = _invia(client, **{"files[]": (io.BytesIO(b"x"), "nota.txt"), "id_fascicolo": pratica_luigi.id})
        assert estranea.status_code == 403 and estranea.get_json()["code"] == "pratica_non_disponibile"
        nessun_file = _invia(client, id_fascicolo=pratica_mario.id)
        assert nessun_file.status_code == 422 and nessun_file.get_json()["message"] == "Nessun file selezionato."
        propria = _invia(client, **{
            "files[]": [(io.BytesIO(b"contenuto"), "nota.txt"), (io.BytesIO(b"0" * (1024 * 1024 + 1)), "grande.pdf")],
            "id_fascicolo": pratica_mario.id,
            "note": "Carta d'identità",
        })
        assert propria.status_code == 200
        esito = propria.get_json()
        assert esito["caricati"] == ["nota.txt"]
        assert esito["errori"] == ["grande.pdf: supera il limite di 1 MB"]
        generico = _invia(client, **{"files[]": (io.BytesIO(b"generico"), "../../evasione.txt")})
        assert generico.status_code == 200 and generico.get_json()["caricati"] == ["../../evasione.txt"]
    with app.test_request_context("/"):
        assert not get_fascicoli().get(pratica_luigi.id).documenti
        assert [d.nome for d in get_fascicoli().get(pratica_mario.id).documenti] == ["nota.txt"]
    cartella = Path(app.config["PORTALE_UPLOADS"]) / mario.id
    salvati = list(cartella.iterdir())
    assert len(salvati) == 1 and salvati[0].name.endswith("_evasione.txt")


def test_api_portale_accetta_preventivo_e_firma_conferimento(tmp_path):
    app = _app_sessione(tmp_path)
    mario, _ = _cliente_e_fascicolo(app, "Mario")
    luigi, _ = _cliente_e_fascicolo(app, "Luigi")
    preventivo = _preventivo(app, mario.id)
    altrui = _preventivo(app, luigi.id)
    bozza = _preventivo(app, mario.id, stato="BOZZA")
    token, _scheda_portale = _portale(app, mario.id)
    with app.test_client() as client:
        economici = client.get(f"{API_PORTALE}/{token}/economici").get_json()
        assert [p["id"] for p in economici["preventivi"]] == [preventivo.id]
        assert economici["preventivi"][0]["can_accept"] is True
        assert economici["preventivi"][0]["pdf_url"] == f"/portale/{token}/preventivi/{preventivo.id}/pdf"
        assert economici["azioni_richieste"][0]["id"] == preventivo.id

        assert client.post(f"{API_PORTALE}/{token}/preventivi/{altrui.id}/accetta", json={}).status_code == 404
        assert client.post(f"{API_PORTALE}/{token}/preventivi/{bozza.id}/accetta", json={}).status_code == 409

        accettato = client.post(f"{API_PORTALE}/{token}/preventivi/{preventivo.id}/accetta", json={})
        assert accettato.status_code == 200
        esito = accettato.get_json()
        assert esito["sezione"] == "economici"
        assert esito["messaggi"][0] == {"categoria": "success", "testo": "Preventivo accettato correttamente."}

        dopo = client.get(f"{API_PORTALE}/{token}/economici").get_json()
        conferimento = dopo["conferimenti"][0]
        assert conferimento["can_sign"] is True
        firmato = client.post(f"{API_PORTALE}/{token}/conferimenti/{conferimento['id']}/firma", json={})
        assert firmato.status_code == 200
        # Anagrafica incompleta: come la vista classica, firma registrata e rinvio agli economici.
        assert firmato.get_json()["sezione"] == "economici"
        assert firmato.get_json()["messaggi"][0]["categoria"] == "warning"
        finale = client.get(f"{API_PORTALE}/{token}/economici").get_json()
        assert finale["conferimenti"][0]["can_sign"] is False


def test_api_portale_aggiorna_solo_i_recapiti(tmp_path):
    from web.helpers import get_clienti

    app = _app_sessione(tmp_path)
    mario, _ = _cliente_e_fascicolo(app, "Mario", codice_fiscale="PRVMRA80A01H501U")
    token, _scheda_portale = _portale(app, mario.id, modifica_anagrafica=True)
    with app.test_client() as client:
        errato = client.post(f"{API_PORTALE}/{token}/anagrafica", json={"cellulare": {"x": 1}})
        assert errato.status_code == 422
        risposta = client.post(
            f"{API_PORTALE}/{token}/anagrafica",
            json={"cellulare": " 333 1234567 ", "telefono": "080 123", "email": "mario@example.it", "codice_fiscale": "XXXX"},
        )
    assert risposta.status_code == 200
    assert risposta.get_json()["recapiti"] == {"cellulare": "333 1234567", "telefono": "080 123", "email": "mario@example.it"}
    with app.test_request_context("/"):
        cliente = get_clienti().get(mario.id)
        assert cliente.recapiti.email == "mario@example.it" and cliente.codice_fiscale == "PRVMRA80A01H501U"


# ------------------------------------------------------------------ API pagamenti

def test_api_pagamento_stato_del_link(tmp_path):
    from web.helpers import get_pagamenti

    app = _app_sessione(tmp_path)
    _configura_pagamenti(app)
    valido = _link_pagamento(app)
    scaduto = _link_pagamento(app, giorni=-1)
    pagato = _link_pagamento(app)
    with app.test_request_context("/"):
        get_pagamenti().segna_pagato(pagato.id, "Stripe", tx_id="cs_1")
    with app.test_client() as client:
        checkout = client.get(f"{API_PAGAMENTI}/{valido.token}")
        assert checkout.status_code == 200
        dati = checkout.get_json()
        assert dati["vista"] == "checkout" and dati["importo_cifra"] == "250.50"
        assert dati["provider_attivi"] == ["stripe", "paypal", "satispay", "sumup", "bonifico"]
        assert "token" not in dati
        _senza_segreti(checkout.get_data(as_text=True))
        gia = client.get(f"{API_PAGAMENTI}/{pagato.token}")
        assert gia.status_code == 200 and gia.get_json()["vista"] == "gia_pagato" and gia.get_json()["metodo"] == "Stripe"
        for token in (scaduto.token, "token-inesistente"):
            for metodo, suffisso in (("GET", ""), ("POST", "/avvia"), ("GET", "/esito")):
                risposta = client.open(f"{API_PAGAMENTI}/{token}{suffisso}", method=metodo, json={"provider": "bonifico"})
                if token == scaduto.token and suffisso == "/esito":
                    # L'esito di un link esistente resta leggibile (pagina di ritorno dal gestore).
                    assert risposta.status_code == 200
                    continue
                assert risposta.status_code == 410, (token, suffisso)
                assert risposta.get_json()["code"] == "link_non_valido"
        assert client.post(f"{API_PAGAMENTI}/{pagato.token}/avvia", json={"provider": "bonifico"}).status_code == 410


def _gestori_finti(monkeypatch, chiamate: list):
    from pct.pagamenti import GestionePagamenti

    monkeypatch.setattr(
        GestionePagamenti, "stripe_crea_sessione",
        lambda self, lp, success, cancel: chiamate.append(("stripe", success, cancel)) or "https://checkout.stripe.com/c/pay/cs_test_1",
    )
    monkeypatch.setattr(
        GestionePagamenti, "paypal_crea_ordine",
        lambda self, lp, return_url, cancel_url: chiamate.append(("paypal", return_url)) or {"id": "ORD1", "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=ORD1"},
    )
    monkeypatch.setattr(
        GestionePagamenti, "sumup_crea_checkout",
        lambda self, lp, return_url: chiamate.append(("sumup", return_url)) or {"checkout_id": "chk_123", "status": "PENDING"},
    )
    monkeypatch.setattr(
        GestionePagamenti, "satispay_crea_pagamento",
        lambda self, lp, callback_url: chiamate.append(("satispay", callback_url)) or {"id": "S1", "redirect_url": "https://online.satispay.com/pay/S1"},
    )


def test_api_pagamento_avvio_per_gestore(tmp_path, monkeypatch):
    app = _app_sessione(tmp_path)
    _configura_pagamenti(app)
    lp = _link_pagamento(app)
    chiamate: list = []
    _gestori_finti(monkeypatch, chiamate)
    url = f"{API_PAGAMENTI}/{lp.token}/avvia"
    with app.test_client() as client:
        stripe = client.post(url, json={"provider": "stripe"})
        assert stripe.get_json() == {"ok": True, "tipo": "redirect", "url": "https://checkout.stripe.com/c/pay/cs_test_1"}
        paypal = client.post(url, json={"provider": "paypal"})
        assert paypal.get_json()["url"].startswith("https://www.sandbox.paypal.com/")
        with client.session_transaction() as sessione:
            assert sessione[f"paypal_order_{lp.id}"] == "ORD1"
        satispay = client.post(url, json={"provider": "satispay"})
        assert satispay.get_json()["url"] == "https://online.satispay.com/pay/S1"
        sumup = client.post(url, json={"provider": "sumup"})
        assert sumup.get_json() == {
            "ok": True, "tipo": "sumup", "checkout_id": "chk_123",
            "url_esito": f"/pagamenti/paga/{lp.token}/successo?provider=sumup",
        }
        bonifico = client.post(url, json={"provider": "bonifico"})
        dati = bonifico.get_json()
        assert dati["tipo"] == "bonifico" and dati["url_esito"] == f"/pagamenti/paga/{lp.token}/successo?provider=bonifico"
        assert dati["esito"]["vista"] == "bonifico" and dati["esito"]["bonifico"]["iban"] == "IT60X0542811101000000123456"
        for risposta in (stripe, paypal, satispay, sumup, bonifico):
            assert risposta.status_code == 200
            _senza_segreti(risposta.get_data(as_text=True))
        assert client.post(url, json={"provider": "contanti"}).status_code == 400
    assert [c[0] for c in chiamate] == ["stripe", "paypal", "satispay", "sumup"]
    assert chiamate[0][1].endswith(f"/pagamenti/paga/{lp.token}/successo")
    assert chiamate[0][2].endswith(f"/pagamenti/paga/{lp.token}")
    assert chiamate[2][1].endswith("/pagamenti/webhooks/satispay")


def test_api_pagamento_errori_dei_gestori_senza_segreti(tmp_path, monkeypatch):
    from pct.pagamenti import GestionePagamenti

    app = _app_sessione(tmp_path)
    _configura_pagamenti(app, bonifico=False)
    lp = _link_pagamento(app)

    def _stripe_rotto(self, lp, success, cancel):
        raise RuntimeError(f"Invalid API Key provided: {SEGRETI['stripe']}")

    monkeypatch.setattr(GestionePagamenti, "stripe_crea_sessione", _stripe_rotto)
    monkeypatch.setattr(GestionePagamenti, "paypal_crea_ordine", lambda self, lp, return_url, cancel_url: {"id": "O", "approve_url": "javascript:alert(1)"})
    monkeypatch.setattr(GestionePagamenti, "sumup_crea_checkout", lambda self, lp, return_url: None)
    url = f"{API_PAGAMENTI}/{lp.token}/avvia"
    with app.test_client() as client:
        stripe = client.post(url, json={"provider": "stripe"})
        assert stripe.status_code == 502 and stripe.get_json()["code"] == "gestore_non_disponibile"
        _senza_segreti(stripe.get_data(as_text=True))
        assert client.post(url, json={"provider": "paypal"}).status_code == 502
        assert client.post(url, json={"provider": "sumup"}).get_json()["message"] == "Errore SumUp."
        # Bonifico non attivo nello studio: non si avvia e non si mostrano coordinate.
        assert client.post(url, json={"provider": "bonifico"}).status_code == 400
        esito = client.get(f"{API_PAGAMENTI}/{lp.token}/esito?provider=bonifico").get_json()
        assert esito["vista"] == "bonifico" and esito["bonifico"] is None


def test_api_pagamento_esito(tmp_path):
    from web.helpers import get_pagamenti

    app = _app_sessione(tmp_path)
    _configura_pagamenti(app)
    lp = _link_pagamento(app)
    with app.test_client() as client:
        attesa = client.get(f"{API_PAGAMENTI}/{lp.token}/esito?provider=stripe").get_json()
        assert attesa["vista"] == "atteso"
        riflesso = client.get(f"{API_PAGAMENTI}/{lp.token}/esito?provider=<script>").get_json()
        assert "<script>" not in json.dumps(riflesso)
        with app.test_request_context("/"):
            get_pagamenti().segna_pagato(lp.id, "PayPal", tx_id="ORD9")
        pagato = client.get(f"{API_PAGAMENTI}/{lp.token}/esito").get_json()
    assert pagato["vista"] == "pagato" and pagato["metodo"] == "PayPal" and pagato["id_transazione"] == "ORD9"
    assert pagato["data_pagamento"] == datetime.now().strftime("%d/%m/%Y")


def test_vista_classica_del_pagamento_invariata(tmp_path, monkeypatch):
    app = _app_sessione(tmp_path)
    _configura_pagamenti(app)
    lp = _link_pagamento(app)
    _gestori_finti(monkeypatch, [])
    with app.test_client() as client:
        stripe = client.post(f"/pagamenti/paga/{lp.token}/avvia", data={"provider": "stripe"})
        assert stripe.status_code == 302 and stripe.headers["Location"] == "https://checkout.stripe.com/c/pay/cs_test_1"
        bonifico = client.post(f"/pagamenti/paga/{lp.token}/avvia", data={"provider": "bonifico"})
        assert bonifico.headers["Location"].endswith(f"/pagamenti/paga/{lp.token}/successo?provider=bonifico")
        sumup = client.post(f"/pagamenti/paga/{lp.token}/avvia", data={"provider": "sumup"})
        assert sumup.status_code == 200 and "chk_123" in sumup.get_data(as_text=True)
        _senza_segreti(sumup.get_data(as_text=True))
        assert client.post(f"/pagamenti/paga/{lp.token}/avvia", data={"provider": "contanti"}).status_code == 400
        successo = client.get(f"/pagamenti/paga/{lp.token}/successo?provider=bonifico&_legacy=1")
        assert "Effettua il bonifico" in successo.get_data(as_text=True)


# ------------------------------------------------------------------ CSRF e accesso

def test_scritture_pubbliche_protette_dal_csrf(tmp_path):
    from web.services.security_runtime import _CSRF_PROTECTED_ENDPOINTS

    scritture = {
        "api_v1_portale_token.portale_privacy_consenso",
        "api_v1_portale_token.portale_documenti_upload",
        "api_v1_portale_token.portale_preventivo_accetta",
        "api_v1_portale_token.portale_conferimento_firma",
        "api_v1_portale_token.portale_anagrafica_aggiorna",
        "api_v1_portale_token.pagamento_avvia",
    }
    assert scritture <= _CSRF_PROTECTED_ENDPOINTS

    app = _app_sessione(tmp_path, ENABLE_BROWSER_CSRF=True)
    mario, _ = _cliente_e_fascicolo(app, "Mario")
    token, _scheda_portale = _portale(app, mario.id)
    _configura_pagamenti(app)
    lp = _link_pagamento(app)
    with app.test_client() as client:
        assert client.post(f"{API_PORTALE}/{token}/privacy", json={"consenso": True}).status_code == 400
        assert client.post(f"{API_PAGAMENTI}/{lp.token}/avvia", json={"provider": "bonifico"}).status_code == 400
        estraneo = {"Origin": "https://sito-estraneo.example"}
        assert client.post(f"{API_PORTALE}/{token}/privacy", json={"consenso": True}, headers=estraneo).status_code == 400
        # La shell consegna la conferma di sicurezza della sessione (meta csrf-token).
        shell = client.get(f"/portale/{token}/privacy").get_data(as_text=True)
        conferma = re.search(r'<meta name="csrf-token" content="([^"]+)"', shell).group(1)
        assert client.post(f"{API_PORTALE}/{token}/privacy", json={"consenso": True}, headers={"X-CSRF-Token": conferma}).status_code == 200
        assert client.post(f"{API_PAGAMENTI}/{lp.token}/avvia", json={"provider": "bonifico"}, headers={"X-CSRF-Token": conferma}).status_code == 200


def test_api_pubbliche_senza_login_e_registrate(tmp_path):
    from web.services.auth_runtime import API_PUBBLICHE

    app = _app_sessione(tmp_path)
    # Le API pubbliche dell'accesso (login) hanno il loro elenco dedicato.
    endpoint = {
        rule.endpoint
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/api/v1/pubblico/") and not rule.rule.startswith("/api/v1/pubblico/accesso")
    }
    assert endpoint and endpoint <= API_PUBBLICHE
    assert {e for e in API_PUBBLICHE if e.startswith("api_v1_portale_token.")} == endpoint
    with app.test_client() as client:
        risposta = client.get(f"{API_PORTALE}/token-inesistente")
    assert risposta.status_code == 410 and "/login" not in (risposta.headers.get("Location") or "")


# ------------------------------------------------------------------ più studi

def test_con_piu_studi_lo_studio_si_ricava_dal_token(tmp_path):
    from pct.clienti import GestioneClienti, TipoCliente
    from pct.pagamenti import GestionePagamenti
    from pct.portale import GestionePortale
    from pct.storage import StudioDB
    from pct.tenant import GestioneTenant
    from tests.test_web_bootstrap import _cfg_web, _write_studio_config
    from web.app import create_app
    from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg_web(tmp_path), "MULTI_TENANT": True, "STORAGE_MODE_DEFAULT": "JSON"})
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    manager.crea("Studio Link A", "studio-link-a")
    studio_b = manager.crea("Studio Link B", "studio-link-b")
    for slug in ("studio-link-a", studio_b.slug):
        bootstrap_legacy_tenant_runtime_data(app, tenant_slug=slug)
    percorsi = manager.percorsi_dati(studio_b.slug, reconcile_aliases=False)
    # Archivio SQL dello studio B, come in esercizio.
    studio_db = StudioDB.get(percorsi["STUDIO_DB"])
    cliente = GestioneClienti(db_path=percorsi["CLIENTI_DB"], studio_db=studio_db).nuovo(TipoCliente.PERSONA_FISICA, nome="Bianca", cognome="Studio B")
    token, _scheda_portale = GestionePortale(db_path=percorsi["PORTALE_DB"], uploads_dir=percorsi["PORTALE_UPLOADS"]).crea(cliente.id, creato_da="test")
    lp = GestionePagamenti(db_dir=percorsi["PAGAMENTI_DIR"], studio_db=studio_db).crea_link("parcella-b", cliente.id, 99.0, "Parcella studio B")

    with app.test_client() as client:
        portale = client.get(f"{API_PORTALE}/{token}")
        assert portale.status_code == 200, portale.get_data(as_text=True)
        assert portale.get_json()["cliente"]["nome_completo"] == "Studio B Bianca"
        pagamento = client.get(f"{API_PAGAMENTI}/{lp.token}")
        assert pagamento.status_code == 200, pagamento.get_data(as_text=True)
        assert pagamento.get_json()["cliente"] == "Studio B Bianca"
        # Prima della correzione il link di pagamento risultava sempre scaduto con più studi.
        assert client.get(f"/pagamenti/paga/{lp.token}?_legacy=1").status_code == 200
        assert client.get(f"/pagamenti/paga/{lp.token}").status_code == 200
        assert client.get(f"{API_PORTALE}/token-inesistente").status_code == 410
        assert client.get(f"{API_PAGAMENTI}/token-inesistente").status_code == 410


def test_link_di_pagamento_scaduto_ieri(tmp_path):
    app = _app_sessione(tmp_path)
    lp = _link_pagamento(app, giorni=-1)
    assert datetime.fromisoformat(lp.scade_il) < datetime.now() + timedelta(seconds=1)
    with app.test_client() as client:
        assert client.get(f"/pagamenti/paga/{lp.token}").status_code == 410
