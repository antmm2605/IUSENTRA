from __future__ import annotations

import hashlib

import pytest

from pct.evidence_vault import (
    add_evidence_document,
    assert_required_evidence,
    link_evidence_to_deposit,
    link_evidence_to_notification,
    list_evidence_for_fascicolo,
)
from pct.notification_workflow import create_notification_event
from tests.procedure_pipeline_support import make_repo, seed_inventory


def test_evidence_vault_hash_assert_e_link(tmp_path):
    repo = make_repo(tmp_path)
    path = tmp_path / "ricevuta.txt"
    path.write_text("ricevuta", encoding="utf-8")
    expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    evidence_id = add_evidence_document(
        repo,
        fascicolo_id="F1",
        evidence_type="DEPOSIT_RECEIPT",
        document_id="doc1",
        storage_path=str(path),
        filename_original="ricevuta.txt",
    )
    evidence = list_evidence_for_fascicolo(repo, "F1")[0]
    assert evidence["hash"] == expected_hash

    with pytest.raises(ValueError):
        assert_required_evidence(repo, "F1", ["OFFICE_ACCEPTANCE"])
    assert_required_evidence(repo, "F1", ["DEPOSIT_RECEIPT"])

    notification_id = create_notification_event(
        repo,
        fascicolo_id="F1",
        notification_type="PEC",
        act_document_id="atto1",
    )
    link_evidence_to_notification(repo, notification_id=notification_id, evidence_id=evidence_id)
    assert repo.get_notification_event(notification_id)["status"] == "PROOF_ACQUIRED"

    seed_inventory(repo, tmp_path)
    package_id = repo.create_deposit_package(
        {
            "fascicolo_id": "F1",
            "procedure_code": "PROC",
            "xsd_code": "010001",
            "channel_code": "PCT_CIVILE",
        }
    )
    link_evidence_to_deposit(repo, package_id=package_id, evidence_id=evidence_id)
    assert "Evidenza collegata" in repo.get_deposit_package(package_id)["notes"]
