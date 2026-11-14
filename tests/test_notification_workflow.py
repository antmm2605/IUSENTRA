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

def test_notification_workflow_remaining_error_and_branch_paths(tmp_path, monkeypatch):
    import pct.notification_workflow as workflow_module

    repo = make_repo(tmp_path)
    notification_id = create_notification_event(
        repo,
        fascicolo_id="F-BRANCH",
        notification_type="PEC",
        act_document_id="atto",
        recipient_name="Mario Rossi",
        recipient_address="mario@example.test",
        recipient_address_source="ReGIndE",
    )

    with pytest.raises(ValueError, match="Notifica non trovata"):
        acquire_notification_proof_bundle(repo, 999_999, "missing")
    with pytest.raises(ValueError, match="solo dopo invio o consegna"):
        acquire_notification_proof_bundle(repo, notification_id, "missing")

    mark_notification_ready(repo, notification_id)
    record_notification_sent(repo, notification_id)
    record_notification_delivery(repo, notification_id)
    proof = build_complete_notification_proof_bundle(
        repo,
        notification_id=notification_id,
        bundle_id="proof-branch",
    )
    acquire_notification_proof_bundle(repo, notification_id, str(proof["bundle_id"]))

    mark_proof_deposit_required(repo, notification_id)
    assert repo.get_notification_event(notification_id)["status"] == "PROOF_ACQUIRED"
    with pytest.raises(ValueError, match="Evidenza deposito prova mancante"):
        mark_proof_deposited(repo, notification_id, 999_999)

    other_evidence_id = add_evidence_document(
        repo,
        fascicolo_id="F-OTHER",
        evidence_type="DEPOSIT_RECEIPT",
        document_id="deposit-other",
        hash="b" * 64,
    )
    with pytest.raises(ValueError, match="altro fascicolo"):
        mark_proof_deposited(repo, notification_id, other_evidence_id)

    evidence_id = add_evidence_document(
        repo,
        fascicolo_id="F-BRANCH",
        evidence_type="DEPOSIT_RECEIPT",
        document_id="deposit-branch",
        hash="c" * 64,
    )
    actual_event = repo.get_notification_event(notification_id)
    assert actual_event is not None
    with monkeypatch.context() as event_patch:
        event_patch.setattr(
            type(repo),
            "get_notification_event",
            lambda _repo, _notification_id, conn=None: {
                **actual_event,
                "status": "PROOF_ACQUIRED",
                "proof_bundle_id": None,
            },
        )
        with pytest.raises(ValueError, match="bundle probatorio"):
            mark_proof_deposited(repo, notification_id, evidence_id)

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        workflow_module,
        "fetch_notification_case_for_event",
        lambda _conn, _notification_id: None,
    )
    monkeypatch.setattr(
        type(repo),
        "update_notification_event",
        lambda _repo, event_id, updates, **kwargs: captured.update(
            {
                "event_id": event_id,
                "updates": updates,
                "source": kwargs.get("source"),
            }
        ),
    )
    mark_proof_deposited(repo, notification_id, evidence_id)
    assert captured["event_id"] == notification_id
    assert captured["updates"] == {
        "status": "PROOF_DEPOSITED",
        "proof_bundle_id": str(proof["bundle_id"]),
    }
    assert captured["source"] == "notification_proof_validation"


def test_motore_usa_consegna_comune_solo_se_tutti_i_destinatari_sono_provati(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from pct.notification_proof_matrix import add_notification_receipt, link_notification_evidence
    from web import helpers
    from web.services import notification_presidia_runtime
    from web.services.ragionamento_raccolta import _consegne_verificate

    repo = make_repo(tmp_path)
    notification_id = repo.create_notification_event({
        "tenant_id": "studio",
        "fascicolo_id": "F1",
        "notification_type": "PEC",
        "act_document_id": "atto1",
        "recipient_address": "primo@example.test",
        "status": "DELIVERED",
    })
    proof = build_complete_notification_proof_bundle(repo, notification_id=notification_id, bundle_id="prova")
    with repo.connect() as conn:
        monkeypatch.setattr(helpers, "_studio_db", lambda _: SimpleNamespace(
            conn=conn, fetchall_readonly=lambda sql, params: conn.execute(sql, params).fetchall(),
        ))
        monkeypatch.setattr(notification_presidia_runtime, "_tenant_id", lambda: "studio")
        atteso = {"atto1": {"data": "2026-06-02", "riferimento": "prova"}}
        assert _consegne_verificate("F1") == atteso
        secondo = conn.execute(
            """INSERT INTO notification_recipients
               (tenant_id, notification_case_id, fascicolo_id, recipient_address, status)
               SELECT tenant_id, notification_case_id, fascicolo_id, ?, 'DELIVERY_RECEIVED'
               FROM notification_recipients WHERE id=?""",
            ("secondo@example.test", proof["recipient_id"]),
        ).lastrowid
        conn.commit()
        assert _consegne_verificate("F1") == {}

        for tipo, ruolo in (("ACCETTAZIONE", "RICEVUTA_ACCETTAZIONE"),
                            ("AVVENUTA_CONSEGNA", "RICEVUTA_AVVENUTA_CONSEGNA")):
            ricevuta_id = add_notification_receipt(repo, {
                "notification_event_id": notification_id,
                "recipient_id": secondo,
                "receipt_type": tipo,
                "event_time": "2026-06-01T22:00:30+00:00",
                "raw_eml_document_id": f"secondo-{tipo}.eml",
                "verification_status": "VERIFIED",
                "correlation_status": "CORRELATED",
            })
            evidence_id = add_evidence_document(
                repo, fascicolo_id="F1", evidence_type=ruolo,
                document_id=f"secondo-{tipo}.eml", hash="a" * 64,
            )
            link_notification_evidence(
                repo, bundle_id="prova", evidence_id=evidence_id,
                evidence_role=ruolo, recipient_id=secondo,
            )
        assert _consegne_verificate("F1") == atteso

        for event_time in ("2026-06-03T00:00:30+02:00", "2026-06-02T10:00:30", ""):
            conn.execute("UPDATE notification_receipts SET event_time=? WHERE id=?", (event_time, ricevuta_id))
            assert _consegne_verificate("F1") == {}
