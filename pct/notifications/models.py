"""Modelli dominio per notifiche interne e Web Push."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


PRIORITIES = {"normal", "important", "urgent"}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def normalize_priority(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in PRIORITIES else "normal"


def json_dump(value: Any) -> str:
    return json.dumps(value if isinstance(value, (dict, list)) else {}, ensure_ascii=False, sort_keys=True)


def json_load(value: Any, default: Any | None = None) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return {} if default is None else default
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {} if default is None else default
    return parsed if isinstance(parsed, (dict, list)) else ({} if default is None else default)


@dataclass
class NotificationRecord:
    id: str = field(default_factory=lambda: new_id("ntf"))
    tenant_id: str = ""
    user_id: str = ""
    type: str = "operational"
    priority: str = "normal"
    title: str = ""
    body: str = ""
    href: str = ""
    source_type: str = ""
    source_id: str = ""
    dedupe_key: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    read_at: str = ""
    expires_at: str = ""
    payload_json: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "NotificationRecord":
        self.priority = normalize_priority(self.priority)
        self.tenant_id = str(self.tenant_id or "").strip()
        self.user_id = str(self.user_id or "").strip()
        self.type = str(self.type or "operational").strip()[:80]
        self.title = str(self.title or "Notifica operativa").strip()[:220]
        self.body = str(self.body or "").strip()[:1000]
        self.href = str(self.href or "").strip()[:500]
        self.source_type = str(self.source_type or "").strip()[:80]
        self.source_id = str(self.source_id or "").strip()[:180]
        self.dedupe_key = str(self.dedupe_key or "").strip()[:240]
        if not isinstance(self.payload_json, dict):
            self.payload_json = {}
        return self

    def to_db(self) -> dict[str, Any]:
        payload = asdict(self.normalized())
        payload["payload_json"] = json_dump(self.payload_json)
        return payload

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "NotificationRecord":
        data = dict(payload or {})
        data["payload_json"] = json_load(data.get("payload_json"), {})
        fields = set(cls.__dataclass_fields__)
        return cls(**{key: data.get(key, "") for key in fields}).normalized()


@dataclass
class PushSubscriptionRecord:
    id: str = field(default_factory=lambda: new_id("sub"))
    tenant_id: str = ""
    user_id: str = ""
    endpoint: str = ""
    p256dh: str = ""
    auth: str = ""
    user_agent: str = ""
    device_label: str = ""
    enabled: bool = True
    created_at: str = field(default_factory=utc_now_iso)
    last_seen_at: str = field(default_factory=utc_now_iso)
    revoked_at: str = ""

    def normalized(self) -> "PushSubscriptionRecord":
        self.tenant_id = str(self.tenant_id or "").strip()
        self.user_id = str(self.user_id or "").strip()
        self.endpoint = str(self.endpoint or "").strip()[:2048]
        self.p256dh = str(self.p256dh or "").strip()[:512]
        self.auth = str(self.auth or "").strip()[:512]
        self.user_agent = str(self.user_agent or "").strip()[:500]
        self.device_label = str(self.device_label or "").strip()[:120]
        self.enabled = bool(self.enabled)
        return self

    def to_db(self) -> dict[str, Any]:
        payload = asdict(self.normalized())
        payload["enabled"] = 1 if self.enabled else 0
        return payload

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "PushSubscriptionRecord":
        data = dict(payload or {})
        data["enabled"] = bool(data.get("enabled"))
        fields = set(cls.__dataclass_fields__)
        return cls(**{key: data.get(key, "") for key in fields}).normalized()


@dataclass
class NotificationPreferences:
    tenant_id: str
    user_id: str
    push_enabled: bool = True
    notify_urgent: bool = True
    notify_important: bool = True
    notify_normal: bool = False
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def defaults(cls, tenant_id: str, user_id: str) -> "NotificationPreferences":
        return cls(tenant_id=str(tenant_id or "").strip(), user_id=str(user_id or "").strip())

    @classmethod
    def from_mapping(cls, payload: dict[str, Any], tenant_id: str, user_id: str) -> "NotificationPreferences":
        data = dict(payload or {})
        return cls(
            tenant_id=str(data.get("tenant_id") or tenant_id or "").strip(),
            user_id=str(data.get("user_id") or user_id or "").strip(),
            push_enabled=bool(data.get("push_enabled", True)),
            notify_urgent=bool(data.get("notify_urgent", True)),
            notify_important=bool(data.get("notify_important", True)),
            notify_normal=bool(data.get("notify_normal", False)),
            quiet_hours_enabled=bool(data.get("quiet_hours_enabled", False)),
            quiet_hours_start=str(data.get("quiet_hours_start") or "22:00"),
            quiet_hours_end=str(data.get("quiet_hours_end") or "07:00"),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
        )

    def to_db(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "push_enabled": 1 if self.push_enabled else 0,
            "notify_urgent": 1 if self.notify_urgent else 0,
            "notify_important": 1 if self.notify_important else 0,
            "notify_normal": 1 if self.notify_normal else 0,
            "quiet_hours_enabled": 1 if self.quiet_hours_enabled else 0,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "updated_at": self.updated_at,
        }
