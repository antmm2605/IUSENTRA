"""Servizi applicativi per notifiche interne e canale Web Push."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from .models import (
    NotificationPreferences,
    NotificationRecord,
    PushSubscriptionRecord,
    normalize_priority,
    utc_now_iso,
)
from .repository import NotificationRepository
from .web_push import WebPushConfig, load_web_push_config, safe_web_push_payload, send_web_push


ENDPOINT_RE = re.compile(r"^https://.+", re.IGNORECASE)
LOCAL_ENDPOINT_RE = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?/", re.IGNORECASE)


class NotificationServiceError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class PushDispatchSummary:
    configured: bool
    attempted: int = 0
    sent: int = 0
    disabled: int = 0
    skipped: int = 0


def clean_text(value: Any, *, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _parse_hhmm(value: str) -> time | None:
    try:
        return time.fromisoformat(str(value or "")[:5])
    except ValueError:
        return None


def _quiet_now(preferences: NotificationPreferences) -> bool:
    if not preferences.quiet_hours_enabled:
        return False
    start = _parse_hhmm(preferences.quiet_hours_start)
    end = _parse_hhmm(preferences.quiet_hours_end)
    if start is None or end is None:
        return False
    current = datetime.now().time().replace(microsecond=0)
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


class NotificationService:
    def __init__(self, repository: NotificationRepository, *, web_push_config: WebPushConfig | None = None) -> None:
        self.repository = repository
        self.web_push_config = web_push_config or load_web_push_config()

    def create_notification(
        self,
        *,
        tenant_id: str,
        user_id: str,
        type: str,
        priority: str,
        title: str,
        body: str,
        href: str = "",
        source_type: str = "",
        source_id: str = "",
        dedupe_key: str = "",
        expires_at: str = "",
        payload_json: dict[str, Any] | None = None,
        send_push: bool = True,
    ) -> tuple[NotificationRecord, bool, PushDispatchSummary]:
        record = NotificationRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            type=clean_text(type, limit=80) or "operational",
            priority=normalize_priority(priority),
            title=clean_text(title, limit=220) or "Notifica operativa",
            body=clean_text(body, limit=1000),
            href=clean_text(href, limit=500),
            source_type=clean_text(source_type, limit=80),
            source_id=clean_text(source_id, limit=180),
            dedupe_key=clean_text(dedupe_key, limit=240),
            expires_at=clean_text(expires_at, limit=40),
            payload_json=payload_json or {},
        )
        saved, created = self.repository.upsert_notification(record)
        summary = (
            self.dispatch_web_push(saved)
            if created and send_push
            else PushDispatchSummary(configured=self.web_push_config.configured, skipped=1)
        )
        return saved, created, summary

    def sync_operational_items(
        self,
        *,
        tenant_id: str,
        user_id: str,
        items: list[dict[str, Any]],
    ) -> list[NotificationRecord]:
        for item in items:
            item_id = clean_text(item.get("id"), limit=240)
            if not item_id:
                continue
            self.create_notification(
                tenant_id=tenant_id,
                user_id=user_id,
                type=clean_text(item.get("type"), limit=80) or "operational",
                priority=normalize_priority(item.get("priority")),
                title=clean_text(item.get("title"), limit=220),
                body=clean_text(item.get("message") or item.get("body"), limit=1000),
                href=clean_text(item.get("href"), limit=500),
                source_type=clean_text(item.get("type"), limit=80),
                source_id=item_id,
                dedupe_key=item_id,
                payload_json={
                    "actionLabel": clean_text(item.get("actionLabel"), limit=120),
                    "createdAt": clean_text(item.get("createdAt"), limit=60),
                },
            )
        return self.repository.list_notifications(tenant_id, user_id, limit=50)

    def mark_read(self, tenant_id: str, user_id: str, notification_id: str) -> None:
        if not self.repository.mark_read(tenant_id, user_id, notification_id):
            raise NotificationServiceError("Notifica non trovata.", 404)

    def mark_all_read(self, tenant_id: str, user_id: str) -> None:
        self.repository.mark_all_read(tenant_id, user_id)

    def preferences(self, tenant_id: str, user_id: str) -> NotificationPreferences:
        return self.repository.get_preferences(tenant_id, user_id)

    def register_subscription(
        self,
        *,
        tenant_id: str,
        user_id: str,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: str = "",
        device_label: str = "",
    ) -> PushSubscriptionRecord:
        endpoint = clean_text(endpoint, limit=2048)
        p256dh = clean_text(p256dh, limit=512)
        auth = clean_text(auth, limit=512)
        if not endpoint or not (ENDPOINT_RE.match(endpoint) or LOCAL_ENDPOINT_RE.match(endpoint)):
            raise NotificationServiceError("Subscription non valida: indirizzo dispositivo mancante o non supportato.")
        if not p256dh or not auth:
            raise NotificationServiceError("Subscription non valida: chiavi dispositivo mancanti.")
        record, _created = self.repository.upsert_subscription(
            PushSubscriptionRecord(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                user_agent=clean_text(user_agent, limit=500),
                device_label=clean_text(device_label, limit=120),
            )
        )
        prefs = self.repository.get_preferences(tenant_id, user_id)
        if not prefs.push_enabled:
            prefs.push_enabled = True
            self.repository.save_preferences(prefs)
        return record

    def revoke_subscription(
        self,
        *,
        tenant_id: str,
        user_id: str,
        endpoint: str = "",
        subscription_id: str = "",
    ) -> int:
        return self.repository.revoke_subscription(
            tenant_id,
            user_id,
            endpoint=clean_text(endpoint, limit=2048),
            subscription_id=clean_text(subscription_id, limit=120),
        )

    def dispatch_web_push(self, notification: NotificationRecord) -> PushDispatchSummary:
        if not self.web_push_config.configured:
            return PushDispatchSummary(configured=False, skipped=1)
        preferences = self.repository.get_preferences(notification.tenant_id, notification.user_id)
        if not self._priority_allowed(notification.priority, preferences) or _quiet_now(preferences):
            return PushDispatchSummary(configured=True, skipped=1)
        subscriptions = self.repository.list_active_subscriptions(notification.tenant_id, notification.user_id)
        if not subscriptions:
            return PushDispatchSummary(configured=True, skipped=1)
        payload = safe_web_push_payload(notification)
        attempted = sent = disabled = 0
        for subscription in subscriptions:
            attempted += 1
            result = send_web_push(subscription, payload, config=self.web_push_config)
            if result.ok:
                sent += 1
                self.repository.record_delivery(
                    tenant_id=notification.tenant_id,
                    user_id=notification.user_id,
                    notification_id=notification.id,
                    channel="web_push",
                    status="sent",
                )
                continue
            if result.expired:
                disabled += self.repository.disable_subscription_by_id(
                    subscription.id,
                    tenant_id=notification.tenant_id,
                    user_id=notification.user_id,
                )
            self.repository.record_delivery(
                tenant_id=notification.tenant_id,
                user_id=notification.user_id,
                notification_id=notification.id,
                channel="web_push",
                status=result.status or "failed",
                detail=result.error,
            )
        return PushDispatchSummary(
            configured=True,
            attempted=attempted,
            sent=sent,
            disabled=disabled,
            skipped=max(0, len(subscriptions) - attempted),
        )

    @staticmethod
    def _priority_allowed(priority: str, preferences: NotificationPreferences) -> bool:
        if not preferences.push_enabled:
            return False
        if priority == "urgent":
            return preferences.notify_urgent
        if priority == "important":
            return preferences.notify_important
        return preferences.notify_normal

    def create_test_notification(self, *, tenant_id: str, user_id: str) -> tuple[NotificationRecord, PushDispatchSummary]:
        record, _created, _summary = self.create_notification(
            tenant_id=tenant_id,
            user_id=user_id,
            type="test",
            priority="important",
            title="Notifica dispositivo",
            body="Notifica di test pronta nel gestionale.",
            href="/app-v2",
            source_type="push_test",
            source_id=utc_now_iso(),
            dedupe_key=f"push-test:{user_id}:{utc_now_iso()}",
            payload_json={"test": True},
            send_push=False,
        )
        return record, self.dispatch_web_push(record)
