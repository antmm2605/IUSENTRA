from __future__ import annotations

from pct.procedure_coverage_ext import compute_extended_coverage, enqueue_extended_gaps, list_procedure_inventory_coverage
from tests.procedure_pipeline_support import make_repo, seed_inventory


def test_coverage_genera_gap_per_blocchi_mancanti(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)

    coverage = compute_extended_coverage(repo, "PROC_PCT_INGIUNZIONE_ANTE_CAUSAM_NEEDS_REVIEW", "010001")
    assert coverage["status"] == "PARTIAL"
    assert "source_evidence" in coverage["missing_blocks"]
    assert "knowledge_card" in coverage["missing_blocks"]
    assert "human_review" in coverage["missing_blocks"]

    gaps = enqueue_extended_gaps(repo, coverage)
    gap_types = {gap["gap_type"] for gap in gaps}
    assert {"MISSING_SOURCE_EVIDENCE", "MISSING_KNOWLEDGE_CARD", "NEEDS_HUMAN_REVIEW"} <= gap_types


def test_coverage_ready_solo_con_mapping_fonti_card_e_review(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)
    procedure_code = "PROC_PCT_INGIUNZIONE_ANTE_CAUSAM_NEEDS_REVIEW"
    mapping = repo.list_xsd_mappings("010001")[0]
    mapping["review_status"] = "validated"
    repo.upsert_xsd_mapping(mapping)
    repo.add_source_evidence(
        {
            "procedure_code": procedure_code,
            "xsd_code": "010001",
            "source_type": "official",
            "source_url": "https://pst.giustizia.it/PST/it/download.page",
            "source_title": "PST",
            "last_checked_at": "2026-05-20",
            "evidence_kind": "catalogo_xsd",
            "copyright_policy": "official_public",
            "review_status": "validated",
        }
    )
    repo.create_knowledge_card(
        {
            "procedure_code": procedure_code,
            "xsd_code": "010001",
            "title": "Scheda ingiunzione",
            "status": "approved",
            "validation_report_json": {"blocking_errors": []},
            "card_json": {"data_verifica": "2026-05-20"},
        }
    )

    coverage = compute_extended_coverage(repo, procedure_code, "010001")
    assert coverage["ready"] is True
    assert coverage["status"] == "READY"
    assert coverage["auto_publish_eligible"] is False

    inventory = list_procedure_inventory_coverage(repo)
    assert any(row["xsd_code"] == "010001" for row in inventory)
