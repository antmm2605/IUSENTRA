from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping


class PresidioStatus(StrEnum):
    DETECTED = "DETECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ORIGINAL_TO_ACQUIRE = "ORIGINAL_TO_ACQUIRE"
    ORIGINAL_ACQUIRED = "ORIGINAL_ACQUIRED"
    NOTIFICATION_CONFIRMED = "NOTIFICATION_CONFIRMED"
    RECIPIENTS_TO_VERIFY = "RECIPIENTS_TO_VERIFY"
    READY_FOR_RELATA = "READY_FOR_RELATA"
    RELATA_DRAFTED = "RELATA_DRAFTED"
    RELATA_SIGNED = "RELATA_SIGNED"
    READY_TO_SEND = "READY_TO_SEND"
    SENT_WAITING_RAC = "SENT_WAITING_RAC"
    RAC_RECEIVED = "RAC_RECEIVED"
    PARTIAL_DELIVERY = "PARTIAL_DELIVERY"
    DELIVERY_COMPLETE = "DELIVERY_COMPLETE"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    PROOF_TO_DEPOSIT = "PROOF_TO_DEPOSIT"
    PROOF_DEPOSITED = "PROOF_DEPOSITED"
    CLOSED = "CLOSED"
    NOT_REQUIRED = "NOT_REQUIRED"
    CANCELLED = "CANCELLED"
    LEGACY_ASSUMED_HANDLED = "LEGACY_ASSUMED_HANDLED"
    LEGACY_REVIEW_REQUIRED = "LEGACY_REVIEW_REQUIRED"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class DocumentRole(StrEnum):
    OFFICE_PEC_COPY = "office_pec_copy"
    PORTAL_ORIGINAL = "portal_original"
    NOTIFIED_ACT = "notified_act"
    RELATA = "relata"
    ATTESTATION = "attestation"
    SENT_PEC = "sent_pec"
    RAC = "rac"
    RDAC = "rdac"
    DELIVERY_FAILURE = "delivery_failure"
    PROOF_DEPOSIT_RECEIPT = "proof_deposit_receipt"


class ReceiptKind(StrEnum):
    SENT = "sent"
    RAC = "rac"
    RDAC = "rdac"
    FAILURE = "delivery_failure"
    PROOF_DEPOSIT = "proof_deposit_receipt"


class FailureAttribution(StrEnum):
    ATTRIBUTABLE_TO_RECIPIENT = "attributable_to_recipient"
    NOT_ATTRIBUTABLE_TO_RECIPIENT = "not_attributable_to_recipient"
    UNCERTAIN = "uncertain"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    DEAD = "dead"


TERMINAL_STATUSES = frozenset(
    {
        PresidioStatus.CLOSED,
        PresidioStatus.NOT_REQUIRED,
        PresidioStatus.CANCELLED,
    }
)

_EARLY_ACTIVE = frozenset(
    {
        PresidioStatus.NEEDS_REVIEW,
        PresidioStatus.ORIGINAL_TO_ACQUIRE,
        PresidioStatus.ORIGINAL_ACQUIRED,
        PresidioStatus.NOTIFICATION_CONFIRMED,
        PresidioStatus.RECIPIENTS_TO_VERIFY,
        PresidioStatus.READY_FOR_RELATA,
        PresidioStatus.SENT_WAITING_RAC,
        PresidioStatus.RAC_RECEIVED,
        PresidioStatus.PARTIAL_DELIVERY,
        PresidioStatus.DELIVERY_COMPLETE,
        PresidioStatus.DELIVERY_FAILED,
        PresidioStatus.PROOF_DEPOSITED,
        PresidioStatus.NOT_REQUIRED,
        PresidioStatus.CANCELLED,
        PresidioStatus.LEGACY_ASSUMED_HANDLED,
        PresidioStatus.LEGACY_REVIEW_REQUIRED,
    }
)

