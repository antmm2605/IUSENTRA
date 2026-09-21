"""Regressioni del CAPTCHA pubblico PST osservato il 21/09/2026."""

from urllib.parse import parse_qs, urlsplit

import pytest

from web.blueprints.api_v1_react import (
    _pst_pagopa_proxy_href,
    _pst_pagopa_rewrite_text,
    _pst_pagopa_safe_path,
)

BASE = "https://servizipst.giustizia.it/PST/it/pagopa_nuovarich.wp"
CAPTCHA = "do/consultazionepubblica/captcha/image"


def test_markup_ministeriale_preserva_src_vuoto_e_assegnazione_javascript():
    html = '''<img id="captchaImg" src="" alt="CAPTCHA" />
<script>
var captchaEndpoint = '/PST/do/consultazionepubblica/captcha/image';
function loadCaptcha() {
    document.getElementById('captchaImg').src = captchaEndpoint + '?ts=' + Date.now();
    document.getElementById('captCode').value = '';
}
</script>'''
    result = _pst_pagopa_rewrite_text(html, base_url=BASE, fascicolo_id="CASE")
    assert 'src=""' in result
    assert "document.getElementById('captchaImg').src = captchaEndpoint + '?ts=' + Date.now();" in result
    assert "captchaEndpoint = '/api/v1/ui/pst/pagopa-proxy/" + CAPTCHA + "';" in result
    assert "%22%22" not in result


def test_timestamp_captcha_non_diventa_parte_del_contesto_fascicolo():
    endpoint = _pst_pagopa_proxy_href("/PST/" + CAPTCHA, base_url=BASE, fascicolo_id="CASE")
    assert parse_qs(urlsplit(endpoint + "?ts=123456").query) == {"ts": ["123456"]}
    assert _pst_pagopa_safe_path(CAPTCHA) == CAPTCHA


@pytest.mark.parametrize("path", [
    CAPTCHA + "/altro",
    "do/consultazionepubblica/captcha/admin",
    "do/consultazionepubblica/altro",
    "do/../consultazionepubblica/captcha/image",
    "https://example.org/captcha/image",
])
def test_eccezione_captcha_non_apre_altri_percorsi(path):
    assert _pst_pagopa_safe_path(path) == ""


def test_link_documenti_e_form_mantengono_il_fascicolo():
    html = '<form action="/PST/it/pagopa_altripag.wp"><img src=/PST/resources/logo.png></form>'
    result = _pst_pagopa_rewrite_text(html, base_url=BASE, fascicolo_id="CASE")
    assert 'action="/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp?iusentra_fascicolo=CASE"' in result
    assert 'src=/api/v1/ui/pst/pagopa-proxy/resources/logo.png?iusentra_fascicolo=CASE' in result


def test_form_ministeriale_decodifica_amp_prima_dei_parametri():
    from html.parser import HTMLParser

    class FormParser(HTMLParser):
        action = ""

        def handle_starttag(self, tag, attrs):
            if tag == "form":
                self.action = dict(attrs)["action"]

    action = "/PST/it/pagopa_nuovarich.wp?actionPath=/ExtStr2/do/pagamentitelematici/inviaRichiestaAltriPagamenti&amp;currentFrame=8"
    result = _pst_pagopa_rewrite_text(
        f'<form action="{action}" method="post"></form>', base_url=BASE, fascicolo_id="CASE",
    )
    parser = FormParser()
    parser.feed(result)
    query = parse_qs(urlsplit(parser.action).query)
    assert query == {
        "actionPath": ["/ExtStr2/do/pagamentitelematici/inviaRichiestaAltriPagamenti"],
        "currentFrame": ["8"],
        "iusentra_fascicolo": ["CASE"],
    }


def test_controlli_sicurezza_conservano_multipart_originale():
    from flask import Flask, request
    from werkzeug.datastructures import MultiDict
    from web.services.backend_security import backend_control_violations_for_request
    app = Flask(__name__)
    with app.test_request_context(
        '/api/v1/ui/pst/pagopa-proxy/it/pagopa_nuovarich.wp', method='POST',
        data=MultiDict([('nominativoPagatore', 'Dati di prova'), ('importo', '21.50'),
                        ('opzione', 'uno'), ('opzione', 'due')]), content_type='multipart/form-data',
    ):
        size = request.content_length
        assert not backend_control_violations_for_request(request)
        assert not backend_control_violations_for_request(request)
        assert len(request.get_data()) == size
        assert request.form.getlist('opzione') == ['uno', 'due']
        assert b'Dati di prova' in request.get_data()
