"""Link scaduto e pagamento «da verificare»: pagine React allo stesso indirizzo (niente più scaduto.html)."""

from __future__ import annotations

from pathlib import Path

from tests.test_migrazione_react_portale_pagamenti import (
    _cliente_e_fascicolo,
    _configura_pagamenti,
    _link_pagamento,
    _portale,
)
from tests.test_revisione_2410_sicurezza import _app as _app_sessione
from web.services.pagamenti_link_azioni import PaymentCheckoutReview

RADICE = Path(__file__).resolve().parents[1]


def _verifica_shell_pagamento(risposta, status: int, vista: str) -> str:
    html = risposta.get_data(as_text=True)
    assert risposta.status_code == status
    assert 'id="pagamento-react-root"' in html and f'data-vista="{vista}"' in html
    assert risposta.headers["Cache-Control"] == "no-store"
    return html


def test_link_scaduto_anche_in_vista_classica_e_avvio_mostra_la_pagina_react(tmp_path):
    app = _app_sessione(tmp_path)
    scaduto = _link_pagamento(app, giorni=-1)
    with app.test_client() as client:
        for risposta in (
            client.get("/pagamenti/paga/token-inesistente?_legacy=1"),
            client.get(f"/pagamenti/paga/{scaduto.token}?_legacy=1"),
            client.post(f"/pagamenti/paga/{scaduto.token}/avvia", data={"provider": "bonifico"}),
        ):
            _verifica_shell_pagamento(risposta, 410, "scaduto")


def test_pagamento_da_verificare_nella_pagina_react(tmp_path, monkeypatch):
    app = _app_sessione(tmp_path)
    _configura_pagamenti(app)
    lp = _link_pagamento(app)
    messaggio = "Il collegamento richiede una verifica dello studio prima del pagamento."

    def _da_verificare(*_args, **_kwargs):
        raise PaymentCheckoutReview(messaggio)

    monkeypatch.setattr("web.blueprints.pagamenti.vista_link", _da_verificare)
    monkeypatch.setattr("web.blueprints.pagamenti.verifica_ritorno", _da_verificare)
    with app.test_client() as client:
        pagina = client.get(f"/pagamenti/paga/{lp.token}")
        ritorno = client.get(f"/pagamenti/paga/{lp.token}/successo?provider=paypal&token=ORDINE")
        avvio = client.post(f"/pagamenti/paga/{lp.token}/avvia", data={"provider": "bonifico"})
    for risposta in (pagina, ritorno, avvio):
        html = _verifica_shell_pagamento(risposta, 409, "da_verificare")
        assert f'data-messaggio="{messaggio}"' in html
        assert f'data-token="{lp.token}"' in html
        assert "Pagamento da verificare" in html


def test_portale_scaduto_anche_per_i_pdf_risponde_con_la_pagina_react(tmp_path):
    app = _app_sessione(tmp_path)
    mario, _ = _cliente_e_fascicolo(app, "Mario")
    token, scheda = _portale(app, mario.id, vedi_economici=True)
    with app.test_request_context("/"):
        from web.services.portale_cliente_legacy_contesto import gestore_portale

        gestore_portale().revoca(scheda.id)
    with app.test_client() as client:
        for indirizzo in (
            f"/portale/{token}/parcelle/P1/pdf",
            f"/portale/{token}/preventivi/P1/pdf",
            f"/portale/{token}/conferimenti/C1/pdf",
            f"/portale/{token}?_legacy=1",
        ):
            risposta = client.get(indirizzo)
            html = risposta.get_data(as_text=True)
            assert risposta.status_code == 410, indirizzo
            assert 'id="portale-token-react-root"' in html and 'data-stato="scaduto"' in html, indirizzo


def test_template_scaduto_eliminati():
    for nome in ("pagamenti/scaduto.html", "portale/scaduto.html"):
        assert not (RADICE / "web" / "templates" / nome).exists(), nome


def test_collegamento_discordante_mai_500_ma_da_verificare_con_log(tmp_path, monkeypatch, caplog):
    from pct.payment_links_sql import PaymentLinkConflict
    from web.services.pagamenti_link_azioni import MESSAGGIO_LINK_DISCORDANTE

    app = _app_sessione(tmp_path)
    _configura_pagamenti(app)
    lp = _link_pagamento(app)

    def _discordante(*_args, **_kwargs):
        raise PaymentLinkConflict("Collegamento discordante dalla fonte SQL: verifica necessaria.")

    monkeypatch.setattr("web.blueprints.pagamenti.vista_link", _discordante)
    monkeypatch.setattr("web.blueprints.api_v1_portale_token.vista_link", _discordante)
    with caplog.at_level("WARNING"), app.test_client() as client:
        pagina = client.get(f"/pagamenti/paga/{lp.token}")
        api = client.get(f"/api/v1/pubblico/pagamenti/{lp.token}")
    html = _verifica_shell_pagamento(pagina, 409, "da_verificare")
    assert "Il collegamento di pagamento non corrisponde ai dati dello studio" in html
    assert "fonte SQL" not in html
    assert api.status_code == 409
    assert api.get_json() == {"ok": False, "code": "payment_review", "message": MESSAGGIO_LINK_DISCORDANTE}
    assert any("collegamento discordante" in record.getMessage() for record in caplog.records)
