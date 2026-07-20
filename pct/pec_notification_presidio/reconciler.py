from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .identity import normalize_pec, recipient_identity_key
from .models import (
    PresidioStatus,
    ReceiptKind,
    canonical_json,
    normalize_failure_attribution,
    required_text,
    sha256_text,
    utc_now_iso,
)
from .repository import NotificationPresidioRepository
from .work_queue import NotificationPresidioWorkQueue


@dataclass(frozen=True, slots=True)
class NotificationReceiptEnvelope:
    kind: ReceiptKind
    message_id: str
    original_message_id: str = ""
    presidio_id: str = ""
    recipient_address: str = ""
    recipient_name: str = ""
    recipient_fiscal_id: str = ""
    occurred_at: str = ""
    eml_sha256: str = ""
    attachment_sha256: str = ""
    source_id: str = ""
    source_locator: str = ""
    failure_reason: str = ""
    failure_attribution: str = ""
    failure_classification: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        required_text(self.message_id, "message_id")
        if self.kind != ReceiptKind.SENT and not self.original_message_id:
            raise ValueError("Le ricevute richiedono l'identificativo originale della PEC inviata")
        if self.kind == ReceiptKind.SENT and not self.presidio_id:
            raise ValueError("La PEC inviata richiede presidio_id risolto lato server")

    def resolved_failure_attribution(self) -> str:
        return normalize_failure_attribution(self.failure_attribution or self.failure_classification)

    def recipient_key(self) -> str:
        identity = {
            "pec_address": self.recipient_address,
            "name": self.recipient_name,
            "fiscal_id": self.recipient_fiscal_id,
        }
        if any(str(value or "").strip() for value in identity.values()):
            return recipient_identity_key(identity)
        return sha256_text(canonical_json(["unknown-recipient", self.original_message_id, self.message_id]))

    def to_internal_dict(self) -> dict[str, Any]:
        return {
            "receipt_type": self.kind.value,
            "message_id": self.message_id,
            "original_message_id": self.original_message_id,
            "presidio_id": self.presidio_id,
            "recipient_address": self.recipient_address,
            "recipient_name": self.recipient_name,
            "recipient_fiscal_id": self.recipient_fiscal_id,
            "recipient_identity_key": self.recipient_key(),
            "occurred_at": self.occurred_at,
            "eml_sha256": self.eml_sha256,
            "attachment_sha256": self.attachment_sha256,
            "source_id": self.source_id,
            "source_locator": self.source_locator,
            "failure_reason": self.failure_reason,
            "failure_attribution": self.resolved_failure_attribution(),
            "failure_classification": self.failure_classification,
            "metadata": dict(self.metadata),
        }


