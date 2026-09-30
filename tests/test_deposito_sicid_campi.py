"""Regressione dei requisiti, senza firma, dispositivi o invio PEC."""

from dataclasses import replace

import pytest
from lxml import etree

from pct.busta import BustaTelematica
from pct.datiatto_xsd import validate_datiatto_xml
from pct.deposito_sicid_campi import SICID_ATTI_SENZA_ISTANZA_MANUALE
from pct.deposito_studio_telematico_validation import validate_studio_telematico_deposit
from pct.deposito_telematico_catalogo import resolve_deposit_type_payload
from scripts.audit_deposito_catalogo_end_to_end import _dati_busta_for, _sample_pdf


@pytest.mark.parametrize("key", sorted(SICID_ATTI_SENZA_ISTANZA_MANUALE))
def test_campi_sicid_non_bloccano_xml_senza_istanza_manuale(key, tmp_path):
    entry = resolve_deposit_type_payload(key)
    assert entry is not None
    fields = {field["id"]: field for field in entry["schema"]["inputFields"]}
    assert "cci" not in fields
    assert "istanza" not in fields
    assert fields["sub_procedimento"]["required"] is False
    assert fields["sub_procedimento"]["group"] == "Dati facoltativi del deposito"

    dati = _dati_busta_for(entry, _sample_pdf(tmp_path / "atto.pdf"))
    extra = dict(dati.datiatto_extra)
    for field in ("cci", "sub_procedimento", "istanza"):
        extra.pop(field, None)
    dati = replace(dati, datiatto_extra=extra, allegati=[])
    findings = validate_studio_telematico_deposit(
        key=key,
        context={"datiatto_extra": extra},
        selected_documents=[],
    )
    assert not any(finding["field"] == "istanza" for finding in findings)

    xml = BustaTelematica(dati).crea_dati_atto_xml_per_firma()
    validation = validate_datiatto_xml(xml)
    assert validation.ok, validation
    root = etree.fromstring(xml)
    # Il documento operativo resta principale; l'indice PDF generato è aggiuntivo.
    index = root.xpath("./*[local-name()='IndiceBusta']")[0]
    assert len(index.xpath("./*[local-name()='AttoPrincipale']")) == 1
    main_id = index.xpath("./*[local-name()='AttoPrincipale']")[0].get("id")
    assert all(node.get("id") != main_id for node in index.xpath("./*[local-name()='AllegatoSemplice']"))
    invalid = etree.fromstring(xml)
    invalid_index = invalid.xpath("./*[local-name()='IndiceBusta']")[0]
    invalid_index.remove(invalid_index.xpath("./*[local-name()='AttoPrincipale']")[0])
    assert not validate_datiatto_xml(etree.tostring(invalid)).ok
    suffix = key.rsplit("::", 1)[-1]
    if suffix in {"Memoria171ter1", "Repliche171ter2", "Controrepliche171ter3", "IstanzaAccoglimentoDomanda183ter"}:
        assert len(root.xpath(f"./*[local-name()='istanze']/*[local-name()='{suffix}']")) == 1


def test_altri_tipi_conservano_requisito_istanza_e_dati_obbligatori():
    key = "Introduttivi_SICID::Citazione"
    entry = resolve_deposit_type_payload(key)
    assert entry is not None
    assert any(field["id"] == "istanza" and field["required"] for field in entry["schema"]["inputFields"])
    findings = validate_studio_telematico_deposit(key=key, context={}, selected_documents=[])
    assert any(finding["field"] == "istanza" for finding in findings)
    findings = validate_studio_telematico_deposit(
        key="Parte_SICID::Memoria171ter1",
        context={},
        selected_documents=[],
    )
    assert any(finding["field"] == "numero_rg" for finding in findings)
