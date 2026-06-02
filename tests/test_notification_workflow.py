from __future__ import annotations

import pytest

from pct.evidence_vault import add_evidence_document
from pct.notification_workflow import (
    NOTIFICATION_STATUSES,
    NotificationStatus,
    acquire_notification_proof,
    acquire_notification_proof_bundle,
    attach_relata,
    create_notification_event,
    mark_notification_ready,
    mark_proof_deposit_required,
    mark_proof_deposited,
    proof_deposit_required,
    record_notification_delivery,
    record_notification_sent,
)
from tests.procedure_pipeline_support import build_complete_notification_proof_bundle, make_repo


def test_notification_ready_sent_proof_e_deposito_prova(tmp_path):
    repo = make_repo(tmp_path)
    assert NotificationStatus.PROOF_DEPOSITED.value in NOTIFICATION_STATUSES
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
        hash="a" * 64,
    )
    with pytest.raises(ValueError, match="Catena probatoria"):
        acquire_notification_proof(repo, notification_id, evidence_id)
    proof = build_complete_notification_proof_bundle(repo, notification_id=notification_id, bundle_id="proof-F1")
    acquire_notification_proof_bundle(repo, notification_id, str(proof["bundle_id"]))
    assert repo.get_notification_event(notification_id)["status"] == "PROOF_ACQUIRED"
    assert proof_deposit_required(repo, notification_id) is True

    mark_proof_deposit_required(repo, notification_id)
    deposit_evidence_id = add_evidence_document(
        repo,
        fascicolo_id="F1",
        evidence_type="DEPOSIT_RECEIPT",
        document_id="deposito-prova",
        hash="d" * 64,
    )
    with pytest.raises(ValueError, match="Catena probatoria"):
        mark_proof_deposited(repo, notification_id, deposit_evidence_id)
    build_complete_notification_proof_bundle(
        repo,
        notification_id=notification_id,
        bundle_id="deposit-proof-F1",
        bundle_type="DEPOSITO_PROVA_NOTIFICA",
    )
    mark_proof_deposited(repo, notification_id, deposit_evidence_id)
    assert repo.get_notification_event(notification_id)["status"] == "PROOF_DEPOSITED"
    assert repo.list_audit_log("notification_events")


def test_notification_proof_bundle_blocca_destinatario_senza_ricevute(tmp_path):
    repo = make_repo(tmp_path)
    notification_id = create_notification_event(
        repo,
        fascicolo_id="F2",
        notification_type="PEC",
        act_document_id="atto2",
        recipient_name="Mario Rossi",
        recipient_address="mario@example.test",
        recipient_address_source="ReGIndE",
    )
    mark_notification_ready(repo, notification_id)
    record_notification_sent(repo, notification_id)
    record_notification_delivery(repo, notification_id)
    proof = build_complete_notification_proof_bundle(repo, notification_id=notification_id, bundle_id="proof-F2")
    acquire_notification_proof_bundle(repo, notification_id, str(proof["bundle_id"]))

    with repo.connect() as conn:
        case = repo._fetch_one(conn, "SELECT * FROM notification_cases WHERE notification_event_id = ?", (notification_id,))
        assert case is not None
        conn.execute(
            """
            INSERT INTO notification_recipients (
                notification_case_id, notification_event_id, fascicolo_id,
                recipient_name, recipient_address, recipient_address_source, status
            ) VALUES (?, ?, ?, 'Luigi Bianchi', 'luigi@example.test', 'INI-PEC', 'DELIVERY_RECEIVED')
            """,
            (int(case["id"]), notification_id, "F2"),
        )
        conn.commit()

    with pytest.raises(ValueError, match="manca la ricevuta di accettazione"):
        repo.update_notification_event(
            notification_id,
            {"proof_bundle_id": str(proof["bundle_id"])},
            source="notification_proof_validation",
        )
