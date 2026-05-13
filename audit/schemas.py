"""Typed schemas and validation helpers for audit evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .exceptions import AuditValidationError
from .hashing import is_sha256_hex


EVENT_VERSION = "audit-event-v1"
ENVELOPE_VERSION = "audit-envelope-v1"
RECEIPT_VERSION = "audit-worm-receipt-v1"
SNAPSHOT_VERSION = "audit-snapshot-v1"


class AuditKind(str, Enum):
    ACT_GENERATED = "ACT_GENERATED"
    PEC_SENT = "PEC_SENT"
    PEC_RECEIPT_ACQUIRED = "PEC_RECEIPT_ACQUIRED"
    DEPOSIT_ATTEMPT = "DEPOSIT_ATTEMPT"
    DEPOSIT_ACCEPTED = "DEPOSIT_ACCEPTED"
    DEPOSIT_FAILED = "DEPOSIT_FAILED"
    DOC_VIEWED = "DOC_VIEWED"
    DOC_DOWNLOADED = "DOC_DOWNLOADED"
    INCIDENT_OPENED = "INCIDENT_OPENED"
    INCIDENT_UPDATED = "INCIDENT_UPDATED"
    RECEIPT_ISSUED = "RECEIPT_ISSUED"


class ActorType(str, Enum):
    USER = "user"
    SYSTEM = "system"
    SERVICE = "service"


@dataclass(frozen=True)
class ActorContext:
    actor_id: str = ""
    actor_type: str = ActorType.SYSTEM.value
    display_name: str = ""
    display_name_hash: str = ""

    def validate(self) -> None:
        if self.actor_type not in {item.value for item in ActorType}:
            raise AuditValidationError("actor_type non valido.")
        if self.display_name_hash and not is_sha256_hex(self.display_name_hash):
            raise AuditValidationError("display_name_hash deve essere SHA-256 hex.")


@dataclass(frozen=True)
class SourceContext:
    service: str
    module: str
    request_id: str = ""
    idempotency_key: str = ""

    def validate(self) -> None:
        if not self.service.strip():
            raise AuditValidationError("source.service obbligatorio.")
        if not self.module.strip():
            raise AuditValidationError("source.module obbligatorio.")
        if not self.idempotency_key.strip():
            raise AuditValidationError("source.idempotency_key obbligatorio.")


@dataclass(frozen=True)
class AuditFileRef:
    label: str
    storage_ref: str
    sha256: str = ""
    size_bytes: int | None = None
    mime: str = ""
    path: str | Path | None = None
    trusted_hash: bool = False

    def validate(self) -> None:
        if not self.label.strip():
            raise AuditValidationError("files[].label obbligatorio.")
        if not self.storage_ref.strip():
            raise AuditValidationError("files[].storage_ref obbligatorio.")
        if self.sha256 and not is_sha256_hex(self.sha256):
            raise AuditValidationError("files[].sha256 deve essere SHA-256 hex.")
        if self.size_bytes is not None and int(self.size_bytes) < 0:
            raise AuditValidationError("files[].size_bytes non valido.")


@dataclass(frozen=True)
class AuditEventIndexRecord:
    event_id: str
    tenant_id: str
    fascicolo_id: str
    actor_id: str
    kind: str
    event_ts_utc: str
    event_hash: str
    prev_event_hash: str
    payload_hash: str
    files_hashes_jsonb: dict[str, Any] = field(default_factory=dict)
    signature_alg: str = ""
    signer_kid: str = ""
    signer_cert_fingerprint: str = ""
    worm_bucket: str = ""
    worm_key: str = ""
    worm_version_id: str = ""
    worm_retention_until: str = ""
    snapshot_id: str = ""
    idempotency_key: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class AuditSnapshotIndexRecord:
    snapshot_id: str
    tenant_id: str
    period_start_utc: str
    period_end_utc: str
    merkle_root: str
    events_count: int
    snapshot_hash: str
    signature_alg: str
    signer_kid: str
    tsa_token_worm_key: str = ""
    worm_bucket: str = ""
    worm_key: str = ""
    worm_version_id: str = ""
    created_at: str = ""
