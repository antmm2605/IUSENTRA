"""Modelli del dominio Documenti AI Fascicolo."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import uuid4


DOCUMENT_AI_STATUSES = ("uploaded", "processing", "ready", "error", "archived")
DOCUMENT_AI_SOURCES = (
    "upload",
    "generated",
    "assistant_edit",
    "user_accept",
    "user_reject",
    "import",
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
    page_number: int
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
