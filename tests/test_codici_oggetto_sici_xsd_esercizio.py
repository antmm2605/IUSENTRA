"""Il catalogo codici oggetto SICID deve coincidere con gli XSD SICI in esercizio.

Fonte: PST, XSD_SICI_20260720 (pubblicato 22/07/2026, in esercizio dal 19/10/2026) e
Nota modifiche XSD dell'11/05/2026: descrizione dell'oggetto 171404 corretta perche
induceva in errore, nuovi oggetti CCI 471404, 471405, 471412-471419.
"""

import json
from pathlib import Path

from pct.datiatto_xsd import _SCHEMA_ROOTS
from pct.guida_pratica.sici_catalog_alignment import load_sici_codici_oggetto
from pct.pratiche_collegate_catalog import codice_oggetto_pst_payload, normalize_codice_oggetto_pst
from pct.pst_catalog import PST_SICI_XSD_ACTIVE_TIPI_BASE, get_xsd_channel

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "pct" / "data" / "cataloghi" / "codici_oggetto_pst.json"
UI_CATALOG = ROOT / "pct" / "data" / "cataloghi" / "codici_oggetto_pst_ui.json"
NUOVI_CCI = ("471404", "471405", "471412", "471413", "471414", "471415", "471416", "471417", "471418", "471419")


def _official() -> dict[str, str]:
    return load_sici_codici_oggetto(ROOT / PST_SICI_XSD_ACTIVE_TIPI_BASE)


def _records(path: Path) -> dict[str, dict]:
    return {row["codice"]: row for row in json.loads(path.read_text(encoding="utf-8"))["records"]}


def test_xsd_sici_attivo_coincide_con_canale_in_esercizio_e_validatore():
    channel = get_xsd_channel("SICI")
    package_dir = Path(channel.package_name).stem

    assert channel.production_ready is True
    assert package_dir in PST_SICI_XSD_ACTIVE_TIPI_BASE
    assert any((ROOT / PST_SICI_XSD_ACTIVE_TIPI_BASE).is_relative_to(root) for root in _SCHEMA_ROOTS)


def test_ogni_codice_oggetto_sici_ufficiale_e_nel_registro_sicid_con_descrizione_ministeriale():
    official = _official()
    catalog = _records(CATALOG)

    assert len(official) == 835
    for code, description in official.items():
        record = catalog[code]
        assert record["registri"][0] == "SICID", code
        assert record["descrizioniPerRegistro"]["SICID"] == description, code
        assert record["descrizione"] == description, code
        assert record["fileFonte"].startswith("XSD_SICI_20260720/"), code


def test_registro_sicid_non_contiene_codici_assenti_dagli_xsd_in_esercizio():
    official = _official()
    sicid = {code for code, record in _records(CATALOG).items() if "SICID" in record["registri"]}

    assert sicid == set(official)


def test_171404_ha_la_descrizione_corretta_dal_ministero():
    record = _records(CATALOG)["171404"]
    ui_record = _records(UI_CATALOG)["171404"]
    corretta = "Reclamo avverso il rigetto della dichiarazione dello stato di insolvenza (Marzano)"

    assert record["descrizione"] == corretta
    assert "Esdebitazione del Debitore Incapiente (CCI)" not in record["descrizioniAlternative"]
    assert ui_record["descrizione"] == corretta


def test_nuovi_oggetti_cci_sono_depositabili_sul_sicid():
    catalog = _records(CATALOG)
    ui_catalog = _records(UI_CATALOG)

    for code in NUOVI_CCI:
        assert catalog[code]["registri"][:1] == ["SICID"], code
        assert "SICID" in ui_catalog[code]["registri"], code
    assert normalize_codice_oggetto_pst("Esdebitazione del Debitore Incapiente (CCI)") == "471404"
    assert codice_oggetto_pst_payload("471404")["file_fonte_codice_oggetto"].startswith("XSD_SICI_20260720/")


def test_catalogo_ui_e_la_proiezione_esatta_del_catalogo_tecnico():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    ui_catalog = json.loads(UI_CATALOG.read_text(encoding="utf-8"))
    keys = list(ui_catalog["records"][0].keys())

    assert ui_catalog["versione"] == catalog["versione"]
    assert ui_catalog["totaleCodici"] == len(catalog["records"])
    assert ui_catalog["records"] == [{key: row.get(key) for key in keys} for row in catalog["records"]]
    sici_source = next(item for item in catalog["fonti"] if item["registro"] == "SICID")
    assert sici_source["zipFonte"] == "XSD_SICI_20260720.zip"


def test_tredici_nuovi_codici_luglio_sono_attivi_con_provenienza_e_decorrenza():
    from pct.pst_catalog import PST_SICI_XSD_20260722_NEW_OBJECT_CODES

    catalog = _records(CATALOG)
    for code in PST_SICI_XSD_20260722_NEW_OBJECT_CODES:
        row = catalog[code]
        assert row["registri"] == ["SICID"]
        assert row["validoDal"] == "2026-10-19"
        assert row["descrizione"] == _official()[code]
        assert codice_oggetto_pst_payload(code)["file_fonte_codice_oggetto"] == row["fileFonte"]


def test_tutti_entry_point_attivi_compilano_con_xsd_ufficiali():
    from lxml import etree
    from pct.ministerial_xsd_catalog import active_schema_paths

    for path in active_schema_paths():
        etree.XMLSchema(etree.parse(str(path)))


def test_eventi_ufficiali_comprendono_documentazione_infocamere():
    from lxml import etree

    path = (ROOT / PST_SICI_XSD_ACTIVE_TIPI_BASE).with_name("eventi.xsd")
    root = etree.parse(str(path))
    assert root.xpath(
        "//xs:enumeration[@value='24']/xs:annotation/xs:documentation[text()='Documentazione InfoCamere']",
        namespaces={"xs": "http://www.w3.org/2001/XMLSchema"},
    )


def test_pacchetto_ministeriale_conservato_senza_modifiche():
    import hashlib

    folder = ROOT / "docs/specs/ministero/xsd/2026-10-19-sici"
    manifest = json.loads((folder / "source-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 156
    assert manifest["archiveSha256"] == "83e5ca05691e9d1e0422de84695ed8fdab4aa1e080e2fcca9ddac9e9ba11a264"
    for row in manifest["files"]:
        assert hashlib.sha256((folder / "XSD_SICI_20260720" / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_un_solo_canale_sici_attivo_e_alias_di_lettura_compatibile():
    from pct.pst_catalog import get_xsd_channels

    channels = get_xsd_channels()
    assert sum(row.package_name == "XSD_SICI_20260720.zip" for row in channels) == 1
    assert get_xsd_channel("SICI_20260722_PREVIEW") == get_xsd_channel("SICI")
