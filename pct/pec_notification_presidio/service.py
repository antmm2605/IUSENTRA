from __future__ import annotations

from typing import Any, Mapping

from .historical_policy import classify_historical_record
from .identity import canonical_document_identity, notification_instance_identity
from .models import Priority, canonical_json, required_text, sha256_text
from .repository import NotificationPresidioRepository


class NotificationPresidioService:
    """Orchestrazione deterministica; nessun OCR, filesystem o rete nel percorso caldo."""

    def __init__(self, repository: NotificationPresidioRepository) -> None:
        self.repository = repository

    def create_candidate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        recipients = tuple(payload.get("recipients") or ())
        documents = tuple(payload.get("documents") or ())
        if not recipients:
            raise ValueError("Almeno un destinatario è obbligatorio")
        if not documents:
            raise ValueError("Almeno un documento sorgente è obbligatorio")
        primary = dict(documents[0])
        primary.setdefault("source_message_id", payload.get("source_message_id"))
        document_identity = canonical_document_identity(primary)
        source_order = str(
            payload.get("source_order_or_event_id")
            or payload.get("legal_event_id")
            or payload.get("source_message_id")
            or ""
        )
        instance_key = notification_instance_identity(
            tenant_id=self.repository.tenant_id,
            fascicolo_id=required_text(payload.get("fascicolo_id"), "fascicolo_id"),
            canonical_document_key=document_identity.key,
            document_version=str(primary.get("document_version") or "1"),
            notification_case=required_text(payload.get("notification_case"), "notification_case"),
            source_order_or_event_id=source_order,
            recipients=recipients,
            channel=str(payload.get("channel") or "pec"),
        )
        policy = classify_historical_record(payload)
        status = policy.status
        priority = Priority(str(payload.get("priority") or policy.priority))
        dedupe_key = sha256_text(
            canonical_json(
                [
                    "notification-candidate-v1",
                    self.repository.tenant_id,
                    payload.get("source_message_id"),
                    payload.get("trigger_type"),
                    instance_key,
                ]
            )
        )
        candidate = {
            **dict(payload),
            "status": status.value,
            "priority": priority.value,
            "human_review_required": bool(
                payload.get("human_review_required")
                or policy.human_review_required
                or document_identity.human_review_required
            ),
            "confidence": min(
                float(
                    payload.get("confidence")
                    if payload.get("confidence") is not None
                    else document_identity.confidence
                ),
                document_identity.confidence,
            ),
            "source_effective_at": str(payload.get("source_effective_at") or policy.effective_at),
            "legacy_policy_id": policy.policy_id,
            "legacy_assumed_handled": policy.legacy_assumed_handled,
            "detection_reason": str(payload.get("detection_reason") or policy.reason),
            "dedupe_key": dedupe_key,
            "notification_instance_key": instance_key,
        }
        presidio, created = self.repository.create_or_get_presidio(candidate)
        for document in documents:
            item = dict(document)
            item.setdefault("source_message_id", payload.get("source_message_id"))
            self.repository.upsert_document(str(presidio["id"]), item)
        for recipient in recipients:
            self.repository.upsert_recipient(str(presidio["id"]), recipient)
        return {
            "id": str(presidio["id"]),
            "created": created,
            "status": str(presidio["status"]),
            "priority": str(presidio["priority"]),
            "humanReviewRequired": bool(presidio.get("human_review_required")),
        }

    def list_projection(
        self,
        *,
        status: str = "",
        priority: str = "",
        fascicolo_id: str = "",
        assigned_user_id: str = "",
        channel: str = "",
        recipient_identity_key: str = "",
        legacy_assumed_handled: bool | None = None,
        needs_review: bool | None = None,
        date_from: str = "",
        date_to: str = "",
        cursor: tuple[str, str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self.repository.list_presidia(
            status=status,
            priority=priority,
            fascicolo_id=fascicolo_id,
            assigned_user_id=assigned_user_id,
            channel=channel,
            recipient_identity_key=recipient_identity_key,
            legacy_assumed_handled=legacy_assumed_handled,
            needs_review=needs_review,
            date_from=date_from,
            date_to=date_to,
            cursor=cursor,
            limit=limit,
        ).to_public_dict()
