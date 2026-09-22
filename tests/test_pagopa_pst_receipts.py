from contextlib import nullcontext

import pytest

from tests.test_pagamenti_giustizia import _rt_xml
from web.services import pagopa_pst_receipts as pst

NUMBER = "330000000000000001"
CF = "RSSMRA80A01H501U"


class Response:
    status_code = 200

    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.content


def session(monkeypatch, html, receipt=None):
    calls = []

    class Session:
        headers = {}

        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            assert self.verify == "official-ca.pem"
            assert kwargs["allow_redirects"] is False
            return nullcontext(Response(receipt if len(calls) == 2 else b"<html/>"))

        def post(self, url, **kwargs):
            assert self.headers["Accept-Language"].startswith("it-IT")
            assert kwargs["files"]["crs"] == (None, NUMBER)
            assert kwargs["files"]["codiceFiscalePagatore"] == (None, CF)
            assert kwargs["allow_redirects"] is False
            return nullcontext(Response(html.encode()))

    monkeypatch.setattr(pst.requests, "Session", lambda: nullcontext(Session()))
    return calls


def test_recupera_rt_dalla_sola_riga_corrispondente(monkeypatch):
    receipt = _rt_xml(iuv=NUMBER[1:], importo="21.50")
    html = f'<table id="richiesta"><tr><td>{NUMBER}</td><td><a href="{pst.RECEIPT_PATH}?crs=reference">RT</a></td></tr></table>'
    calls = session(monkeypatch, html, receipt)
    assert pst.recupera_rt(NUMBER, CF, verify="official-ca.pem") == receipt
    assert len(calls) == 2


@pytest.mark.parametrize("url", ["https://example.org/RT.xml", "//example.org" + pst.RECEIPT_PATH, "/PST/do/pagamentitelematici/eliminaAvviso.action"])
def test_non_segue_link_esterni_o_operazioni_diverse(monkeypatch, url):
    html = f'<table id="richiesta"><tr><td>{NUMBER}</td><td><a href="{url}">RT</a></td></tr></table>'
    calls = session(monkeypatch, html)
    assert pst.recupera_rt(NUMBER, CF, verify="official-ca.pem") is None
    assert len(calls) == 1


def test_html_incompleto_non_equivale_a_ricevuta_assente(monkeypatch):
    session(monkeypatch, '<html><input name="codiceFiscalePagatore"></html>')
    with pytest.raises(ValueError, match="ricerca incompleta"):
        pst.recupera_rt(NUMBER, CF, verify="official-ca.pem")


def test_ricevuta_di_altro_avviso_rifiutata(monkeypatch):
    html = f'<table id="richiesta"><tr><td>{NUMBER}</td><td><a href="{pst.RECEIPT_PATH}?crs=reference">RT</a></td></tr></table>'
    session(monkeypatch, html, _rt_xml(iuv="ALTRO", importo="21.50"))
    with pytest.raises(ValueError, match="avviso richiesto"):
        pst.recupera_rt(NUMBER, CF, verify="official-ca.pem")


def test_risposta_eccessiva_rifiutata():
    with pytest.raises(ValueError, match="limite"):
        pst._body(Response(b"x" * (pst.MAX_BYTES + 1)))
