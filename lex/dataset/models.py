"""Modelli puri per dataset Lex basati su documenti dello studio."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, replace
from pathlib import PurePath, PureWindowsPath
from typing import Any, Literal


DatasetFormat = Literal["alpaca", "sharegpt", "multilingual"]
DatasetFileType = Literal["jsonl", "json", "csv"]
DatasetKind = Literal["single_turn_qa", "multi_turn_dialogue", "eval"]
PrivacyClassification = Literal["public", "studio_internal", "sensitive", "highly_sensitive"]
ReviewStatus = Literal["pending_human_review", "approved", "rejected"]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\r\n", "\n").replace("\r", "\n").split()).strip()


def stable_id(*parts: Any, prefix: str = "") -> str:
    raw = "\n".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}{digest}" if prefix else digest


def sanitize_source_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "\\" in raw or ":" in raw:
        return PureWindowsPath(raw).name
    return PurePath(raw).name


def compact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != "" and value != [] and value != {}
    }


@dataclass(frozen=True, slots=True)
class DocumentPage:
    page_number: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "page_number", max(1, int(self.page_number or 1)))
        object.__setattr__(self, "text", str(self.text or ""))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StudioDatasetDocument:
    tenant_id: str
    document_id: str
    title: str
    text: str = ""
    source_name: str = ""
    mime_type: str = "text/plain"
    source_kind: str = "studio_document"
    fascicolo_id: str = ""
    sha256: str = ""
    pages: tuple[DocumentPage, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        tenant_id = clean_text(self.tenant_id)
        document_id = clean_text(self.document_id)
        title = clean_text(self.title) or document_id or "Documento studio"
        if not tenant_id:
            raise ValueError("tenant_id obbligatorio per il documento dataset Lex.")
        if not document_id:
            raise ValueError("document_id obbligatorio per il documento dataset Lex.")
        pages = tuple(page if isinstance(page, DocumentPage) else DocumentPage(**dict(page)) for page in self.pages)
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "document_id", document_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "text", str(self.text or ""))
        object.__setattr__(self, "source_name", sanitize_source_name(self.source_name or title))
        object.__setattr__(self, "mime_type", clean_text(self.mime_type) or "text/plain")
        object.__setattr__(self, "source_kind", clean_text(self.source_kind) or "studio_document")
        object.__setattr__(self, "fascicolo_id", clean_text(self.fascicolo_id))
        object.__setattr__(self, "sha256", clean_text(self.sha256))
        object.__setattr__(self, "pages", pages)
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def all_text(self) -> str:
        page_text = "\n\n".join(page.text for page in self.pages if page.text)
        return page_text or self.text

    def to_source_metadata(self) -> "SourceMetadata":
        return SourceMetadata(
            tenant_id=self.tenant_id,
            document_id=self.document_id,
            title=self.title,
            source_name=self.source_name,
            source_kind=self.source_kind,
            fascicolo_id=self.fascicolo_id,
            sha256=self.sha256,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pages"] = [page.to_dict() for page in self.pages]
        return payload


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    tenant_id: str
    document_id: str
    title: str
    source_name: str = ""
    source_kind: str = "studio_document"
    fascicolo_id: str = ""
    sha256: str = ""
    page_start: int | None = None
    page_end: int | None = None
    chunk_id: str = ""
    chunk_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", clean_text(self.tenant_id))
        object.__setattr__(self, "document_id", clean_text(self.document_id))
        object.__setattr__(self, "title", clean_text(self.title) or "Documento studio")
        object.__setattr__(self, "source_name", sanitize_source_name(self.source_name or self.title))
        object.__setattr__(self, "source_kind", clean_text(self.source_kind) or "studio_document")
        object.__setattr__(self, "fascicolo_id", clean_text(self.fascicolo_id))
        object.__setattr__(self, "sha256", clean_text(self.sha256))
        object.__setattr__(self, "chunk_id", clean_text(self.chunk_id))
        object.__setattr__(self, "chunk_index", int(self.chunk_index or 0))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def with_chunk(self, *, chunk_id: str, chunk_index: int, page_start: int | None, page_end: int | None) -> "SourceMetadata":
        return replace(
            self,
            chunk_id=chunk_id,
            chunk_index=chunk_index,
            page_start=page_start,
            page_end=page_end,
        )

    def to_dict(self) -> dict[str, Any]:
        return compact_dict(asdict(self))


@dataclass(frozen=True, slots=True)
class IngestionManifestDocument:
    tenant_id: str
    document_id: str
    title: str
    source_name: str
    source_kind: str
    mime_type: str
    fascicolo_id: str = ""
    sha256: str = ""
    page_count: int = 0
    text_chars: int = 0
    privacy_classification: PrivacyClassification = "studio_internal"
    rag_use: str = "rag_immediate"
    fine_tuning_use: str = "supervised_candidate_requires_review"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return compact_dict(asdict(self))


@dataclass(frozen=True, slots=True)
class IngestionManifest:
    tenant_id: str
    manifest_id: str
    created_at: str
    documents: tuple[IngestionManifestDocument, ...]
    storage_scope: str
    rag_policy: dict[str, Any] = field(default_factory=dict)
    fine_tuning_policy: dict[str, Any] = field(default_factory=dict)
    privacy_policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["documents"] = [document.to_dict() for document in self.documents]
        return payload


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    chunk_id: str
    tenant_id: str
    document_id: str
    chunk_index: int
    text: str
    source: SourceMetadata
    token_estimate: int = 0
    rag_ready: bool = True
    fine_tuning_candidate: bool = True
    privacy_classification: PrivacyClassification = "studio_internal"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        text = str(self.text or "").strip()
        token_estimate = self.token_estimate or max(1, len(text.split()))
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "token_estimate", int(token_estimate))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = self.source.to_dict()
        if not include_text:
            payload.pop("text", None)
        return compact_dict(payload)


@dataclass(frozen=True, slots=True)
class QAGenerationTask:
    task_id: str
    chunk_id: str
    tenant_id: str
    document_id: str
    chunk_text: str
    source: SourceMetadata
    instructions: tuple[str, ...]
    max_pairs: int = 1
    requires_human_review: bool = True
    privacy_classification: PrivacyClassification = "studio_internal"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = self.source.to_dict()
        return compact_dict(payload)


@dataclass(frozen=True, slots=True)
class QAPair:
    qa_id: str
    question: str
    answer: str
    tenant_id: str
    document_id: str
    chunk_id: str
    source: SourceMetadata
    dataset_kind: DatasetKind = "single_turn_qa"
    intended_use: str = "supervised_fine_tuning_candidate"
    review_status: ReviewStatus = "pending_human_review"
    requires_human_review: bool = True
    privacy_classification: PrivacyClassification = "studio_internal"
    reviewer_id: str = ""
    review_note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = self.source.to_dict()
        return compact_dict(payload)

    def reviewed(self, *, approved: bool, reviewer_id: str = "", note: str = "") -> "QAPair":
        return replace(
            self,
            review_status="approved" if approved else "rejected",
            reviewer_id=clean_text(reviewer_id),
            review_note=clean_text(note),
            requires_human_review=False if approved else True,
        )


@dataclass(frozen=True, slots=True)
class DatasetPipelineResult:
    manifest: IngestionManifest
    chunks: tuple[DocumentChunk, ...]
    qa_tasks: tuple[QAGenerationTask, ...]
    qa_pairs: tuple[QAPair, ...]

    def to_dict(self, *, include_chunk_text: bool = False) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "chunks": [chunk.to_dict(include_text=include_chunk_text) for chunk in self.chunks],
            "qa_tasks": [task.to_dict() for task in self.qa_tasks],
            "qa_pairs": [pair.to_dict() for pair in self.qa_pairs],
        }
