import json
from pathlib import Path


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "pct" / "data" / "legal_sources_registry.json"


def _registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_legal_sources_registry_contiene_fonti_ufficiali_minime():
    registry = _registry()
    source_ids = {source["id"] for source in registry["sources"]}

    required = {
        "normattiva",
        "gazzetta_ufficiale",
        "ministero_giustizia",
        "pst",
        "specifiche_pct_art_34",
        "giustizia_amministrativa_siga",
        "giustizia_tributaria_sigit",
        "dm_55_2014",
        "dm_147_2022",
        "l_247_2012_art_13",
        "dm_44_2011",
        "gdpr_reg_2016_679",
    }

    assert required <= source_ids


def test_legal_sources_registry_non_promette_conformita_senza_review():
    registry = _registry()
    allowed_statuses = set(registry["policy"]["allowed_statuses"])

    for source in registry["sources"]:
        assert source["status"] in allowed_statuses
        assert source["official_url"].startswith("https://")
        assert source["last_verified_at"]
        if source["id"] in {"specifiche_pct_art_34", "giustizia_amministrativa_siga", "giustizia_tributaria_sigit", "sigp_giudice_pace", "gdpr_reg_2016_679"}:
            assert source["status"] == "manual_review_required"


def test_fonti_tariffario_tracciano_dm55_e_dm147():
    registry = _registry()
    tariffario_sources = {
        source["id"]: source
        for source in registry["sources"]
        if "Tariffario" in source.get("modules", [])
    }

    assert tariffario_sources["dm_55_2014"]["status"] == "active"
    assert tariffario_sources["dm_147_2022"]["status"] == "active"
    assert "Normattiva" in tariffario_sources["dm_55_2014"]["version"]
    assert "Normattiva" in tariffario_sources["dm_147_2022"]["version"]
