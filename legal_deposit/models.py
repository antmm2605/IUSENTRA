from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DepositState(StrEnum):
    DRAFT = "DRAFT"
    DOCUMENTS_LOADED = "DOCUMENTS_LOADED"
    PRECHECK_RUNNING = "PRECHECK_RUNNING"
    PRECHECK_FAILED = "PRECHECK_FAILED"
    PRECHECK_PASSED = "PRECHECK_PASSED"
    PACKAGE_READY = "PACKAGE_READY"
    AWAITING_USER_CONFIRMATION = "AWAITING_USER_CONFIRMATION"
    SIGNING_REQUESTED = "SIGNING_REQUESTED"
    SIGNED = "SIGNED"
    SENDING = "SENDING"
    SENT = "SENT"
    RECEIPT_ACCEPTED = "RECEIPT_ACCEPTED"
    RECEIPT_DELIVERED = "RECEIPT_DELIVERED"
    DEPOSIT_CONFIRMED = "DEPOSIT_CONFIRMED"
    REJECTED = "REJECTED"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    RESUBMIT_READY = "RESUBMIT_READY"
    ARCHIVED = "ARCHIVED"


class PreflightStatus(StrEnum):
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(slots=True)
class PreflightResult:
    status: PreflightStatus
    code: str
    message: str
    detail: str = ""
    suggested_fix: str = ""
    auto_fix_available: bool = False
    manual_review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "suggested_fix": self.suggested_fix,
            "auto_fix_available": self.auto_fix_available,
            "manual_review_required": self.manual_review_required,
        }


@dataclass(slots=True)
class DepositDocument:
    path: str
    document_id: str = ""
    role: str = "main_act"
    filename: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    sha256: str = ""
    signed: bool = False
    signature_format: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DepositTransition:
    status_before: str
    status_after: str
    user_id: str = ""
    reason: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DepositPreparation:
    job_id: str
    status: DepositState
    channel: str
    documents: list[DepositDocument]
    preflight: list[PreflightResult]
    manifest: dict[str, Any]
    summary: dict[str, Any]
    transitions: list[DepositTransition] = field(default_factory=list)

    @property
    def blocking_errors(self) -> list[PreflightResult]:
        return [item for item in self.preflight if item.status == PreflightStatus.ERROR]

    @property
    def warnings(self) -> list[PreflightResult]:
        return [item for item in self.preflight if item.status == PreflightStatus.WARNING]
