"""Workflow notifica, relata e prova documentale senza invii reali."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pct.evidence_vault import link_evidence_to_notification
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


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
            "status": payload.get("status", "DRAFT"),
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
    repo.update_notification_event(notification_id, {"status": "READY"})


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
    if notification.get("status") != "READY":
        raise ValueError("La notifica può essere inviata solo dopo READY.")
    result = (connector or StubNotificationConnector()).send(notification)
    repo.update_notification_event(
        notification_id,
        {"status": "SENT", "sent_at": datetime.utcnow().isoformat(timespec="seconds")},
    )
    return result


def record_notification_delivery(repo: ProcedureLifecycleRepository, notification_id: int, delivered: bool = True) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if notification.get("status") != "SENT":
        raise ValueError("La consegna può essere registrata solo dopo SENT.")
    repo.update_notification_event(
        notification_id,
        {
            "status": "DELIVERED" if delivered else "FAILED",
            "delivered_at": datetime.utcnow().isoformat(timespec="seconds") if delivered else None,
        },
    )


def acquire_notification_proof(repo: ProcedureLifecycleRepository, notification_id: int, evidence_id: int) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if notification.get("status") not in {"SENT", "DELIVERED"}:
        raise ValueError("La prova si acquisisce solo dopo invio o consegna.")
    link_evidence_to_notification(repo, notification_id=notification_id, evidence_id=evidence_id)


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
    if notification.get("status") != "PROOF_ACQUIRED":
        raise ValueError("Serve prima acquisire la prova notifica.")
    if proof_deposit_required(repo, notification_id):
        repo.update_notification_event(notification_id, {"status": "PROOF_DEPOSIT_REQUIRED"})


def mark_proof_deposited(repo: ProcedureLifecycleRepository, notification_id: int, deposit_evidence_id: int) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    if notification.get("status") not in {"PROOF_DEPOSIT_REQUIRED", "PROOF_ACQUIRED"}:
        raise ValueError("Stato notifica non compatibile con deposito prova.")
    with repo.connect() as conn:
        evidence = repo._fetch_one(conn, "SELECT * FROM evidence_documents WHERE id = ?", (deposit_evidence_id,))
    if not evidence:
        raise ValueError("Evidenza deposito prova mancante.")
    repo.update_notification_event(
        notification_id,
        {
            "status": "PROOF_DEPOSITED",
            "proof_bundle_id": str(evidence.get("document_id") or deposit_evidence_id),
        },
    )
