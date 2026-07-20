"""Presidio persistente delle notifiche legali rilevate dalle PEC."""

from .historical_policy import HistoricalDecision, classify_historical_record
from .identity import (
    CorrelationDecision,
    IdentityDecision,
    canonical_document_identity,
    notification_instance_identity,
    recipient_identity_key,
)
from .models import (
    DocumentRole,
    FailureAttribution,
    PresidioStatus,
    Priority,
    ReceiptKind,
)
from .reconciler import NotificationReceiptEnvelope, PecNotificationReconciler
from .repository import NotificationPresidioRepository
from .service import NotificationPresidioService
from .work_queue import NotificationPresidioWorkQueue

__all__ = [
    "CorrelationDecision",
    "DocumentRole",
    "FailureAttribution",
    "HistoricalDecision",
    "IdentityDecision",
    "NotificationPresidioRepository",
    "NotificationPresidioService",
    "NotificationPresidioWorkQueue",
    "NotificationReceiptEnvelope",
    "PecNotificationReconciler",
    "PresidioStatus",
    "Priority",
    "ReceiptKind",
    "canonical_document_identity",
    "classify_historical_record",
    "notification_instance_identity",
    "recipient_identity_key",
]
