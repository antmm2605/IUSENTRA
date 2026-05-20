from __future__ import annotations

from pct.procedure_xsd_mapper import infer_mapping_for_xsd, map_all_xsd_objects
from tests.procedure_pipeline_support import make_repo, seed_inventory


def test_mapper_prefissi_principali_e_unknown_needs_review(tmp_path):
    samples = {
        "010123": "INGIUNZIONE_ANTE_CAUSAM",
        "050123": "INGIUNZIONE_SOCIETARIA",
        "030123": "SFRATTO",
        "011123": "CAUTELARE",
        "012123": "CAUTELARE",
        "015123": "CAUTELARE",
        "017123": "CAUTELARE",
        "019123": "CAUTELARE",
        "051123": "CAUTELARE",
        "052123": "CAUTELARE",
        "053123": "CAUTELARE",
        "055123": "CAUTELARE",
        "059123": "CAUTELARE",
        "020123": "POSSESSORIA",
    }
    for code, expected in samples.items():
        candidate = infer_mapping_for_xsd({"xsd_code": code, "xsd_label": "test"})
        haystack = f"{candidate.procedure_code} {candidate.notes}".upper().replace("_", " ")
        assert expected.replace("_", " ") in haystack
        assert candidate.review_status == "needs_review"
        assert candidate.confidence_score >= 75

    unknown = infer_mapping_for_xsd({"xsd_code": "999001", "xsd_label": "ignoto"})
    assert unknown.review_status == "needs_review"
    assert unknown.confidence_score < 75


def test_map_all_scrive_mapping_e_audit(tmp_path):
    repo = make_repo(tmp_path)
    seed_inventory(repo, tmp_path)

    report = map_all_xsd_objects(repo, dry_run=False)

    assert report.total_xsd_objects == 6
    assert report.needs_review == 6
    assert report.validated == 0
    assert repo.list_xsd_mappings("010001")
    assert repo.list_audit_log("legal_procedure_xsd_map")
