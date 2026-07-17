"""Servizi applicativi per notifiche interne e canale Web Push."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from pct.pec_operational_cleanup import is_legacy_pec_notification_item

from .models import (
    NotificationPreferences,
    NotificationRecord,
    PushSubscriptionRecord,
    normalize_priority,
    utc_now_iso,
)
from .repository import NotificationRepository
from .web_push import (
    WebPushConfig,
    load_web_push_config,
    safe_remote_hearing_url,
    safe_web_push_payload,
    send_web_push,
)


ENDPOINT_RE = re.compile(r"^https://.+", re.IGNORECASE)
LOCAL_ENDPOINT_RE = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?/", re.IGNORECASE)
ROME_TZ = ZoneInfo("Europe/Rome")
REMOTE_HEARING_ITEM_FIELDS = (
    "remoteHearingDetected",
    "remoteHearingMode",
    "remoteHearingUrl",
    "remoteHearingSource",
    "remoteHearingVerified",
    "remoteHearingTime",
    "remoteHearingPlatform",
    "remoteHearingMeetingId",
    "remoteHearingPasscode",
    "remoteHearingAccessInfo",
    "remoteHearingPdfRequired",
)


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


def _quiet_now(preferences: NotificationPreferences, *, now: datetime | None = None) -> bool:
    if not preferences.quiet_hours_enabled:
        return False
    start = _parse_hhmm(preferences.quiet_hours_start)
    end = _parse_hhmm(preferences.quiet_hours_end)
    if start is None or end is None:
        return False
    current_dt = now or datetime.now(ROME_TZ)
    if current_dt.tzinfo is None:
        current_dt = current_dt.replace(tzinfo=ROME_TZ)
    else:
        current_dt = current_dt.astimezone(ROME_TZ)
    current = current_dt.time().replace(microsecond=0, tzinfo=None)
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def _remote_hearing_push_state(payload: dict[str, Any] | None) -> tuple[int, str]:
    data = payload if isinstance(payload, dict) else {}
    mode = clean_text(data.get("remoteHearingMode"), limit=40).lower()
    detected = str(data.get("remoteHearingDetected") or "").strip().lower() in {"1", "true", "yes", "on"}
    detected = detected or mode in {"remoto", "mista", "audiovisiva", "teams"}
    accepted_url = safe_remote_hearing_url(data, require_verified=False)
    verified_url = safe_remote_hearing_url(data, require_verified=True)
    if verified_url:
        return 3, verified_url
    if accepted_url:
        return 2, accepted_url
    if detected or str(data.get("remoteHearingPdfRequired") or "").strip().lower() in {"1", "true", "yes", "on"}:
        return 1, ""
    return 0, ""


def _remote_hearing_push_enriched(
    previous_payload: dict[str, Any] | None,
    current_payload: dict[str, Any] | None,
) -> bool:
    previous_level, _previous_url = _remote_hearing_push_state(previous_payload)
    current_level, current_url = _remote_hearing_push_state(current_payload)
    return bool(current_level == 3 and current_url and previous_level < 3)


def _operational_item_score(item: dict[str, Any]) -> tuple[int, int, int, int]:
    href = clean_text(item.get("href"), limit=500)
    remote_level, _remote_url = _remote_hearing_push_state(item)
    remote_details = sum(bool(item.get(key)) for key in REMOTE_HEARING_ITEM_FIELDS)
    return (
        1 if href.startswith("/agenda/") else 0,
        1 if clean_text(item.get("type"), limit=80) == "hearing" else 0,
        remote_level,
        remote_details,
    )


def _merge_operational_items(primary: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    preferred = candidate if _operational_item_score(candidate) > _operational_item_score(primary) else primary
    alternate = primary if preferred is candidate else candidate
    merged = dict(preferred)
    richer_remote = (
        candidate
        if _remote_hearing_push_state(candidate) > _remote_hearing_push_state(primary)
        else primary
    )
    for key in REMOTE_HEARING_ITEM_FIELDS:
        value = richer_remote.get(key)
        if value not in (None, "", False):
            merged[key] = value
        elif key not in merged and key in alternate:
            merged[key] = alternate[key]
    priority_rank = {"normal": 1, "important": 2, "urgent": 3}
    if priority_rank.get(str(alternate.get("priority") or ""), 0) > priority_rank.get(
        str(merged.get("priority") or ""), 0
    ):
        merged["priority"] = alternate.get("priority")
    for key in ("title", "message", "body", "actionLabel", "sourceType", "createdAt"):
        if not merged.get(key) and alternate.get(key):
            merged[key] = alternate[key]
    return merged


def coalesce_operational_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unisce proiezioni della stessa attività senza perdere i dati audiovisivi."""

    merged_by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    unkeyed: list[dict[str, Any]] = []
    for raw_item in items:
        item = dict(raw_item or {})
        item_id = clean_text(item.get("id"), limit=240)
        if not item_id:
            unkeyed.append(item)
            continue
        if item_id not in merged_by_id:
            merged_by_id[item_id] = item
            order.append(item_id)
            continue
        merged_by_id[item_id] = _merge_operational_items(merged_by_id[item_id], item)
    return [merged_by_id[item_id] for item_id in order] + unkeyed


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
        redispatch_on_remote_hearing_enrichment: bool = False,
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
        existing = (
            self.repository.get_notification_by_dedupe_key(record.tenant_id, record.user_id, record.dedupe_key)
            if redispatch_on_remote_hearing_enrichment and record.dedupe_key
            else None
        )
        saved, created = self.repository.upsert_notification(record)
        enriched = bool(
            not created
            and existing is not None
            and redispatch_on_remote_hearing_enrichment
            and _remote_hearing_push_enriched(existing.payload_json, saved.payload_json)
        )
        if enriched and self.repository.mark_unread(saved.tenant_id, saved.user_id, saved.id):
            saved.read_at = ""
        should_dispatch = bool(send_push and (created or enriched))
        summary = (
            self.dispatch_web_push(saved)
            if should_dispatch
            else PushDispatchSummary(configured=self.web_push_config.configured, skipped=1)
        )
        return saved, created, summary

    def sync_operational_items(
        self,
        *,
        tenant_id: str,
        user_id: str,
        items: list[dict[str, Any]],
        expire_source_types: set[str] | None = None,
    ) -> list[NotificationRecord]:
        active_dedupe_keys: set[str] = set()
        for item in coalesce_operational_items(items):
            if is_legacy_pec_notification_item(item):
                continue
            item_id = clean_text(item.get("id"), limit=240)
            if not item_id:
                continue
            active_dedupe_keys.add(item_id)
            remote_payload = {
                "remoteHearingDetected": bool(item.get("remoteHearingDetected")),
                "remoteHearingMode": clean_text(item.get("remoteHearingMode"), limit=40),
                "remoteHearingUrl": clean_text(item.get("remoteHearingUrl"), limit=1000),
                "remoteHearingSource": clean_text(item.get("remoteHearingSource"), limit=500),
                "remoteHearingVerified": bool(item.get("remoteHearingVerified")),
                "remoteHearingTime": clean_text(item.get("remoteHearingTime"), limit=120),
                "remoteHearingPlatform": clean_text(item.get("remoteHearingPlatform"), limit=80),
                "remoteHearingMeetingId": clean_text(item.get("remoteHearingMeetingId"), limit=160),
                "remoteHearingPasscode": clean_text(item.get("remoteHearingPasscode"), limit=160),
                "remoteHearingAccessInfo": clean_text(item.get("remoteHearingAccessInfo"), limit=500),
                "remoteHearingPdfRequired": bool(item.get("remoteHearingPdfRequired")),
            }
            remote_level, _remote_url = _remote_hearing_push_state(remote_payload)
            self.create_notification(
                tenant_id=tenant_id,
                user_id=user_id,
                type=clean_text(item.get("type"), limit=80) or "operational",
                priority=normalize_priority(item.get("priority")),
                title=clean_text(item.get("title"), limit=220),
                body=clean_text(item.get("message") or item.get("body"), limit=1000),
                href=clean_text(item.get("href"), limit=500),
                source_type=clean_text(item.get("sourceType") or item.get("type"), limit=80),
                source_id=item_id,
                dedupe_key=item_id,
                payload_json={
                    "actionLabel": clean_text(item.get("actionLabel"), limit=120),
                    "createdAt": clean_text(item.get("createdAt"), limit=60),
                    "operationalSync": True,
                    **remote_payload,
                },
                send_push=remote_level in {0, 3},
                redispatch_on_remote_hearing_enrichment=True,
            )
        self.repository.expire_notifications_not_in_dedupe_keys(
            tenant_id,
            user_id,
            active_dedupe_keys=active_dedupe_keys,
            source_types=expire_source_types
            or {"deadline", "hearing", "task", "communication", "document", "filing"},
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
