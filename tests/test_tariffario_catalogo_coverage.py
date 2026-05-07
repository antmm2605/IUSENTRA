from pct.tariffario_catalogo import (
    list_all_snapshot_tables,
    load_tariffario_snapshot,
    missing_snapshot_meta,
    profile_reference_rows,
    profiles_for_table,
    tariffario_profile_rows,
    tariffario_rule_rows,
    validate_tariffario_catalog_coverage,
)


def test_catalogo_tariffario_copre_snapshot_profili_e_regole():
    report = validate_tariffario_catalog_coverage()

    assert report["ok"], report
    assert report["tables"] >= 42
    assert report["profiles"] >= 53
    assert report["rules"] >= 150
    assert missing_snapshot_meta() == []


def test_profili_hanno_codici_univoci_tabelle_riferimenti_e_status():
    snapshot = load_tariffario_snapshot()
    profiles = tariffario_profile_rows()
    codes = [row["profile_code"] for row in profiles]

    assert len(codes) == len(set(codes))
    for row in profiles:
        assert row["table_code"] in snapshot
        assert row["table_label"]
        assert row["calc_mode"] in {"per_fasi", "compenso_unico", "per_fasi_adr"}
        assert row["reference_codes"]
        assert row["normative_references"]
        assert row["compliance_status"] in {"snapshot_esatto", "ricostruzione", "fallback_tecnico"}
        if row["exact_snapshot"]:
            assert row["table_code"] in snapshot


def test_regole_espongono_tabella_e_riferimenti_normativi_dal_profilo():
    for row in tariffario_rule_rows():
        assert row["rule_code"]
        assert row["profile_code"]
        assert row["table_code"]
        assert row["table_label"]
        assert row["reference_codes"]
        assert row["compliance_status"] in {"snapshot_esatto", "ricostruzione", "fallback_tecnico"}


def test_helper_catalogo_restituiscono_tabelle_profili_e_reference_rows():
    tables = list_all_snapshot_tables()

    assert {row["table_code"] for row in tables} >= {"A1", "A2", "A3", "A4", "A12", "A13", "A14", "A21", "A22", "A23", "A24", "A25", "A26", "A27"}
    assert profiles_for_table("A25")
    assert profile_reference_rows("stragiudiziale")
