"""Helper per eventi audit leggibili e hash-chain probatoria."""

from __future__ import annotations

from typing import Any

from .evidence_hash import canonical_json, chain_hash, sha256_text, utc_now


def build_audit_payload(
    *,
    tenant_id: str,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_payload = dict(payload or {})
    return {
        "tenant_id": str(tenant_id or "default"),
        "occurred_at": utc_now(),
        "actor": str(actor or "sistema"),
        "action": str(action or "document.event"),
        "resource_type": str(resource_type or "document"),
        "resource_id": str(resource_id or ""),
        "payload": clean_payload,
    }


def audit_hash(prev_hash: str, event: dict[str, Any]) -> str:
    return chain_hash(prev_hash, event)


def payload_digest(payload: dict[str, Any]) -> str:
    return sha256_text(canonical_json(payload))