ALLOWED_TRANSITIONS: dict[PresidioStatus, frozenset[PresidioStatus]] = {
    PresidioStatus.DETECTED: _EARLY_ACTIVE,
    PresidioStatus.NEEDS_REVIEW: frozenset(
        {
            PresidioStatus.ORIGINAL_TO_ACQUIRE,
            PresidioStatus.ORIGINAL_ACQUIRED,
            PresidioStatus.NOTIFICATION_CONFIRMED,
            PresidioStatus.RECIPIENTS_TO_VERIFY,
            PresidioStatus.READY_FOR_RELATA,
            PresidioStatus.SENT_WAITING_RAC,
            PresidioStatus.RAC_RECEIVED,
            PresidioStatus.PARTIAL_DELIVERY,
            PresidioStatus.DELIVERY_COMPLETE,
            PresidioStatus.DELIVERY_FAILED,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.NOT_REQUIRED,
            PresidioStatus.CANCELLED,
            PresidioStatus.LEGACY_ASSUMED_HANDLED,
        }
    ),
    PresidioStatus.ORIGINAL_TO_ACQUIRE: frozenset(
        {
            PresidioStatus.ORIGINAL_ACQUIRED,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.NEEDS_REVIEW,
            PresidioStatus.NOT_REQUIRED,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.ORIGINAL_ACQUIRED: frozenset(
        {
            PresidioStatus.NOTIFICATION_CONFIRMED,
            PresidioStatus.RECIPIENTS_TO_VERIFY,
            PresidioStatus.READY_FOR_RELATA,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.NEEDS_REVIEW,
            PresidioStatus.NOT_REQUIRED,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.NOTIFICATION_CONFIRMED: frozenset(
        {
            PresidioStatus.RECIPIENTS_TO_VERIFY,
            PresidioStatus.READY_FOR_RELATA,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.NEEDS_REVIEW,
            PresidioStatus.NOT_REQUIRED,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.RECIPIENTS_TO_VERIFY: frozenset(
        {
            PresidioStatus.READY_FOR_RELATA,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.NEEDS_REVIEW,
            PresidioStatus.NOT_REQUIRED,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.READY_FOR_RELATA: frozenset(
        {
            PresidioStatus.RELATA_DRAFTED,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.NEEDS_REVIEW,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.RELATA_DRAFTED: frozenset(
        {
            PresidioStatus.RELATA_SIGNED,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.NEEDS_REVIEW,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.RELATA_SIGNED: frozenset(
        {
            PresidioStatus.READY_TO_SEND,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.NEEDS_REVIEW,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.READY_TO_SEND: frozenset(
        {
            PresidioStatus.SENT_WAITING_RAC,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.DELIVERY_FAILED,
            PresidioStatus.NEEDS_REVIEW,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.SENT_WAITING_RAC: frozenset(
        {
            PresidioStatus.RAC_RECEIVED,
            PresidioStatus.PARTIAL_DELIVERY,
            PresidioStatus.DELIVERY_COMPLETE,
            PresidioStatus.DELIVERY_FAILED,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.RAC_RECEIVED: frozenset(
        {
            PresidioStatus.PARTIAL_DELIVERY,
            PresidioStatus.DELIVERY_COMPLETE,
            PresidioStatus.DELIVERY_FAILED,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.PARTIAL_DELIVERY: frozenset(
        {
            PresidioStatus.DELIVERY_COMPLETE,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.DELIVERY_FAILED: frozenset(
        {
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.DELIVERY_COMPLETE: frozenset(
        {
            PresidioStatus.PROOF_TO_DEPOSIT,
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.CLOSED,
        }
    ),
    PresidioStatus.PROOF_TO_DEPOSIT: frozenset(
        {
            PresidioStatus.PROOF_DEPOSITED,
            PresidioStatus.NEEDS_REVIEW,
            PresidioStatus.CANCELLED,
        }
    ),
    PresidioStatus.PROOF_DEPOSITED: frozenset({PresidioStatus.CLOSED}),
    PresidioStatus.LEGACY_ASSUMED_HANDLED: frozenset(
        {PresidioStatus.LEGACY_REVIEW_REQUIRED, PresidioStatus.NEEDS_REVIEW}
    ),
    PresidioStatus.LEGACY_REVIEW_REQUIRED: _EARLY_ACTIVE,
    PresidioStatus.CLOSED: frozenset(),
    PresidioStatus.NOT_REQUIRED: frozenset(),
    PresidioStatus.CANCELLED: frozenset(),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = required_text(value, "timestamp")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Timestamp ISO non valido") from exc
    if parsed.tzinfo is None:
        raise ValueError("Timestamp privo di fuso orario")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_load(value: Any, *, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def sha256_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def required_text(value: Any, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} obbligatorio")
    return normalized


_EMAIL_IN_ERROR_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_WINDOWS_PATH_IN_ERROR_RE = re.compile(r"(?i)(?:[a-z]:\\|\\\\)[^\s\"']+")
_UNIX_PATH_IN_ERROR_RE = re.compile(r"(?<![\w])/(?:[^/\s]+/)+[^\s]*")
_SECRET_IN_ERROR_RE = re.compile(r"(?i)\b(password|token|secret|pin)\s*[:=]\s*\S+")


def sanitize_operational_error(value: Any) -> str:
    text = " ".join(str(value or "").split())
    text = _EMAIL_IN_ERROR_RE.sub("[indirizzo omesso]", text)
    text = _WINDOWS_PATH_IN_ERROR_RE.sub("[percorso omesso]", text)
    text = _UNIX_PATH_IN_ERROR_RE.sub("[percorso omesso]", text)
    text = _SECRET_IN_ERROR_RE.sub(lambda match: f"{match.group(1)}=[omesso]", text)
    return text[:500] or "Errore operativo non specificato"


def normalize_failure_attribution(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return FailureAttribution.UNCERTAIN.value
    try:
        return FailureAttribution(candidate).value
    except ValueError:
        return FailureAttribution.UNCERTAIN.value


def validate_transition(previous: str, next_status: str, *, reason: str = "") -> None:
    previous_value = PresidioStatus(previous)
    next_value = PresidioStatus(next_status)
    if next_value not in ALLOWED_TRANSITIONS.get(previous_value, frozenset()):
        raise ValueError(f"Transizione non ammessa: {previous_value} -> {next_value}")
    if (
        previous_value == PresidioStatus.NOTIFICATION_CONFIRMED
        and next_value in {PresidioStatus.NEEDS_REVIEW, PresidioStatus.NOT_REQUIRED}
        and len(str(reason).strip()) < 12
    ):
        raise ValueError("La correzione della decisione richiede una motivazione chiara di almeno 12 caratteri")
    if next_value in {PresidioStatus.NOT_REQUIRED, PresidioStatus.CANCELLED} and not str(reason).strip():
        raise ValueError(f"{next_value} richiede una motivazione")


@dataclass(frozen=True, slots=True)
class TransitionResult:
    transition_id: str
    previous_status: str
    next_status: str
    entry_hash: str
    inserted: bool


@dataclass(frozen=True, slots=True)
class PresidioProjection:
    id: str
    fascicolo_id: str
    status: str
    priority: str
    confidence: float
    human_review_required: bool
    trigger_type: str
    notification_case: str
    channel: str
    assigned_user_id: str
    legacy_assumed_handled: bool
    proof_deposit_required: bool
    resolution_code: str
    source_effective_at: str
    explicit_due_at: str
    created_at: str
    updated_at: str
    recipients_total: int
    recipients_sent: int
    recipients_rac: int
    recipients_delivered: int
    recipients_failed: int

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "PresidioProjection":
        return cls(
            id=str(row.get("id") or ""),
            fascicolo_id=str(row.get("fascicolo_id") or ""),
            status=str(row.get("status") or ""),
            priority=str(row.get("priority") or ""),
            confidence=float(row.get("confidence") or 0.0),
            human_review_required=bool(row.get("human_review_required")),
            trigger_type=str(row.get("trigger_type") or ""),
            notification_case=str(row.get("notification_case") or ""),
            channel=str(row.get("channel") or ""),
            assigned_user_id=str(row.get("assigned_user_id") or ""),
            legacy_assumed_handled=bool(row.get("legacy_assumed_handled")),
            proof_deposit_required=bool(row.get("proof_deposit_required")),
            resolution_code=str(row.get("resolution_code") or ""),
            source_effective_at=(
                canonical_timestamp(row["source_effective_at"])
                if row.get("source_effective_at") else ""
            ),
            explicit_due_at=(
                canonical_timestamp(row["explicit_due_at"])
                if row.get("explicit_due_at") else ""
            ),
            created_at=canonical_timestamp(row["created_at"]),
            updated_at=canonical_timestamp(row["updated_at"]),
            recipients_total=int(row.get("recipients_total") or 0),
            recipients_sent=int(row.get("recipients_sent") or 0),
            recipients_rac=int(row.get("recipients_rac") or 0),
            recipients_delivered=int(row.get("recipients_delivered") or 0),
            recipients_failed=int(row.get("recipients_failed") or 0),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fascicoloId": self.fascicolo_id,
            "status": self.status,
            "priority": self.priority,
            "confidence": self.confidence,
            "humanReviewRequired": self.human_review_required,
            "triggerType": self.trigger_type,
            "notificationCase": self.notification_case,
            "channel": self.channel,
            "assignedUserId": self.assigned_user_id,
            "legacyAssumedHandled": self.legacy_assumed_handled,
            "proofDepositRequired": self.proof_deposit_required,
            "resolutionCode": self.resolution_code,
            "sourceEffectiveAt": self.source_effective_at,
            "explicitDueAt": self.explicit_due_at,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "recipientProgress": {
                "total": self.recipients_total,
                "sent": self.recipients_sent,
                "rac": self.recipients_rac,
                "delivered": self.recipients_delivered,
                "failed": self.recipients_failed,
            },
        }


@dataclass(frozen=True, slots=True)
class ProjectionPage:
    items: tuple[PresidioProjection, ...]
    next_cursor: tuple[str, str] | None

    def to_public_dict(self) -> dict[str, Any]:
        cursor = None
        if self.next_cursor is not None:
            cursor = {"updatedAt": self.next_cursor[0], "id": self.next_cursor[1]}
        return {"items": [item.to_public_dict() for item in self.items], "nextCursor": cursor}
