from __future__ import annotations

from pct.procedure_source_research import (
    build_source_plan_for_xsd,
    consult_sources_for_xsd,
    seed_multi_source_evidence_for_inventory,
)
from tests.procedure_pipeline_support import make_repo, seed_inventory


def test_source_research_costruisce_piano_multi_fonte_per_famiglia(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)
    xsd = repo.get_xsd_object("010001")

    plan = build_source_plan_for_xsd(xsd)

    assert plan.family == "ingiunzione"
    assert plan.xsd_label == "Ingiunzione test"
    assert plan.review_required is True
    assert {"technical", "official"} <= {ref.source_type for ref in plan.references}
    assert any(ref.source_id == "cpc_art_633" for ref in plan.references)
    assert any(ref.source_id == "cpc_art_125" for ref in plan.references)


def test_source_research_adatta_fonti_alla_pratica_selezionata(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)

    sfratto = build_source_plan_for_xsd(repo.get_xsd_object("030001"))
    cautelare = build_source_plan_for_xsd(repo.get_xsd_object("011001"))
    possessoria = build_source_plan_for_xsd(repo.get_xsd_object("020001"))
    generica = build_source_plan_for_xsd(repo.get_xsd_object("100"))

    assert sfratto.family == "sfratto"
    assert any(ref.source_id == "cpc_art_657" for ref in sfratto.references)
    assert cautelare.family == "cautelare"
    assert any(ref.source_id == "cpc_art_669_bis" for ref in cautelare.references)
    assert possessoria.family == "possessoria"
    assert any(ref.source_id == "cpc_art_703" for ref in possessoria.references)
    assert generica.family == "contenzioso_civile_generale"
    assert any(ref.source_id == "cpc_art_99" for ref in generica.references)


def test_source_research_ogni_pratica_importata_ha_presidio_normattiva_cpc(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)

    for xsd in repo.list_xsd_objects(active_only=True):
        plan = build_source_plan_for_xsd(xsd)
        cpc_refs = [
            ref
            for ref in plan.references
            if "normattiva.it" in ref.source_url and "Codice di procedura civile" in ref.source_title
        ]
        assert cpc_refs, f"manca presidio CPC per {xsd['xsd_code']}"
        assert plan.xsd_code == xsd["xsd_code"]
        assert plan.xsd_label == xsd["xsd_label"]


def test_source_research_registra_evidenze_e_card_in_review(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)

    dry = consult_sources_for_xsd(repo, "030001", dry_run=True)
    assert dry["source_evidence_created"] == 0
    assert dry["plan"]["family"] == "sfratto"

    applied = consult_sources_for_xsd(repo, "030001", dry_run=False)
    assert applied["source_evidence_created"] >= 5
    card = repo.get_knowledge_card(int(applied["card_id"]))
    assert card["status"] == "needs_review"
    assert card["card_json"]["nota_originalita"].startswith("Dalle fonti confrontate")

    report = seed_multi_source_evidence_for_inventory(repo, dry_run=True, limit=2)
    assert report.xsd_total == 2
    assert report.review_required == 2
