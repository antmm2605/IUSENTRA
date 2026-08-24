"""Modelli del dominio Documenti AI Fascicolo."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import uuid4


DOCUMENT_AI_STATUSES = ("uploaded", "processing", "ready", "error", "archived")
DOCUMENT_AI_INDEX_STATUSES = (
    "not_indexed",
    "queued",
    "indexing",
    "ready",
    "error",
    "stale",
    "archived",
)
DOCUMENT_AI_SOURCES = (
    "upload",
    "generated",
    "assistant_edit",
    "user_accept",
    "user_reject",
    "import",
)
DOCUMENT_CATALOG_ASSIGNMENT_STATUSES = (
    "proposed",
    "confirmed",
    "review_required",
    "superseded",
    "rejected",
)
DOCUMENT_CATALOG_JOB_STATUSES = ("queued", "processing", "completed", "review_required", "error")
DOCUMENT_CATALOG_SOURCE_STATES = (
    "verified_snapshot",
    "manual_browser_evidence",
    "manual_override",
    "review_required",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    clean = str(prefix or "docai").strip().lower().replace("_", "-")
    return f"{clean}-{uuid4().hex}"


T = TypeVar("T")


def dataclass_from_dict(cls: type[T], payload: dict[str, Any]) -> T:
    allowed = set(getattr(cls, "__dataclass_fields__", {}).keys())
    return cls(**{key: value for key, value in dict(payload or {}).items() if key in allowed})  # type: ignore[arg-type]


@dataclass(slots=True)
class SerializableDataclass:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DocumentAIRecord(SerializableDataclass):
    id: str
    tenant_id: str
    fascicolo_id: str
    original_filename: str
    safe_filename: str
    file_type: str
    mime_type: str | None
    size_bytes: int
    sha256: str
    status: str
    current_version_id: str | None
    page_count: int | None
    created_by: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class DocumentAIVersion(SerializableDataclass):
    id: str
    tenant_id: str
    fascicolo_id: str
    document_id: str
    version_number: int
    source: str
    storage_path: str
    extracted_text_path: str | None
    pdf_preview_path: str | None
    sha256: str
    created_by: str
    created_at: str


@dataclass(slots=True)
class DocumentAIPageText(SerializableDataclass):
    page_number: int | None
    text: str


@dataclass(slots=True)
class DocumentAIText(SerializableDataclass):
    document_id: str
    version_id: str
    tenant_id: str
    fascicolo_id: str
    text: str
    pages: list[DocumentAIPageText]
    extraction_engine: str
    created_at: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pages"] = [page.to_dict() for page in self.pages]
        return payload


@dataclass(slots=True)
class DocumentAISearchResult(SerializableDataclass):
    document_id: str
    version_id: str
    page_number: int | None
    snippet: str
    start_offset: int | None
    end_offset: int | None


@dataclass(slots=True)
class DocumentAICitation(SerializableDataclass):
    document_id: str
    version_id: str
    page_number: int | None
    quote: str
    sha256: str


@dataclass(slots=True)
class DocumentAIUploadResult(SerializableDataclass):
    document: DocumentAIRecord
    version: DocumentAIVersion
    text: DocumentAIText | None
    extraction_status: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": self.document.to_dict(),
            "version": self.version.to_dict(),
            "text": self.text.to_dict() if self.text else None,
            "extraction_status": self.extraction_status,
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class LexIndexingSummary(SerializableDataclass):
    total_documents: int
    ready: int
    queued: int
    indexing: int
    errors: int
    stale: int
    last_indexed_at: str | None
    status: str
    not_indexed: int = 0
    archived: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DocumentCatalogAssignment(SerializableDataclass):
    id: str
    tenant_id: str
    fascicolo_id: str
    document_id: str
    document_ai_id: str | None
    document_version_id: str | None
    document_sha256: str
    profile_id: str | None
    legal_area: str | None
    legal_branch: str | None
    legal_subfamily: str | None
    jurisdiction: str | None
    rite: str | None
    proceeding_phase: str | None
    document_nature: str
    document_label: str
    document_section: str
    deposit_role: str
    deposit_candidate: bool
    status: str
    confidence: int
    source_state: str
    resolver_version: str
    rule_set_id: str | None
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_by: str = ""
    created_at: str = ""
    updated_by: str = ""
    updated_at: str = ""
    confirmed_at: str | None = None


@dataclass(slots=True)
class DocumentCatalogCandidate(SerializableDataclass):
    id: str
    tenant_id: str
    fascicolo_id: str
    assignment_id: str
    rank_number: int
    profile_id: str | None
    document_nature: str
    document_label: str
    document_section: str
    deposit_role: str
    confidence: int
    reason: str
    created_at: str


@dataclass(slots=True)
class DocumentCatalogEvidence(SerializableDataclass):
    id: str
    tenant_id: str
    fascicolo_id: str
    assignment_id: str
    evidence_type: str
    locator: str
    excerpt: str
    weight: int
    content_sha256: str | None
    created_at: str


@dataclass(slots=True)
class DocumentCatalogReview(SerializableDataclass):
    id: str
    tenant_id: str
    fascicolo_id: str
    assignment_id: str
    state: str
    reason_code: str
    reason: str
    resolved_by: str | None
    resolution_note: str | None
    created_at: str
    resolved_at: str | None
