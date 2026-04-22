from __future__ import annotations

from lex.research.official_sources import OfficialSourcesCatalog
from lex.research.source_policy import Tier, evaluate_source, get_tier_for_domain
from lex.research.source_registry import get_source_registry


def test_source_registry_carica_fonti_partner_e_riservate_del_kit():
    registry = get_source_registry()

    registro_imprese = registry.get("registro_imprese_api")
    pst = registry.get("pst_reginde_pda")
    ini_pec = registry.get("ini_pec")

    assert registro_imprese is not None
    assert registro_imprese.is_partner_source is True
    assert registro_imprese.requires_credentials is True
    assert pst is not None
    assert pst.is_restricted_source is True
    assert ini_pec is not None
    assert ini_pec.supports_public_web_search is False


def test_official_sources_catalog_arricchisce_url_istituzionale_con_metadati_accesso():
    catalog = OfficialSourcesCatalog()

    enriched = catalog.enrich(
        {
            "title": "Consultazione INI-PEC",
            "url": "https://www.inipec.gov.it/cerca-pec",
        }
    )

    assert enriched["source_registry_key"] == "ini_pec"
    assert enriched["source_access_status"] == "portal_or_institutional_channel"
    assert enriched["source_access_label"] == "Portale o canale istituzionale"
    assert enriched["source_requires_credentials"] is True
    assert enriched.get("verified_reference") in {None, False}


def test_source_policy_riconosce_domini_del_catalogo_come_fonti_governate():
    assert get_tier_for_domain("www.inipec.gov.it", "societario") == Tier.TIER_1
    assert get_tier_for_domain("accessoallebanchedati.registroimprese.it", "societario") == Tier.TIER_1

    evaluation = evaluate_source(
        "https://accessoallebanchedati.registroimprese.it/abdo/api",
        "societario",
    )

    assert evaluation.tier == Tier.TIER_1
    assert any("accesso non libero" in warning.lower() for warning in evaluation.warnings)
