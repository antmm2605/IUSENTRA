"""Audit log firmato HMAC con verifica integrita'."""

from __future__ import annotations

import hmac
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any


@dataclass
class AuditEvent:
    id: str
    timestamp: str
    user_id: str
    tenant_id: str
    ip: str
    user_agent: str
    action: str
    entity_type: str
    entity_id: str
    result: str
    details: dict[str, Any]
    previous_hash: str
    signature: str = ""


def build_audit_event(
    *,
    key: str,
    action: str,
    user_id: str = "",
    tenant_id: str = "",
    ip: str = "",
    user_agent: str = "",
    entity_type: str = "",
    entity_id: str = "",
    result: str = "ok",
    details: dict[str, Any] | None = None,
    previous_hash: str = "",
) -> AuditEvent:
    event = AuditEvent(
        id=secrets.token_urlsafe(16),
        timestamp=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        result=result,
        details=details or {},
        previous_hash=previous_hash,
    )
    event.signature = sign_event(key, event)
    return event


def sign_event(key: str, event: AuditEvent) -> str:
    if not key:
        raise ValueError("AUDIT_HMAC_KEY mancante")
    payload = asdict(event)
    payload["signature"] = ""
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(key.encode(), raw, sha256).hexdigest()


def verify_event(key: str, event: AuditEvent) -> bool:
    expected = sign_event(key, event)
    return hmac.compare_digest(expected, event.signature)
