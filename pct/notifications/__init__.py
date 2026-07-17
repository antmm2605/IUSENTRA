"""Centro notifiche persistente IUSENTRA."""

from .models import NotificationPreferences, NotificationRecord, PushSubscriptionRecord
from .repository import NotificationRepository
from .service import (
    NotificationService,
    NotificationServiceError,
    PushDispatchSummary,
    coalesce_operational_items,
)
from .web_push import WebPushConfig, load_web_push_config, safe_web_push_payload, send_web_push

__all__ = [
    "NotificationPreferences",
    "NotificationRecord",
    "NotificationRepository",
    "NotificationService",
    "NotificationServiceError",
    "PushDispatchSummary",
    "coalesce_operational_items",
    "PushSubscriptionRecord",
    "WebPushConfig",
    "load_web_push_config",
    "safe_web_push_payload",
    "send_web_push",
]
