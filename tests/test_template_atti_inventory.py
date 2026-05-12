from pct.template_atti_inventory import (
    EXPECTED_TEMPLATE_TOTAL,
    build_template_inventory,
    detect_duplicate_templates,
    detect_missing_cartabia_profile,
    detect_missing_prefill_bindings,
    detect_templates_not_reachable_from_ui,
    export_template_inventory_report,
    template_inventory_stats,
)


def test_inventory_scopre_fonti_reali_e_riconcilia_1320_canonici(tmp_path):
    source_records = build_template_inventory(include_source_duplicates=True)
    records = build_template_inventory()
    stats = template_inventory_stats(records, source_records=source_records)

    assert stats["expected_total"] == EXPECTED_TEMPLATE_TOTAL == 1320
    assert stats["detected_total"] == EXPECTED_TEMPLATE_TOTAL
    assert stats["matches_expected"] is True
    assert stats["delta"] == 0
    assert stats["source_records_total"] > stats["detected_total"]
    assert stats["cartabia_ready"] == EXPECTED_TEMPLATE_TOTAL
    assert stats["cartabia_review_required"] == 0
    assert "master" in stats["breakdown_by_source"]
    assert "compiler" in stats["breakdown_by_source"]
    assert "builtin_workspace" in stats["breakdown_by_source"]
    assert stats["breakdown_by_source"]["master"] == 420
    assert stats["breakdown_by_source"]["compiler"] == 192
    assert stats["breakdown_by_source"]["builtin_workspace"] == 708

    report = export_template_inventory_report(
        records,
        source_records=source_records,
        output_md=tmp_path / "inventory.md",
        output_json=tmp_path / "inventory.json",
    )
    assert report["stats"]["expected_total"] == 1320
    assert report["stats"]["detected_total"] == 1320
    assert "missing_cartabia_profile" in report
    assert "missing_prefill_bindings" in report


def test_inventory_rileva_duplicate_fonte_e_orfani_senza_correggere_a_mano():
    source_records = build_template_inventory(include_source_duplicates=True)
    records = build_template_inventory()
    stats = template_inventory_stats(records, source_records=source_records)

    assert detect_duplicate_templates(source_records)
    assert stats["duplicates"] >= 1
    assert stats["reconciled_duplicate_templates"] >= 1
    assert stats["duplicate_conflict_templates"] == 0
    assert all(
        record["stato_conformita"] != "cartabia_ready"
        for record in records
        if any("conflitto fonti template" in issue for issue in record.get("blocking_issues", []))
    )
    assert all(
        record["stato_conformita"] == "cartabia_ready"
        for record in records
        if any("copie fonte riconciliate" in warning for warning in record.get("warnings", []))
    )
    assert stats["not_reachable_from_ui"] == len(detect_templates_not_reachable_from_ui(records))
    assert stats["missing_cartabia_profile"] == len(detect_missing_cartabia_profile(records))
    assert stats["missing_prefill_bindings"] == len(detect_missing_prefill_bindings(records))
