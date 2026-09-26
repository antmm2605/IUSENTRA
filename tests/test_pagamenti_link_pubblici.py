"""Il link di pagamento del cliente e i webhook dei gestori non chiedono il login dello studio."""

from __future__ import annotations

from tests.test_revisione_2410_sicurezza import _app


def test_link_di_pagamento_e_webhook_senza_login(tmp_path):
    app = _app(tmp_path)
    with app.test_client() as client:
        for percorso in ("/pagamenti/paga/token-inesistente", "/pagamenti/paga/token-inesistente/successo"):
            risposta = client.get(percorso)
            assert "/login" not in (risposta.headers.get("Location") or ""), percorso
            assert risposta.status_code in (404, 410), percorso
        assert "/login" not in (client.post("/pagamenti/paga/token-inesistente/avvia").headers.get("Location") or "")
        for gestore in ("stripe", "paypal", "satispay", "sumup"):
            risposta = client.post(f"/pagamenti/webhooks/{gestore}", data=b"{}", content_type="application/json")
            assert risposta.status_code != 302, gestore
        # Le pagine dello studio restano protette.
        assert "/login" in (client.get("/pagamenti/impostazioni/pagamenti").headers.get("Location") or "")


def test_il_link_mostrato_allo_studio_esiste():
    from types import SimpleNamespace

    from web.services.react_incassi_pagamenti_bridge import _payment_url

    assert _payment_url(SimpleNamespace(token="abc")) == "/pagamenti/paga/abc"