class PecNotificationReconciler:
    """Riconcilia solo identificativi PEC forti; l'oggetto non chiude mai un presidio."""

    def __init__(
        self,
        repository: NotificationPresidioRepository,
        queue: NotificationPresidioWorkQueue | None = None,
    ) -> None:
        self.repository = repository
        self.queue = queue or NotificationPresidioWorkQueue(repository)

    def _recipient_for_sent(self, envelope: NotificationReceiptEnvelope) -> dict[str, Any] | None:
        key = envelope.recipient_key()
        with self.repository.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM pec_legal_notification_recipients
                WHERE tenant_id=? AND presidio_id=? AND recipient_identity_key=?
                """,
                (self.repository.tenant_id, envelope.presidio_id, key),
            ).fetchone()
            if row is None and envelope.recipient_address:
                row = conn.execute(
                    """
                    SELECT * FROM pec_legal_notification_recipients
                    WHERE tenant_id=? AND presidio_id=? AND pec_address=?
                    ORDER BY updated_at DESC, id DESC LIMIT 1
                    """,
                    (
                        self.repository.tenant_id,
                        envelope.presidio_id,
                        normalize_pec(envelope.recipient_address),
                    ),
                ).fetchone()
        return dict(row) if row is not None else None

    def _unmatched(self, envelope: NotificationReceiptEnvelope, reason: str) -> dict[str, Any]:
        payload = envelope.to_internal_dict()
        payload["unmatched_reason"] = reason
        row, created = self.queue.store_unmatched_receipt(
            {
                **payload,
                "payload": payload,
                "receipt_key": sha256_text(
                    canonical_json(
                        [envelope.message_id, envelope.kind.value, payload["recipient_identity_key"]]
                    )
                ),
            }
        )
        return {"matched": False, "unmatchedId": row.get("id", ""), "created": created}

    def _append_receipt_evidence(
        self,
        presidio_id: str,
        recipient_id: str,
        envelope: NotificationReceiptEnvelope,
    ) -> None:
        self.repository.append_evidence(
            presidio_id,
            {
                "recipient_id": recipient_id,
                "evidence_type": envelope.kind.value,
                "source_type": "pec_message",
                "source_id": envelope.source_id or envelope.message_id,
                "message_id": envelope.message_id,
                "eml_sha256": envelope.eml_sha256,
                "attachment_sha256": envelope.attachment_sha256,
                "source_locator": envelope.source_locator,
                "confidence": 1.0,
                "created_at": envelope.occurred_at or utc_now_iso(),
            },
        )

    @staticmethod
    def _aggregate_target(counts: Mapping[str, int]) -> PresidioStatus | None:
        total = int(counts.get("recipients_total") or 0)
        delivered = int(counts.get("recipients_delivered") or 0)
        failed = int(counts.get("recipients_failed") or 0)
        rac = int(counts.get("recipients_rac") or 0)
        sent = int(counts.get("recipients_sent") or 0)
        if total > 0 and delivered == total:
            return PresidioStatus.DELIVERY_COMPLETE
        if delivered:
            return PresidioStatus.PARTIAL_DELIVERY
        if failed:
            return PresidioStatus.DELIVERY_FAILED
        if total > 0 and rac == total:
            return PresidioStatus.RAC_RECEIVED
        if sent:
            return PresidioStatus.SENT_WAITING_RAC
        return None

    def process(self, envelope: NotificationReceiptEnvelope, *, actor: str = "pec-reconciler") -> dict[str, Any]:
        envelope.validate()
        direct_proof = envelope.kind == ReceiptKind.PROOF_DEPOSIT and bool(envelope.presidio_id)
        if direct_proof:
            self.repository.get_presidio(envelope.presidio_id)
            recipient = None
        elif envelope.kind == ReceiptKind.SENT:
            recipient = self._recipient_for_sent(envelope)
        else:
            recipient = self.repository.find_recipient_for_receipt(
                original_message_id=envelope.original_message_id,
                pec_address=envelope.recipient_address,
            )
        if recipient is None and not direct_proof:
            return self._unmatched(envelope, "Nessuna correlazione forte per Message-ID e destinatario.")

        presidio_id = envelope.presidio_id if direct_proof else str(recipient["presidio_id"])
        recipient_id = "" if direct_proof else str(recipient["id"])
        self._append_receipt_evidence(presidio_id, recipient_id, envelope)
        if recipient_id:
            self.repository.mark_recipient_event(
                recipient_id,
                kind=envelope.kind,
                message_id=envelope.message_id,
                failure_reason=envelope.failure_reason,
                failure_attribution=envelope.resolved_failure_attribution(),
                evidence=envelope.metadata,
                occurred_at=envelope.occurred_at,
            )

        if envelope.kind == ReceiptKind.PROOF_DEPOSIT:
            current_status = PresidioStatus(str(self.repository.get_presidio(presidio_id)["status"]))
            proof_paths = {
                PresidioStatus.DELIVERY_COMPLETE: (
                    PresidioStatus.PROOF_TO_DEPOSIT,
                    PresidioStatus.PROOF_DEPOSITED,
                    PresidioStatus.CLOSED,
                ),
                PresidioStatus.PROOF_TO_DEPOSIT: (
                    PresidioStatus.PROOF_DEPOSITED,
                    PresidioStatus.CLOSED,
                ),
                PresidioStatus.PROOF_DEPOSITED: (PresidioStatus.CLOSED,),
                PresidioStatus.CLOSED: (),
            }
            if current_status not in proof_paths:
                raise ValueError("Ricevuta deposito prova incompatibile con lo stato corrente")
            targets = proof_paths[current_status]
        else:
            target = self._aggregate_target(self.repository.recipient_counts(presidio_id))
            targets = (target,) if target is not None else ()
        transition_id = ""
        for target in targets:
            current = self.repository.get_presidio(presidio_id)
            if str(current.get("status") or "") != target.value:
                result = self.repository.transition(
                    presidio_id,
                    target,
                    actor=actor,
                    reason=f"Riconciliazione {envelope.kind.value} per singolo destinatario.",
                    evidence={
                        "message_id": envelope.message_id,
                        "recipient_id": recipient_id,
                        "failure_attribution": envelope.resolved_failure_attribution(),
                    },
                    idempotency_key=f"receipt:{envelope.message_id}:{recipient_id}:{target.value}",
                    occurred_at=envelope.occurred_at,
                )
                transition_id = result.transition_id
        current_status = str(self.repository.get_presidio(presidio_id).get("status") or "")
        return {
            "matched": True,
            "presidioId": presidio_id,
            "recipientId": recipient_id,
            "transitionId": transition_id,
            "status": current_status,
        }

    def reconcile_one_unmatched(self, worker_id: str) -> dict[str, Any] | None:
        item = self.queue.claim_unmatched(worker_id)
        if item is None:
            return None
        payload = item.get("payload") or {}
        try:
            envelope = NotificationReceiptEnvelope(
                kind=ReceiptKind(str(payload.get("receipt_type"))),
                message_id=str(payload.get("message_id") or ""),
                original_message_id=str(payload.get("original_message_id") or ""),
                presidio_id=str(payload.get("presidio_id") or ""),
                recipient_address=str(payload.get("recipient_address") or ""),
                recipient_name=str(payload.get("recipient_name") or ""),
                recipient_fiscal_id=str(payload.get("recipient_fiscal_id") or ""),
                occurred_at=str(payload.get("occurred_at") or ""),
                eml_sha256=str(payload.get("eml_sha256") or ""),
                attachment_sha256=str(payload.get("attachment_sha256") or ""),
                source_id=str(payload.get("source_id") or ""),
                source_locator=str(payload.get("source_locator") or ""),
                failure_reason=str(payload.get("failure_reason") or ""),
                failure_attribution=str(
                    payload.get("failure_attribution") or payload.get("failure_classification") or ""
                ),
                failure_classification=str(payload.get("failure_classification") or ""),
                metadata=payload.get("metadata") or {},
            )
            result = self.process(envelope)
            if not result.get("matched"):
                self.queue.release_unmatched(str(item["id"]), worker_id=worker_id)
                return result
            self.queue.resolve_unmatched(
                str(item["id"]),
                worker_id=worker_id,
                presidio_id=str(result["presidioId"]),
                recipient_id=str(result["recipientId"]),
            )
            return result
        except Exception:
            self.queue.release_unmatched(str(item["id"]), worker_id=worker_id)
            raise
