from types import SimpleNamespace
from copy import deepcopy

import pytest

from tests.test_pagamenti_giustizia import _rt_xml
from web.services.pagopa_avvisi_runtime import acquisisci_rt, registra_avviso, leggi_avvisi

NUMERO = '330000000000000001'


class Gestore:
    def __init__(self):
        self.fascicolo = SimpleNamespace(pagamenti={'contributo_unificato': {'status': 'da_pagare'}})
        self.docs = []

    def get(self, fascicolo_id):
        return self.fascicolo if fascicolo_id == 'CASO' else None

    def aggiorna(self, fascicolo_id, **data):
        assert fascicolo_id == 'CASO'
        self.fascicolo.pagamenti = deepcopy(data['pagamenti'])

    def aggiungi_documento(self, *args, **kwargs):
        self.docs.append((args, kwargs))
        return SimpleNamespace(id='DOC')


def registra(g):
    return registra_avviso(g, 'CASO', {'numero_avviso': NUMERO, 'importo': '21,50'}, 'test')


def test_avviso_non_diventa_pagamento_e_non_si_duplica():
    g = Gestore()
    avviso = registra(g)
    registra(g)
    assert len(leggi_avvisi(g, 'CASO')) == 1
    assert g.fascicolo.pagamenti['contributo_unificato']['status'] == 'da_pagare'
    assert avviso['stato'] == 'ricevuta_da_acquisire'
    assert avviso['checkout_url'] == 'https://checkout.pagopa.it/80184430587' + NUMERO


@pytest.mark.parametrize('importo', ['NaN', 'Infinity', '-1', '0', '1.001', '1e1000'])
def test_importi_non_validi_rifiutati(importo):
    with pytest.raises(ValueError):
        registra_avviso(Gestore(), 'CASO', {'numero_avviso': NUMERO, 'importo': importo}, 'test')


@pytest.mark.parametrize('esito,importo,iuv', [('1','21.50',NUMERO[1:]), ('0','22.50',NUMERO[1:]), ('0','21.50','ALTRO')])
def test_ricevuta_non_coerente_non_archivia_o_registra(esito, importo, iuv):
    g = Gestore(); registra(g)
    before = deepcopy(g.fascicolo.pagamenti)
    with pytest.raises(ValueError):
        acquisisci_rt(g, 'CASO', _rt_xml(esito=esito, importo=importo, iuv=iuv), 'test')
    assert not g.docs
    assert g.fascicolo.pagamenti == before


def test_rt_correlata_archiviata_una_volta():
    g = Gestore(); registra(g)
    xml = _rt_xml(importo='21.50', iuv=NUMERO[1:])
    result = acquisisci_rt(g, 'CASO', xml, 'test')
    assert result['documento_id'] == 'DOC'
    assert result['stato'] == 'ricevuta_acquisita'
    acquisisci_rt(g, 'CASO', xml, 'test')
    assert len(g.docs) == 1


def test_altro_fascicolo_non_risolto():
    with pytest.raises(LookupError):
        leggi_avvisi(Gestore(), 'ALTRO')


def test_api_conserva_avviso_senza_pagare_e_archivia_rt(tmp_path, monkeypatch):
    import io
    from requests import Response
    from requests.cookies import RequestsCookieJar
    from pct.fascicoli import TipoFascicolo
    from tests.test_react_shell import _app, _fascicoli_repository
    from tests.test_applicazioni import _crea_operatore, _login
    import web.blueprints.api_v1_react as api

    app = _app(tmp_path)
    _crea_operatore(app)
    gestore = _fascicoli_repository(app)
    fascicolo = gestore.nuovo('Prova avviso', TipoFascicolo.CIVILE)
    body_sent = []

    def risposta(method, url, **kwargs):
        body_sent.append(kwargs['data'])
        response = Response(); response.status_code = 302
        response.cookies = RequestsCookieJar(); response._content = b''
        response.headers['Location'] = '/PST/it/pagopa_inviorich.wp?crs=' + NUMERO + '&importo=21.50&tipologia=Contributo+unificato'
        return response

    monkeypatch.setattr(api.requests, 'request', risposta)
    with app.test_client() as client:
        assert client.get(f'/api/v1/ui/fascicoli/{fascicolo.id}/pagopa/avvisi').status_code in {401, 403}
        _login(client)
        response = client.post(f'/api/v1/ui/pst/pagopa-proxy/it/pagopa_nuovarich.wp?iusentra_fascicolo={fascicolo.id}',
                               data={'tipologia': 'CONTRIB_DIRCANC', 'nominativoPagatore': 'Prova'}, content_type='multipart/form-data')
        assert response.status_code == 302
        assert b'nominativoPagatore' in body_sent[0]
        avvisi = client.get(f'/api/v1/ui/fascicoli/{fascicolo.id}/pagopa/avvisi').get_json()['avvisi']
        assert avvisi[0]['numero_avviso'] == NUMERO
        result = client.post(f'/api/v1/ui/fascicoli/{fascicolo.id}/pagopa/ricevuta',
                             data={'ricevuta': (io.BytesIO(_rt_xml(importo='21.50', iuv=NUMERO[1:])), 'RT.xml')})
        assert result.status_code == 200, result.get_json()
        assert result.get_json()['avviso']['documento_id']
        reloaded = _fascicoli_repository(app).get(fascicolo.id)
        assert len(reloaded.documenti) == 1
        assert reloaded.pagamenti['pagopa_portale']['avvisi'][0]['stato'] == 'ricevuta_acquisita'
