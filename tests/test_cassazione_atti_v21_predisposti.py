"""Otto atti di parte Cassazione degli schemi v21 predisposti ma non attivati.

Fonte: docs/specs/ministero/parte/parte_v21/Parte-cassazione.xsd (XSD_Cassazione_20260227, in
esercizio dal 04/03/2026). Per decisione dello studio restano fuori da catalogo e generatore finche
`pct.cassazione_atti_v21.CASSAZIONE_ATTI_V21_ATTIVI` e False; i test con l'interruttore acceso
dimostrano che all'attivazione ogni atto produce un DatiAtto valido.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree

import pct.cassazione_atti_v21 as atti_v21
import pct.deposito_telematico_catalogo as catalogo
from pct.busta import BustaTelematica
from pct.cassazione_xsd_tables import cassazione_enumeration_values, cassazione_parte_roots, cassazione_parte_schema_path
from scripts.audit_deposito_catalogo_end_to_end import _dati_busta_for, _sample_pdf


def _svuota_cache_catalogo() -> None:
    catalogo.list_deposit_catalog_entries.cache_clear()
    catalogo._entries_by_key.cache_clear()


@pytest.fixture
def attivi(monkeypatch):
    monkeypatch.setattr(atti_v21, "CASSAZIONE_ATTI_V21_ATTIVI", True)
    _svuota_cache_catalogo()
    yield
    monkeypatch.setattr(atti_v21, "CASSAZIONE_ATTI_V21_ATTIVI", False)
    _svuota_cache_catalogo()


@pytest.fixture
def atto_pdf(tmp_path: Path) -> Path:
    return _sample_pdf(tmp_path / "atto.pdf")


@pytest.fixture(scope="module")
def schema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(cassazione_parte_schema_path())))


def _v21_entries() -> dict[str, dict]:
    return {
        entry["key"]: entry
        for entry in catalogo.list_deposit_catalog_entries()
        if entry["key"] in atti_v21.CASSAZIONE_ATTI_V21_KEYS
    }


def test_predisposti_ma_non_attivi_per_impostazione_predefinita():
    _svuota_cache_catalogo()
    payload = catalogo.build_deposit_catalog_payload()

    assert atti_v21.CASSAZIONE_ATTI_V21_ATTIVI is False
    assert len(catalogo.list_deposit_catalog_entries()) == 270
    assert payload["counts"]["totalDepositTypes"] == 270
    assert _v21_entries() == {}


def test_radici_esistono_nello_schema_in_esercizio_e_non_nel_catalogo_decompilato():
    raw_keys = {entry.get("key") for entry in catalogo.load_deposit_catalog_raw()["entries"]}

    assert len(atti_v21.CASSAZIONE_ATTI_V21_ROOTS) == 8
    assert atti_v21.CASSAZIONE_ATTI_V21_ROOTS <= cassazione_parte_roots()
    assert not raw_keys & atti_v21.CASSAZIONE_ATTI_V21_KEYS


def test_generazione_bloccata_finche_non_attivati(attivi, monkeypatch, atto_pdf):
    entry = _v21_entries()["Parte_CASSAZIONE::IstanzaAnticipazioneUdienza"]
    dati = _dati_busta_for(entry, atto_pdf)
    monkeypatch.setattr(atti_v21, "CASSAZIONE_ATTI_V21_ATTIVI", False)

    with pytest.raises(ValueError, match="predisposto ma non ancora attivato"):
        BustaTelematica(dati).crea_dati_atto_xml_per_firma()


def test_con_attivazione_entrano_nel_catalogo_e_generano_datiatto_valido(attivi, schema, atto_pdf):
    entries = _v21_entries()
    payload = catalogo.build_deposit_catalog_payload()

    assert set(entries) == atti_v21.CASSAZIONE_ATTI_V21_KEYS
    assert payload["counts"]["totalDepositTypes"] == 278
    assert payload["counts"]["macroareas"]["Corte di Cassazione (civile)"] == 41
    for key, entry in entries.items():
        assert entry["quickOrganizer"]["mappingSource"] == atti_v21.CASSAZIONE_ATTI_V21_SOURCE
        assert entry["rules"]["real_send_allowed_from_pct_panel"] is True, key
        root = etree.fromstring(BustaTelematica(_dati_busta_for(entry, atto_pdf)).crea_dati_atto_xml_per_firma())
        assert etree.QName(root).localname == key.split("::")[1]
        assert schema.validate(etree.ElementTree(root)), (key, str(schema.error_log.last_error))
    for key in atti_v21.CASSAZIONE_ATTI_V21_INTRODUTTIVI_KEYS:
        assert entries[key]["schema"]["contributionXmlMode"] == "cassazione_spese_giustizia"


def test_motivi_di_revocazione_seguono_le_tabelle_ministeriali(attivi, atto_pdf):
    for root_name, article_type in (("RevocazioneExArt391ter", "Art395Num"), ("RevocazioneExArt391quater", "Art391QuaterNum")):
        entry = _v21_entries()[f"Parte_CASSAZIONE::{root_name}"]
        field = next(item for item in entry["schema"]["inputFields"] if item["id"] == "motivi_revocazione_cassazione")
        assert {option["value"] for option in field["options"]} == set(cassazione_enumeration_values(article_type))

    entry = _v21_entries()["Parte_CASSAZIONE::RevocazioneExArt391quater"]
    dati = _dati_busta_for(entry, atto_pdf)
    fuori_tabella = replace(
        dati,
        datiatto_extra={**dati.datiatto_extra, "motivi_revocazione_cassazione": [{"numero": "1", "numero_articolo": "6"}]},
    )
    with pytest.raises(ValueError, match="motivo di revocazione non validi"):
        BustaTelematica(fuori_tabella).crea_dati_atto_xml_per_firma()


def test_oscuramento_richiede_codice_fiscale_valido(attivi, atto_pdf):
    entry = _v21_entries()["Parte_CASSAZIONE::IstanzaOscuramento"]
    dati = _dati_busta_for(entry, atto_pdf)
    errato = replace(dati, datiatto_extra={**dati.datiatto_extra, "oscuramento_parte_codice_fiscale": "ROSSI"})

    with pytest.raises(ValueError, match="Codice fiscale della parte da oscurare non valido"):
        BustaTelematica(errato).crea_dati_atto_xml_per_firma()
