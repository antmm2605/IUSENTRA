from __future__ import annotations

from pathlib import Path

from lex.research.source_policy.inference import get_tier_for_domain, infer_area
from lex.research.source_policy.models import Tier
from lex.research.source_registry import get_source_registry
from lex.retrieval.official_web import search_recognized_official_web
from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS
from pct.scheduler_registry import legal_source_scheduler_templates, run_delegated_agent_template


def test_corte_conti_e_fonti_secondarie_sono_censite_con_livello_corretto():
    source_codes = {row["code"]: row for row in DEFAULT_SOURCE_ROWS}

    assert source_codes["corte_conti"]["enabled"] is True
    assert source_codes["corte_conti"]["is_official"] is True
    assert source_codes["giustizia_amministrativa_decisioni_pareri"]["enabled"] is False
    assert source_codes["studiocataldi_codice_civile"]["is_official"] is False
    assert source_codes["avvocatoandreani_codice_procedura_civile"]["enabled"] is False

    assert infer_area("Corte dei Conti responsabilita erariale appalti") == "contabile"
    assert get_tier_for_domain("corteconti.it", "contabile") == Tier.TIER_1
    assert get_tier_for_domain("banchedati.corteconti.it", "contabile") == Tier.TIER_1
    assert get_tier_for_domain("studiocataldi.it", "civile") == Tier.TIER_2
    assert get_tier_for_domain("avvocatoandreani.it", "civile") == Tier.TIER_2
    assert get_tier_for_domain("iussearch.it", "default") == Tier.TIER_2


def test_registro_fonti_lex_espone_url_ufficiali_e_secondarie():
    registry = get_source_registry()

    corte_conti = registry.get("corte_conti")
    assert corte_conti is not None
    assert corte_conti.official is True
    assert "banchedati.corteconti.it" in corte_conti.domains

    cataldi = registry.get("studiocataldi_codice_penale")
    assert cataldi is not None
    assert cataldi.official is False
    assert cataldi.supports_public_web_search is True

    iussearch = registry.get("iussearch")
    assert iussearch is not None
    assert iussearch.official is False
    assert iussearch.supports_public_web_search is True
    assert iussearch.requires_credentials is False


def test_ricerca_governata_accetta_url_dirette_solo_come_fonti_classificate():
    corte_results = search_recognized_official_web(
        "https://www.corteconti.it/Home/Documenti/Sentenze",
        source_ids=["corte_conti"],
        limit_results=3,
    )

    assert len(corte_results) == 1
    assert corte_results[0]["source_id"] == "corte_conti"
    assert corte_results[0]["source_priority"] == "P0"
    assert corte_results[0]["domain"] == "corteconti.it"

    secondary_results = search_recognized_official_web(
        "https://www.studiocataldi.it/codicecivile/",
        source_ids=["studiocataldi_codice_civile"],
        limit_results=3,
    )

    assert len(secondary_results) == 1
    assert secondary_results[0]["source_id"] == "studiocataldi_codice_civile"
    assert secondary_results[0]["source_priority"] == "P2"
    assert secondary_results[0]["source_requires_credentials"] is False

    search_engine_results = search_recognized_official_web(
        "http://www.iussearch.it/",
        source_ids=["iussearch"],
        limit_results=3,
    )

    assert len(search_engine_results) == 1
    assert search_engine_results[0]["source_id"] == "iussearch"
    assert search_engine_results[0]["source_priority"] == "P2"


def test_scheduler_crea_template_per_nuove_fonti_e_blocca_secondarie(tmp_path: Path):
    cfg = {"LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json")}
    templates = {template.key: template for template in legal_source_scheduler_templates(cfg)}

    assert "legal_source_scan__corte_conti" in templates
    assert templates["legal_source_scan__corte_conti"].enabled is True
    assert "legal_source_scan__studiocataldi_codice_civile" in templates
    assert templates["legal_source_scan__studiocataldi_codice_civile"].enabled is False

    class App:
        config = cfg

    result = run_delegated_agent_template(
        "legal_source_scan__studiocataldi_codice_civile",
        App(),
        {"source_code": "studiocataldi_codice_civile"},
    )

    assert result["ok"] is False
    assert "Normattiva e Gazzetta Ufficiale" in result["supervisor_check"]
    assert result["details"][0]["status"] == "in_osservazione"
