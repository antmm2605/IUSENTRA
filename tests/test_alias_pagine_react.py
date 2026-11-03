"""Gli alias storici dei portali e dei conferimenti portano alla pagina React canonica invece di un 404."""

from __future__ import annotations

import pytest

from tests.test_strumenti_legali import _cfg_web

ALIAS = {
    "/pst": "/polisweb",
    "/ptt": "/sigit",
    "/portali": "/telematico",
    "/portali/pst": "/polisweb",
    "/portali/pdp": "/pdp",
    "/portali/pat": "/pat",
    "/portali/ptt": "/sigit",
    "/portali/sigit": "/sigit",
    "/telematici": "/telematico",
    "/preventivi/conferimento": "/preventivi?metric=conferimenti",
}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path_factory.mktemp("alias")))
    with app.test_client() as c:
        c.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        yield c


@pytest.mark.parametrize("alias,canonica", sorted(ALIAS.items()))
def test_alias_reindirizza_alla_pagina_canonica(client, alias, canonica):
    risposta = client.get(alias, headers={"Accept": "text/html"})
    assert risposta.status_code == 302
    assert risposta.headers["Location"] == canonica
    assert client.get(canonica, headers={"Accept": "text/html"}).status_code == 200


def test_alias_conserva_i_parametri(client):
    risposta = client.get("/portali/pst?numero=12", headers={"Accept": "text/html"})
    assert risposta.headers["Location"] == "/polisweb?numero=12"


def test_alias_conferimenti_conserva_il_filtro_e_i_parametri(client):
    risposta = client.get("/preventivi/conferimento?q=x", headers={"Accept": "text/html"})
    assert risposta.headers["Location"] == "/preventivi?metric=conferimenti&q=x"


def test_acquisizione_resta_servita_direttamente(client):
    assert client.get("/portali/pst/acquisizione", headers={"Accept": "text/html"}).status_code == 200
