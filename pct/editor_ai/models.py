"""Modelli del dominio Editor AI.

Il dominio non sostituisce l'editor professionale IUSENTRA: conserva solo
metadati, versioni, fonti e proposte AI collegate al documento reale del
fascicolo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import uuid4


ATTO_AI_STATUSES = ("draft", "in_review", "approved", "exported", "archived")
ATTO_AI_EDIT_STATUSES = ("pending", "accepted", "rejected", "superseded")
ATTO_AI_VERSION_SOURCES = ("ai_generation", "ai_edit", "manual_edit", "export")
ATTO_AI_EDIT_OPERATIONS = (
    "replace",
    "insert_after",
    "insert_before",
    "delete",
    "rewrite_section",
    "add_section",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    clean = str(prefix or "attoai").strip().lower().replace("_", "-")
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
class AttoAIDraftRequest(SerializableDataclass):
    tenant_id: str
    fascicolo_id: str
    tipo_atto: str
    template_id: str
    istruzioni_utente: str
    document_ids: list[str] = field(default_factory=list)
    use_fascicolo_context: bool = True
    language: str = "it"


@dataclass(slots=True)
class AttoAIRecord(SerializableDataclass):
    id: str
    tenant_id: str
    fascicolo_id: str
    tipo_atto: str
    template_id: str
    title: str
    status: str
    editor_document_id: str
    current_version_id: str | None
    created_by: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class AttoAIVersion(SerializableDataclass):
    id: str
    atto_ai_id: str
    tenant_id: str
    fascicolo_id: str
    version_number: int
    source: str
    editor_document_snapshot: dict[str, Any]
    docx_path: str | None
    pdf_path: str | None
    created_by: str
    created_at: str


@dataclass(slots=True)
class AttoAISource(SerializableDataclass):
    id: str
    atto_ai_id: str
    source_type: str
    source_id: str
    document_id: str | None
    page_number: int | None
    quote: str
    sha256: str
    reason: str


@dataclass(slots=True)
class AttoAIEditProposal(SerializableDataclass):
    id: str
    atto_ai_id: str
    version_id: str
    status: str
    operation_type: str
    target_block_id: str | None
    find_text: str | None
    replace_text: str | None
    insert_text: str | None
    reason: str
    created_by: str
    created_at: str
    resolved_by: str | None = None
    resolved_at: str | None = None


@dataclass(slots=True)
class AttoDraftSection(SerializableDataclass):
    id: str
    heading: str
    level: int
    purpose: str
    source_refs: list[str] = field(default_factory=list)
    required: bool = True


@dataclass(slots=True)
class AttoDraftPlan(SerializableDataclass):
    title: str
    tipo_atto: str
    template_id: str
    sections: list[AttoDraftSection]
    required_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    sources_to_use: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sections"] = [section.to_dict() for section in self.sections]
        return payload


@dataclass(slots=True)
class AttoAIGenerationResult(SerializableDataclass):
    record: AttoAIRecord
    version: AttoAIVersion
    sources: list[AttoAISource]
    plan: AttoDraftPlan
    open_url: str
    readback: dict[str, Any]
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "atto_ai": self.record.to_dict(),
            "version": self.version.to_dict(),
            "sources": [source.to_dict() for source in self.sources],
            "plan": self.plan.to_dict(),
            "open_url": self.open_url,
            "readback": dict(self.readback),
            "missing_fields": list(self.missing_fields),
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class AttoAIExportResult(SerializableDataclass):
    atto_ai_id: str
    editor_document_id: str
    format: str
    download_url: str
    version_id: str | None = None


@dataclass(slots=True)
class FascicoloEditorAIContext(SerializableDataclass):
    tenant_id: str
    fascicolo_id: str
    facts: dict[str, Any]
    documents: list[dict[str, Any]] = field(default_factory=list)
    activities: list[dict[str, Any]] = field(default_factory=list)
    deadlines: list[dict[str, Any]] = field(default_factory=list)
    communications: list[dict[str, Any]] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
