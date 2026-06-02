"""Workflow notifica, relata e prova documentale senza invii reali."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pct.evidence_vault import link_evidence_to_notification
from pct.notification_proof_matrix import fetch_notification_case_for_event
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


class NotificationStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    PROOF_ACQUIRED = "PROOF_ACQUIRED"
    PROOF_DEPOSIT_REQUIRED = "PROOF_DEPOSIT_REQUIRED"
    PROOF_DEPOSITED = "PROOF_DEPOSITED"


NOTIFICATION_STATUSES: tuple[str, ...] = tuple(status.value for status in NotificationStatus)


class RealNotificationConnector:
    def send(self, notification: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Invio reale non configurato: usare connettore autorizzato o stub di test.")


class StubNotificationConnector:
    def send(self, notification: dict[str, Any]) -> dict[str, Any]:
        return {"mode": "stub", "notification_id": notification.get("id"), "sent": True}


def create_notification_event(
    repo: ProcedureLifecycleRepository,
    *,
    fascicolo_id: str,
    notification_type: str,
    act_document_id: str,
    obligation_id: int | None = None,
    **payload: Any,
) -> int:
    return repo.create_notification_event(
        {
            "fascicolo_id": fascicolo_id,
            "obligation_id": obligation_id,
            "notification_type": notification_type,
            "recipient_name": payload.get("recipient_name"),
            "recipient_tax_code": payload.get("recipient_tax_code"),
            "recipient_address": payload.get("recipient_address"),
            "recipient_address_source": payload.get("recipient_address_source"),
            "act_document_id": act_document_id,
            "relata_document_id": payload.get("relata_document_id"),
            "status": payload.get("status", NotificationStatus.DRAFT.value),
            "notes": payload.get("notes"),
        }
    )


def mark_notification_ready(repo: ProcedureLifecycleRepository, notification_id: int, *, reviewed: bool = False) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if not notification.get("recipient_name") or not notification.get("recipient_address"):
        raise ValueError("Destinatario e indirizzo sono obbligatori per READY.")
    if not notification.get("recipient_address_source") and not reviewed:
        raise ValueError("Fonte indirizzo obbligatoria oppure review avvocato esplicita.")
    updates: dict[str, Any] = {"status": NotificationStatus.READY.value}
    if reviewed and not notification.get("recipient_address_source"):
        updates["recipient_address_source"] = "manuale_con_review"
        updates["notes"] = "review avvocato su domicilio digitale"
    repo.update_notification_event(notification_id, updates)


def attach_relata(repo: ProcedureLifecycleRepository, notification_id: int, relata_document_id: str) -> None:
    if not relata_document_id:
        raise ValueError("relata_document_id obbligatorio.")
    repo.update_notification_event(notification_id, {"relata_document_id": relata_document_id})


def record_notification_sent(
    repo: ProcedureLifecycleRepository,
    notification_id: int,
    connector: StubNotificationConnector | RealNotificationConnector | None = None,
) -> dict[str, Any]:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if notification.get("status") != NotificationStatus.READY.value:
        raise ValueError("La notifica può essere inviata solo dopo READY.")
    result = (connector or StubNotificationConnector()).send(notification)
    repo.update_notification_event(
        notification_id,
        {"status": NotificationStatus.SENT.value, "sent_at": datetime.now(UTC).isoformat(timespec="seconds")},
    )
    return result


def record_notification_delivery(repo: ProcedureLifecycleRepository, notification_id: int, delivered: bool = True) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if notification.get("status") != NotificationStatus.SENT.value:
        raise ValueError("La consegna può essere registrata solo dopo SENT.")
    repo.update_notification_event(
        notification_id,
        {
            "status": NotificationStatus.DELIVERED.value if delivered else NotificationStatus.FAILED.value,
            "delivered_at": datetime.now(UTC).isoformat(timespec="seconds") if delivered else None,
        },
    )


def acquire_notification_proof(repo: ProcedureLifecycleRepository, notification_id: int, evidence_id: int) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if notification.get("status") not in {NotificationStatus.SENT.value, NotificationStatus.DELIVERED.value}:
        raise ValueError("La prova si acquisisce solo dopo invio o consegna.")
    link_evidence_to_notification(repo, notification_id=notification_id, evidence_id=evidence_id)


def acquire_notification_proof_bundle(repo: ProcedureLifecycleRepository, notification_id: int, proof_bundle_id: str) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if notification.get("status") not in {NotificationStatus.SENT.value, NotificationStatus.DELIVERED.value}:
        raise ValueError("La prova si acquisisce solo dopo invio o consegna.")
    repo.update_notification_event(
        notification_id,
        {"status": NotificationStatus.PROOF_ACQUIRED.value, "proof_bundle_id": proof_bundle_id},
        source="notification_proof_validation",
    )


def proof_deposit_required(repo: ProcedureLifecycleRepository, notification_id: int) -> bool:
    notification = repo.get_notification_event(notification_id)
    if not notification or not notification.get("obligation_id"):
        return False
    obligations = repo.list_obligations(str(notification.get("fascicolo_id") or ""))
    return any(
        int(row.get("id") or 0) == int(notification["obligation_id"])
        and str(row.get("obligation_type") or "") == "DEPOSITO_PROVA_NOTIFICA"
        for row in obligations
    )


def mark_proof_deposit_required(repo: ProcedureLifecycleRepository, notification_id: int) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if notification.get("status") != NotificationStatus.PROOF_ACQUIRED.value:
        raise ValueError("Serve prima acquisire la prova notifica.")
    if proof_deposit_required(repo, notification_id):
        repo.update_notification_event(
            notification_id,
            {"status": NotificationStatus.PROOF_DEPOSIT_REQUIRED.value},
            source="notification_proof_validation",
        )


def mark_proof_deposited(repo: ProcedureLifecycleRepository, notification_id: int, deposit_evidence_id: int) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if notification.get("status") not in {
        NotificationStatus.PROOF_DEPOSIT_REQUIRED.value,
        NotificationStatus.PROOF_ACQUIRED.value,
    }:
        raise ValueError("Stato notifica non compatibile con deposito prova.")
    with repo.connect() as conn:
        evidence = repo._fetch_one(conn, "SELECT * FROM evidence_documents WHERE id = ?", (deposit_evidence_id,))
    if not evidence:
        raise ValueError("Evidenza deposito prova mancante.")
    if str(evidence.get("fascicolo_id") or "") != str(notification.get("fascicolo_id") or ""):
        raise ValueError("Evidenza deposito prova di altro fascicolo.")
    proof_bundle_id = notification.get("proof_bundle_id")
    with repo.connect() as conn:
        case = fetch_notification_case_for_event(conn, notification_id)
        if case:
            proof_deposit = repo._fetch_one(
                conn,
                """
                SELECT bundle_id FROM notification_proof_deposits
                WHERE notification_case_id = ?
                  AND deposit_status = 'OFFICE_ACCEPTED'
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(case["id"]),),
            )
            if proof_deposit:
                proof_bundle_id = proof_deposit.get("bundle_id")
    if not proof_bundle_id:
        raise ValueError("Deposito prova richiede bundle probatorio già validato.")
    repo.update_notification_event(
        notification_id,
        {
            "status": NotificationStatus.PROOF_DEPOSITED.value,
            "proof_bundle_id": proof_bundle_id,
        },
        source="notification_proof_validation",
    )
