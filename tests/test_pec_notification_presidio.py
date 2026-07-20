from __future__ import annotations

from pathlib import Path

from pct.pec_notification_presidio import (
    NotificationPresidioRepository,
    NotificationPresidioService,
    NotificationReceiptEnvelope,
    PecNotificationReconciler,
    PresidioStatus,
    Priority,
    ReceiptKind,
)


def _repo(tmp_path: Path) -> NotificationPresidioRepository:
    return NotificationPresidioRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="tenant-notifiche-test",
    )


def _candidate(
    service: NotificationPresidioService,
    *,
    recipients: list[dict[str, str]],
) -> str:
    result = service.create_candidate(
        {
            "fascicolo_id": "FASC-001",
            "source_message_id": "ordine-notifica-001",
            "source_effective_at": "2026-07-20T10:00:00+02:00",
            "trigger_type": "EXPLICIT_NOTIFICATION_ORDER",
            "notification_case": "notifica_l53",
            "rulepack_version": "legal-notification-rulepack-v1",
            "priority": "P1",
            "confidence": 0.99,
            "detection_reason": "Ordine espresso di notifica rilevato.",
            "documents": [
                {
                    "content_sha256": "a" * 64,
                    "original_filename": "Ricorso.pdf",
                    "document_version": "1",
                    "document_role": "notified_act",
                }
            ],
            "recipients": recipients,
        }
    )
    assert result["created"] is True
    return str(result["id"])


def _sent(
    reconciler: PecNotificationReconciler,
    *,
    presidio_id: str,
    message_id: str,
    recipient: dict[str, str],
) -> None:
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.SENT,
            message_id=message_id,
            presidio_id=presidio_id,
            recipient_address=recipient["pec_address"],
            recipient_name=recipient["name"],
            recipient_fiscal_id=recipient["fiscal_id"],
            occurred_at="2026-07-20T10:30:00+02:00",
        )
    )


def _recipient_rows(repo: NotificationPresidioRepository, presidio_id: str) -> list[dict[str, str]]:
    with repo.connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM pec_legal_notification_recipients
            WHERE tenant_id=? AND presidio_id=?
            ORDER BY pec_address
            """,
            (repo.tenant_id, presidio_id),
        ).fetchall()
    return [dict(row) for row in rows]


def test_presidio_mixed_rdac_and_failure_stays_partial_with_p0(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    service = NotificationPresidioService(repo)
    reconciler = PecNotificationReconciler(repo)
    first = {
        "name": "Mario Rossi",
        "fiscal_id": "RSSMRA80A01H501U",
        "pec_address": "mario.rossi@pec.test",
        "role": "controparte",
    }
    second = {
        "name": "Anna Bianchi",
        "fiscal_id": "BNCNNA80A41H501Y",
        "pec_address": "anna.bianchi@pec.test",
        "role": "controparte",
    }
    presidio_id = _candidate(service, recipients=[first, second])

    _sent(reconciler, presidio_id=presidio_id, message_id="sent-mario", recipient=first)
    _sent(reconciler, presidio_id=presidio_id, message_id="sent-anna", recipient=second)
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.RDAC,
            message_id="rdac-mario",
            original_message_id="sent-mario",
            recipient_address=first["pec_address"],
            occurred_at="2026-07-20T10:40:00+02:00",
        )
    )
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.FAILURE,
            message_id="failure-anna",
            original_message_id="sent-anna",
            recipient_address=second["pec_address"],
            failure_reason="casella destinatario piena",
            failure_attribution="attributable_to_recipient",
            occurred_at="2026-07-20T10:45:00+02:00",
        )
    )

    presidio = repo.get_presidio(presidio_id)
    assert presidio["status"] == PresidioStatus.PARTIAL_DELIVERY.value
    assert presidio["priority"] == Priority.P0.value
    assert not bool(presidio["human_review_required"])
    rows = _recipient_rows(repo, presidio_id)
    assert [row["delivery_status"] for row in rows] == ["failed", "delivered"]
    assert rows[0]["failure_attribution"] == "attributable_to_recipient"


def test_uncertain_failure_requires_review_and_late_rdac_does_not_close(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    service = NotificationPresidioService(repo)
    reconciler = PecNotificationReconciler(repo)
    recipient = {
        "name": "Mario Rossi",
        "fiscal_id": "RSSMRA80A01H501U",
        "pec_address": "mario.rossi@pec.test",
        "role": "controparte",
    }
    presidio_id = _candidate(service, recipients=[recipient])

    _sent(reconciler, presidio_id=presidio_id, message_id="sent-mario", recipient=recipient)
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.FAILURE,
            message_id="failure-mario",
            original_message_id="sent-mario",
            recipient_address=recipient["pec_address"],
            failure_reason="errore consegna non attribuibile con certezza",
            failure_attribution="uncertain",
            occurred_at="2026-07-20T10:45:00+02:00",
        )
    )
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.RDAC,
            message_id="rdac-tardiva",
            original_message_id="sent-mario",
            recipient_address=recipient["pec_address"],
            occurred_at="2026-07-20T10:55:00+02:00",
        )
    )

    presidio = repo.get_presidio(presidio_id)
    assert presidio["status"] == PresidioStatus.DELIVERY_FAILED.value
    assert presidio["priority"] == Priority.P0.value
    assert bool(presidio["human_review_required"])
    [row] = _recipient_rows(repo, presidio_id)
    assert row["delivery_status"] == "failed"
    assert row["failure_attribution"] == "uncertain"
