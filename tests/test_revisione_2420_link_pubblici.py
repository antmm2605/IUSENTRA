"""Revisione 2.420.0: link pubblici sconosciuti e caricamenti del portale."""

from __future__ import annotations


def test_link_sconosciuto_non_rilegge_tutti_gli_studi(monkeypatch):
    from flask import Flask, g

    import web.services.token_pubblici_tenant as risolutore

    risolutore.dimentica_negativi()
    letture: list[str] = []

    class Studio:
        def __init__(self, slug: str):
            self.slug = slug
            self.stato = "ATTIVO"

    class Registro:
        def __init__(self, registry_path: str):
            pass

        def lista(self):
            letture.append("lista")
            return [Studio("a"), Studio("b")]

        def get(self, slug):
            return Studio(slug)

        def percorsi_dati(self, slug, **_kw):
            return {"slug": slug}

    import pct.tenant as tenant

    monkeypatch.setattr(tenant, "GestioneTenant", Registro)
    app = Flask(__name__)
    app.config.update(MULTI_TENANT=True, TENANTS_REGISTRY="registro.json")
    verifiche: list[str] = []

    def verifica(studio, _percorsi):
        verifiche.append(studio.slug)
        return False

    with app.test_request_context("/"):
        for _ in range(5):
            assert risolutore.risolvi_studio_da_token("token-inventato", verifica=verifica, cache={}, etichetta="prova") is False
        assert not getattr(g, "data_paths", None)
    # Un solo giro sugli studi: le richieste successive dello stesso link sconosciuto
    # rispondono subito «non trovato».
    assert letture == ["lista"] and verifiche == ["a", "b"]
    risolutore.dimentica_negativi()


def test_richiamata_satispay_in_get_registra_il_pagamento_confermato(tmp_path, monkeypatch):
    import web.blueprints.pagamenti as modulo
    from tests.test_pagamenti_webhook_studi import _stato_singolo, _studio_singolo

    app, lp = _studio_singolo(tmp_path)
    verifiche = []
    monkeypatch.setattr(modulo, "satispay_pagamento_confermato", lambda gp, pagamento, link: verifiche.append((pagamento, link.id)) or True)
    with app.test_client() as client:
        risposta = client.get(f"/pagamenti/webhooks/satispay?link_id={lp.id}&payment_id=PAG-1")
    assert risposta.status_code == 200 and risposta.get_json()["verified"] is True
    assert verifiche == [("PAG-1", lp.id)]
    assert _stato_singolo(app, lp) == "PAGATO"
