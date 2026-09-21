from types import SimpleNamespace

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
