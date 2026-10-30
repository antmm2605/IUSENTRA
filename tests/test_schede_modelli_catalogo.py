from web.services.schede_fonti_catalogo import catalog_from_records, catalogo_modelli
from lex.normativa.biblioteca.fabbisogno import CARTELLA_SCHEDE


def record(identity, code, **fields):
    return {"global_template_id": "tpl_" + identity * 20, "codice": code, "titolo": "Modello", "source": "master", **fields}


def test_all_native_inventory_identities_are_visible_without_collapsing_sources():
    from pct.template_atti_unified_catalog import build_unified_template_catalog
    native = build_unified_template_catalog()
    output = catalogo_modelli(CARTELLA_SCHEDE)
    assert len(output) == len(native)
    assert {row["id"] for row in output} == {row["global_template_id"] for row in native}
    assert len({row["id"] for row in output}) == len(output)
    assert len(output) >= 1320
    assert any(row["stato_norme"] == "associate" for row in output)
    assert any(row["stato_norme"] == "da_associare" for row in output)


def test_explicit_bindings_cover_template_variants_and_compilers_but_not_generic_fallback():
    schede = {"CIV_001": {"template": ["CIV_002"], "modelli_compilatore": ["CIV_COMP_001"],
        "base_normativa": [{"atto": "codice_procedura_civile", "articolo": "163"}]}}
    rows = [record("a", "CIV_002"), record("b", "CIV_COMP_001"),
            record("c", "ALTRO", link_compilatore_code="CIV_COMP_001", original_id="CIV_001")]
    output = {row["id"]: row for row in catalog_from_records(rows, schede)}
    assert output[rows[0]["global_template_id"]]["schede_normative"] == ["CIV_001"]
    assert output[rows[1]["global_template_id"]]["numero_riferimenti"] == 1
    assert output[rows[2]["global_template_id"]]["stato_norme"] == "da_associare"


def test_equal_codes_keep_distinct_source_identities_and_do_not_export_other_fields():
    rows = [record("a", "CIV_001", source="master", customer_name="private"),
            record("b", "CIV_001", source="builtin_workspace")]
    output = catalog_from_records(rows, {"CIV_001": {}})
    assert len(output) == 2 and output[0]["id"] != output[1]["id"]
    assert {row["provenienza"] for row in output} == {"Catalogo professionale", "Archivio dei modelli"}
    assert "customer_name" not in str(output) and "private" not in str(output)


def test_missing_or_duplicate_native_identity_fails_instead_of_hiding_records():
    import pytest
    for rows in [[{"codice": "CIV_001"}], [record("a", "A"), record("a", "B")]]:
        with pytest.raises(ValueError):
            catalog_from_records(rows, {})


def test_normative_approval_is_specific_to_each_native_template(tmp_path):
    from tests.test_api_schede_fonti import _biblioteca
    from pct.storage import StudioDB
    from web.services import schede_fonti_runtime as runtime
    database = _biblioteca(tmp_path)
    studio = StudioDB(tmp_path / "private.sqlite")
    models = [row for row in runtime._modelli() if row["codice"] == "CIV_ORD_023"]
    assert len(models) >= 2
    first, second = models[:2]
    a = runtime.scheda(database, first["id"], studio_db=studio)
    assert a["norme"] and a["schede_collegate"] == ["CIV_ORD_023"]
    runtime.approva(database, first["id"], "Avvocato prova", a["impronta"], studio_db=studio)
    assert any(row["approvata"] for row in runtime.scheda(database, first["id"], studio_db=studio)["norme"])
    assert not any(row["approvata"] for row in runtime.scheda(database, second["id"], studio_db=studio)["norme"])
    missing = next(row for row in runtime._modelli() if row["stato_norme"] == "da_associare")
    detail = runtime.scheda(database, missing["id"], studio_db=studio)
    assert detail["stato_collegamento"] == "da_associare" and detail["norme"] == []
