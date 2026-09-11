"""DatiAtto Cassazione sugli schemi degli atti di parte in esercizio.

Fonte: PST, XSD_Cassazione_20260227 (Processo Telematico di legittimita - Schemi XSD v.21),
in esercizio dal 04/03/2026; schemi versionati in docs/specs/ministero/parte/. Prima di questa
versione IUSENTRA generava gli atti con i namespace v13, otto versioni indietro: mancavano i
ruoli e i riti aggiunti per identificare il fascicolo di grado precedente e restava selezionabile
il tipo "RicorsoPerRevocazione", eliminato dalla v16.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree

from pct.busta import CASSAZIONE_ATTI_NS, CASSAZIONE_PARTE_NS, BustaTelematica
from pct.cassazione_xsd_tables import cassazione_enumeration_values, cassazione_parte_schema_path
from pct.datiatto_xsd import _SCHEMA_ROOTS
from pct.deposito_datiatto_fields import datiatto_input_fields
from pct.deposito_telematico_catalogo import CASSAZIONE_ROOT_ELIMINATA_STATUS, list_deposit_catalog_entries
from pct.pst_catalog import PST_CASSAZIONE_XSD_ACTIVE_VERSION, get_xsd_channel
from scripts.audit_deposito_catalogo_end_to_end import _dati_busta_for, _sample_pdf


def _cassazione_entries() -> list[dict]:
    return [
        entry
        for entry in list_deposit_catalog_entries()
        if str(entry["schema"].get("generatorClass") or "").startswith("ParteCassazione")
    ]


def _entry(key: str) -> dict:
    return next(entry for entry in _cassazione_entries() if entry["key"] == key)


@pytest.fixture(scope="module")
def schema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(cassazione_parte_schema_path())))


@pytest.fixture
def atto_pdf(tmp_path: Path) -> Path:
    return _sample_pdf(tmp_path / "atto.pdf")


def test_versione_attiva_coincide_con_pacchetto_in_esercizio_e_validatore():
    channel = get_xsd_channel("CASSAZIONE")

    assert channel.production_ready is True
    assert channel.package_name == "XSD_Cassazione_20260227.zip"
    assert PST_CASSAZIONE_XSD_ACTIVE_VERSION == "v21"
    assert CASSAZIONE_PARTE_NS.endswith("/cassazione/Parte/v21")
    assert CASSAZIONE_ATTI_NS.endswith("/cassazione/tipi/atti/v21")
    assert any(root.name == "parte_v21" for root in _SCHEMA_ROOTS)
    assert not any(root.name == "parte_v13" for root in _SCHEMA_ROOTS)


def test_ogni_atto_cassazione_del_catalogo_e_valido_sugli_schemi_in_esercizio(schema, atto_pdf):
    generated = 0
    for entry in _cassazione_entries():
        if entry["schema"]["status"] == CASSAZIONE_ROOT_ELIMINATA_STATUS:
            continue
        root = etree.fromstring(BustaTelematica(_dati_busta_for(entry, atto_pdf)).crea_dati_atto_xml_per_firma())
        assert etree.QName(root).namespace == CASSAZIONE_PARTE_NS, entry["key"]
        assert schema.validate(etree.ElementTree(root)), (entry["key"], str(schema.error_log.last_error))
        generated += 1
    assert generated == 32


def test_memoria_380_bis_eliminata_dal_ministero_non_e_inviabile(atto_pdf):
    entry = _entry("Parte_CASSAZIONE::Memoria380bis")

    assert "Memoria380bis" not in cassazione_etree_roots()
    assert entry["schema"]["status"] == CASSAZIONE_ROOT_ELIMINATA_STATUS
    assert entry["rules"]["real_send_allowed_from_pct_panel"] is False
    assert entry["rules"]["ministerial_act_eliminated"] is True
    assert "non può essere depositato" in entry["rules"]["real_send_blocker"]
    with pytest.raises(ValueError, match="Dati del deposito non conformi"):
        BustaTelematica(_dati_busta_for(entry, atto_pdf)).crea_dati_atto_xml_per_firma()


def cassazione_etree_roots() -> set[str]:
    root = etree.parse(str(cassazione_parte_schema_path())).getroot()
    return {node.get("name") for node in root.findall("{http://www.w3.org/2001/XMLSchema}element")}


def test_tipi_di_ricorso_offerti_sono_quelli_dello_schema_in_esercizio(atto_pdf):
    fields = datiatto_input_fields("Parte_CASSAZIONE::Ricorso", "ParteCassazione", "Ricorso")
    tipo = next(field for field in fields if field["id"] == "tipo_ricorso_cassazione")

    assert {option["value"] for option in tipo["options"]} == set(cassazione_enumeration_values("TipoRicorso"))
    assert "RicorsoPerRevocazione" not in {option["value"] for option in tipo["options"]}

    dati = _dati_busta_for(_entry("Parte_CASSAZIONE::Ricorso"), atto_pdf)
    revocazione = replace(dati, datiatto_extra={**dati.datiatto_extra, "tipo_ricorso_cassazione": "RicorsoPerRevocazione"})
    with pytest.raises(ValueError, match="ricorso per revocazione non è più un tipo di ricorso"):
        BustaTelematica(revocazione).crea_dati_atto_xml_per_firma()


def test_provvedimento_impugnato_accetta_ruoli_e_riti_aggiunti_dalla_v21(schema, atto_pdf):
    dati = _dati_busta_for(_entry("Parte_CASSAZIONE::Ricorso"), atto_pdf)
    provvedimento = {
        "ufficio": "0580010",
        "ruolo": "ProcedimentoUnitario",
        "rito": "PULiquidazioneGiudiziale",
        "numero_fascicolo": "12",
        "anno_fascicolo": "2025",
        "numero_cci": "3",
    }
    concorsuale = replace(dati, datiatto_extra={**dati.datiatto_extra, "provvedimento_impugnato": provvedimento})

    root = etree.fromstring(BustaTelematica(concorsuale).crea_dati_atto_xml_per_firma())
    fascicolo = root.find(f"{{{CASSAZIONE_PARTE_NS}}}Provvedimento/{{{CASSAZIONE_ATTI_NS}}}DatiFascicolo")

    assert schema.validate(etree.ElementTree(root)), str(schema.error_log.last_error)
    assert [etree.QName(child).localname for child in fascicolo] == ["Ufficio", "Ruolo", "Rito", "Numero", "NumeroCCI", "Anno"]
    assert fascicolo.findtext(f"{{{CASSAZIONE_ATTI_NS}}}Rito") == "PULiquidazioneGiudiziale"

    rito_errato = replace(
        dati,
        datiatto_extra={**dati.datiatto_extra, "provvedimento_impugnato": {**provvedimento, "rito": "RitoInventato"}},
    )
    with pytest.raises(ValueError, match="Rito del fascicolo impugnato non valido"):
        BustaTelematica(rito_errato).crea_dati_atto_xml_per_firma()


def test_segnalazione_errore_materiale_richiede_raccolta_generale_del_provvedimento(atto_pdf):
    entry = _entry("Parte_CASSAZIONE::SegnalazioneErroreMateriale")
    field_ids = {field["id"] for field in entry["schema"]["inputFields"]}
    dati = _dati_busta_for(entry, atto_pdf)
    extra = {
        key: value
        for key, value in dati.datiatto_extra.items()
        if key != "numero_raccolta_generale_provvedimento"
    }

    assert {"numero_raccolta_generale_provvedimento", "anno_raccolta_generale_provvedimento"} <= field_ids
    with pytest.raises(ValueError, match="Numero di raccolta generale del provvedimento mancante"):
        BustaTelematica(replace(dati, datiatto_extra=extra)).crea_dati_atto_xml_per_firma()
