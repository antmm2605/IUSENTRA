"""Result models for audit emission, snapshots and verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuditEmitResult:
    event_id: str
    event_hash: str
    worm_uri: str
    worm_bucket: str
    worm_key: str
    worm_version_id: str
    worm_retention_until: str
    indexed: bool = True
    receipt_worm_key: str = ""
    receipt_worm_version_id: str = ""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuditVerificationResult:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditSnapshotResult:
    snapshot_id: str
    tenant_id: str
    period_start_utc: str
    period_end_utc: str
    events_count: int
    merkle_root: str
    snapshot_hash: str
    worm_uri: str
    tsa_token_worm_key: str = ""
    indexed: bool = True
