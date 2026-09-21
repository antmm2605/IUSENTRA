from types import SimpleNamespace

import pytest

from web.services.pagopa_prefill import dati_precompilazione


def test_anagrafica_e_avviso_restano_fonti_distinte():
    cliente = SimpleNamespace(nome_completo="Cliente Test", identificativo_fiscale="CFCLIENTE")
    values = dati_precompilazione(None, cliente, [
        {"numero_avviso": "330000000000000001", "codice_fiscale_debitore": "CFAVVISO"},
    ])
    assert values["nominativoPagatore"] == "Cliente Test"
    assert values["codiceFiscale"] == "CFCLIENTE"
    assert values["codiceFiscalePagatore"] == "CFAVVISO"
    assert values["crs"] == "330000000000000001"


def test_non_indovina_debitore_o_avviso_ambiguo():
    values = dati_precompilazione(None, None, [
        {"numero_avviso": "330000000000000001"},
        {"numero_avviso": "330000000000000002"},
    ])
    assert not any(values.values())


@pytest.mark.parametrize("action", ["xmlDetailsBolli.action", "pdfDetailsBolli.action"])
def test_download_ricevute_pst_consente_solo_endpoint_ufficiali(action):
    from web.blueprints.api_v1_react import _pst_pagopa_safe_path

    path = "do/pagamentitelematici/" + action
    assert _pst_pagopa_safe_path(path) == path
    assert _pst_pagopa_safe_path(path + "/altro") == ""
    assert _pst_pagopa_safe_path("do/pagamentitelematici/elimina.action") == ""
