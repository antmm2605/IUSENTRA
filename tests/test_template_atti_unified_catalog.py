from pct.template_atti_unified_catalog import (
    build_unified_template_catalog,
    get_template_source_breakdown,
    get_unified_template_item,
)


def test_unified_catalog_governa_tutti_i_template_con_capability_minime():
    catalog = build_unified_template_catalog(refresh=True)
    stats = get_template_source_breakdown(refresh=True)

    assert catalog
    assert stats["expected_total"] == 1320
    assert stats["detected_total"] == len(catalog)
    assert all("supports_timbro" in item for item in catalog)
    assert all("supports_prefill" in item for item in catalog)
    assert all("supports_cartabia_checks" in item for item in catalog)
    assert all("supports_deposit_checks" in item for item in catalog)
    assert all("supports_render" in item for item in catalog)
    assert all("missing_capabilities" in item for item in catalog)


def test_unified_catalog_non_promuove_ready_senza_fonti_o_capability():
    catalog = build_unified_template_catalog(refresh=True)

    for item in catalog:
        if item.get("stato_conformita") == "cartabia_ready":
            assert item.get("source_evidence_ids")
            assert not item.get("missing_capabilities")
            assert not item.get("blocking_issues")

    sample = get_unified_template_item("CIV_ORD_001")
    assert sample is not None
    assert sample["supports_timbro"] is True
    assert sample["supports_prefill"] is True
    assert sample["supports_cartabia_checks"] is True
