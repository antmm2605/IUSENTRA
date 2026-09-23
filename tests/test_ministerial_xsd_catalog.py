from pathlib import Path

from pct.busta import DATIATTO_ROOT_NS_BY_GENERATOR_CLASS
from pct.cassazione_atti_v21 import CASSAZIONE_ATTI_V21_KEYS
from pct.datiatto_unep import ROOT_NS as UNEP_ROOT_NS
from pct.datiatto_xsd import _global_element_index
from pct.deposito_telematico_catalogo import (
    CASSAZIONE_ROOT_ELIMINATA_STATUS,
    build_deposit_catalog_payload,
    list_deposit_catalog_entries,
    resolve_deposit_type_payload,
)
from pct.ministerial_xsd_catalog import (
    ACTIVE_MINISTERIAL_SCHEMAS,
    active_ministerial_root_index,
    active_schema_paths,
    active_xsd_association,
)


def test_inventario_contiene_solo_entry_point_in_esercizio():
    paths = active_schema_paths()

    assert len(paths) == len(ACTIVE_MINISTERIAL_SCHEMAS) == 20
    assert all(path.is_file() for path in paths)
    assert all("preview" not in path.as_posix().casefold() for path in paths)
    assert any("2026-05-12-sici" in path.as_posix() for path in paths)
    assert any("parte_v21/Parte-cassazione.xsd" in path.as_posix() for path in paths)
    assert not any("parte_v13" in path.as_posix() for path in paths)


def test_ogni_voce_operativa_punta_a_radice_namespace_e_file_attivi():
    for entry in list_deposit_catalog_entries():
        schema = entry["schema"]
        association = schema["activeXsd"]
        if schema["status"] == CASSAZIONE_ROOT_ELIMINATA_STATUS:
            assert association["active"] is False
            assert entry["rules"]["real_send_allowed_from_pct_panel"] is False
            continue
        assert association["active"] is True, entry["key"]
        assert Path(association["schemaPath"]).is_file(), entry["key"]
        expected_namespace = (
            UNEP_ROOT_NS
            if schema["generatorClass"] == "UNEP"
            else DATIATTO_ROOT_NS_BY_GENERATOR_CLASS[schema["generatorClass"]]
        )
        assert association["namespace"] == expected_namespace, entry["key"]


def test_versioni_storiche_non_sono_indicizzate_dal_validatore_runtime():
    active_paths = {str(path.resolve()) for path in active_schema_paths()}
    indexed_paths = {
        str(path.resolve())
        for paths in _global_element_index().values()
        for path in paths
    }

    assert indexed_paths <= active_paths
    assert not any("sicid_v6" in path or "parte_v13" in path for path in indexed_paths)


def test_ruoli_specialistici_e_deposito_complementare_sono_fail_closed():
    avvocato = build_deposit_catalog_payload(professional_role="AVV.")["entries"]
    curatore = build_deposit_catalog_payload(professional_role="CUR")["entries"]
    custode = build_deposit_catalog_payload(professional_role="CUS")["entries"]
    delegato = build_deposit_catalog_payload(professional_role="DEL")["entries"]
    ctu = build_deposit_catalog_payload(professional_role="CTU")["entries"]

    assert all(entry["schema"]["generatorClass"] not in {
        "CurSiecicConcorsuali", "CusSiecicEsecuzioni", "DelSiecicEsecuzioni",
        "Professionista", "Professionista_SIGP", "ProfSiecicConcorsuali", "ProfSiecicEsecuzioni",
    } for entry in avvocato)
    assert {entry["schema"]["generatorClass"] for entry in curatore} == {"CurSiecicConcorsuali"}
    assert {entry["schema"]["generatorClass"] for entry in custode} == {"CusSiecicEsecuzioni"}
    assert {entry["schema"]["generatorClass"] for entry in delegato} == {"DelSiecicEsecuzioni"}
    assert {entry["schema"]["generatorClass"] for entry in ctu} == {
        "Professionista", "Professionista_SIGP", "ProfSiecicConcorsuali", "ProfSiecicEsecuzioni",
    }

    for generator in ("AttoSistemaSicid", "AttoSistemaSiecic", "AttoSistema_SIGP"):
        association = active_xsd_association(generator, "DepositoComplementare")
        assert association["active"] is True
        assert association["systemOnly"] is True
        assert association["selectableByProfessional"] is False


def test_otto_nuovi_atti_cassazione_sono_attivi_solo_su_v21():
    index = active_ministerial_root_index()
    for key in CASSAZIONE_ATTI_V21_KEYS:
        root = key.split("::", 1)[1]
        assert index[("ParteCassazione", root)]["packageName"] == "XSD_Cassazione_20260227.zip"
        entry = resolve_deposit_type_payload(key, professional_role="AVV.")
        assert entry is not None
        assert entry["schema"]["activeXsd"]["schemaPath"].endswith("parte_v21/Parte-cassazione.xsd")
