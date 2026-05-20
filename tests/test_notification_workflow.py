from __future__ import annotations

import pytest

from pct.evidence_vault import add_evidence_document
from pct.notification_workflow import (
    acquire_notification_proof,
    attach_relata,
    create_notification_event,
    mark_notification_ready,
    mark_proof_deposit_required,
    mark_proof_deposited,
    proof_deposit_required,
    record_notification_delivery,
    record_notification_sent,
)
from tests.procedure_pipeline_support import make_repo


def test_notification_ready_sent_proof_e_deposito_prova(tmp_path):
    repo = make_repo(tmp_path)
    obligation_id = repo.add_obligation(
        {
            "fascicolo_id": "F1",
            "procedure_code": "PROC",
            "xsd_code": "010001",
            "trigger_event": "DECRETO",
            "obligation_type": "DEPOSITO_PROVA_NOTIFICA",
            "evidence_required_json": ["DEPOSIT_RECEIPT"],
        }
    )
    notification_id = create_notification_event(
        repo,
        fascicolo_id="F1",
        obligation_id=obligation_id,
        notification_type="PEC",
        act_document_id="atto1",
        recipient_name="Mario Rossi",
        recipient_address="mario@example.test",
    )

    with pytest.raises(ValueError):
        mark_notification_ready(repo, notification_id)
    mark_notification_ready(repo, notification_id, reviewed=True)
    attach_relata(repo, notification_id, "relata1")
    assert record_notification_sent(repo, notification_id)["sent"] is True
    record_notification_delivery(repo, notification_id)

    with pytest.raises(ValueError):
        acquire_notification_proof(repo, notification_id, 999)
    evidence_id = add_evidence_document(
        repo,
        fascicolo_id="F1",
        evidence_type="NOTIFICATION_RECEIPT",
        document_id="ricevuta1",
        hash="abc",
    )
    acquire_notification_proof(repo, notification_id, evidence_id)
    assert repo.get_notification_event(notification_id)["status"] == "PROOF_ACQUIRED"
    assert proof_deposit_required(repo, notification_id) is True

    mark_proof_deposit_required(repo, notification_id)
    deposit_evidence_id = add_evidence_document(
        repo,
        fascicolo_id="F1",
        evidence_type="DEPOSIT_RECEIPT",
        document_id="deposito-prova",
        hash="def",
    )
    mark_proof_deposited(repo, notification_id, deposit_evidence_id)
    assert repo.get_notification_event(notification_id)["status"] == "PROOF_DEPOSITED"
    assert repo.list_audit_log("notification_events")
