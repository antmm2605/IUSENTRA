"""Il caso INPS viene respinto prima del passaggio al Local Signer."""
from copy import deepcopy
from dataclasses import replace

import pytest
from lxml import etree

from pct.busta import BustaTelematica
from pct.datiatto_xsd import validate_datiatto_xml
from pct.deposito_telematico_catalogo import resolve_deposit_type_payload
from pct.deposito_sicid_campi import SICID_ATTI_SENZA_ISTANZA_MANUALE
from scripts.audit_deposito_catalogo_end_to_end import _dati_busta_for, _sample_pdf
from web.services.deposito_signature_runtime import dati_atto_signature_gate


def _case(tmp_path, duplicate):
    entry = resolve_deposit_type_payload("Introduttivi_SICID::Citazione")
    dati = _dati_busta_for(entry, _sample_pdf(tmp_path / "ricorso.pdf"))
    root = etree.fromstring(dati.anagrafica_procedimento_xml)
    parties = root.xpath("./*[local-name()='Partecipanti']")[0]
    inps = parties[1]
    inps.xpath("./*[local-name()='codiceFiscale']")[0].text = "80078750587"
    inps.xpath("./*[local-name()='denominazione']")[0].text = "INPS"
    if duplicate:
        other = deepcopy(inps)
        other.set("ID", "controparte_inps_duplicata")
        parties.append(other)
    return replace(dati, anagrafica_procedimento_xml=etree.tostring(root)), root


def test_inps_unico_genera_xml_valido(tmp_path):
    dati, _ = _case(tmp_path, False)
    payload = BustaTelematica(dati).crea_dati_atto_xml_per_firma()
    assert validate_datiatto_xml(payload).ok


def test_citazione_richiede_una_data_senza_istanza_aggiuntiva(tmp_path):
    entry = resolve_deposit_type_payload('Introduttivi_SICID::Citazione')
    fields = entry['schema']['inputFields']
    assert {field['id'] for field in fields if field['required']} == {'data_notifica_citazione'}
    dati, _ = _case(tmp_path, False)
    extra = {key: value for key, value in dati.datiatto_extra.items() if key not in {'istanza', 'data_atto_deposito'}}
    payload = BustaTelematica(replace(dati, datiatto_extra=extra)).crea_dati_atto_xml_per_firma()
    assert validate_datiatto_xml(payload).ok
    root = etree.fromstring(payload)
    assert root.get('Datacitazione') == '2026-06-30'
    assert not root.xpath("./*[local-name()='istanze']")


@pytest.mark.parametrize('key', sorted(SICID_ATTI_SENZA_ISTANZA_MANUALE))
def test_campi_generici_non_consumati_non_cambiano_xml_ministeriale(key, tmp_path):
    entry = resolve_deposit_type_payload(key)
    assert 'istanza' not in {field['id'] for field in entry['schema']['inputFields']}
    dati = _dati_busta_for(entry, _sample_pdf(tmp_path / 'atto.pdf'))
    extra = {**dati.datiatto_extra, 'istanza': 'COLLAUDO', 'data_atto_deposito': '2026-06-30'}
    busta = BustaTelematica(replace(dati, datiatto_extra=extra))
    before = busta.crea_dati_atto_xml_per_firma()
    busta.dati = replace(dati, datiatto_extra={k: v for k, v in extra.items() if k not in {'istanza', 'data_atto_deposito'}})
    after = busta.crea_dati_atto_xml_per_firma()
    assert before == after
    assert validate_datiatto_xml(after).ok


def test_inps_duplicato_blocca_generazione_senza_rimuovere_parti(tmp_path):
    dati, source = _case(tmp_path, True)
    before = etree.tostring(source)
    with pytest.raises(ValueError, match="80078750587") as exc:
        BustaTelematica(dati).crea_dati_atto_xml_per_firma()
    assert "AK_PARTECIPANTI" in str(exc.value)
    assert "Codice fiscale 80078750587 ripetuto" in str(exc.value)
    assert "controparte_inps_duplicata" in str(exc.value)
    assert etree.tostring(source) == before
    assert len(source.xpath("./*[local-name()='Partecipanti']/*")) == 3


def test_gate_non_richiede_firma_ne_prepara_pacchetto_con_duplicati(tmp_path):
    dati, _ = _case(tmp_path, True)
    payload, response = dati_atto_signature_gate(
        {}, BustaTelematica(dati), id_deposito="collaudo-duplicati",
        timestamp="2026-10-20T12:00:00+02:00", pec_dest="", tipo_atto="Citazione",
        oggetto_pec="collaudo senza invio", corpo_pec="", documenti_busta=[],
    )
    assert payload is None
    assert response["_status"] == 400
    assert response["package_ready"] is False
    assert response["requires_guided_completion"] is True
    assert "requires_local_signature" not in response
    assert "80078750587" in response["errore"]


def test_cf_avvocato_uguale_a_parte_non_e_duplicato_partecipanti(tmp_path):
    dati, root = _case(tmp_path, False)
    party_cf = root.xpath("./*[local-name()='Partecipanti']/*[1]/*[local-name()='codiceFiscale']")[0].text
    root.xpath("./*[local-name()='Soggetti']/*[local-name()='Avvocato']/*[local-name()='codiceFiscale']")[0].text = party_cf
    dati = replace(dati, anagrafica_procedimento_xml=etree.tostring(root))
    assert validate_datiatto_xml(BustaTelematica(dati).crea_dati_atto_xml_per_firma()).ok
