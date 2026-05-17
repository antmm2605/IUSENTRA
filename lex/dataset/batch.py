"""Batch governato per costruire dataset Lex da documenti autorizzati."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .chunking import ChunkingOptions
from .export import export_qa_pairs
from .models import (
    DatasetFileType,
    DatasetFormat,
    DatasetPipelineResult,
    DocumentPage,
    QAPair,
    StudioDatasetDocument,
    clean_text,
    sanitize_source_name,
)
from .pipeline import build_studio_dataset_pipeline
from .privacy import classify_privacy
from .qa import QAGenerationPolicy


DATASET_EXPORT_FORMATS: tuple[DatasetFormat, ...] = ("alpaca", "sharegpt", "multilingual")


@dataclass(frozen=True, slots=True)
class StudioDatasetBatchOptions:
    tenant_id: str
    fascicolo_ids: tuple[str, ...] = ()
    max_documents: int | None = None
    dry_run: bool = True
    allow_sensitive_export: bool = False
    include_pending_review_export: bool = False
    dataset_formats: tuple[DatasetFormat, ...] = DATASET_EXPORT_FORMATS
    file_type: DatasetFileType = "jsonl"
    chunking_options: ChunkingOptions = field(default_factory=ChunkingOptions)
    qa_policy: QAGenerationPolicy = field(default_factory=QAGenerationPolicy)

    def __post_init__(self) -> None:
        tenant = clean_text(self.tenant_id)
        if not tenant:
            raise ValueError("tenant_id obbligatorio per il batch dataset Lex.")
        formats = tuple(self.dataset_formats or DATASET_EXPORT_FORMATS)
        invalid = [fmt for fmt in formats if fmt not in DATASET_EXPORT_FORMATS]
        if invalid:
            raise ValueError(f"Formati dataset non supportati: {', '.join(invalid)}.")
        if self.file_type not in {"jsonl", "json", "csv"}:
            raise ValueError(f"Tipo file dataset non supportato: {self.file_type!r}.")
        if self.max_documents is not None and self.max_documents < 1:
            raise ValueError("max_documents deve essere positivo.")
        object.__setattr__(self, "tenant_id", tenant)
        object.__setattr__(self, "fascicolo_ids", tuple(clean_text(item) for item in self.fascicolo_ids if clean_text(item)))
        object.__setattr__(self, "dataset_formats", formats)


@dataclass(frozen=True, slots=True)
class StudioDatasetBatchResult:
    pipeline: DatasetPipelineResult
    documents_count: int
    sensitive_documents_count: int
    sensitive_chunks_count: int
    output_files: tuple[str, ...] = ()
    dry_run: bool = True
    blocked_exports: tuple[str, ...] = ()

    def summary(self) -> dict[str, Any]:
        return {
            "tenant_id": self.pipeline.manifest.tenant_id,
            "manifest_id": self.pipeline.manifest.manifest_id,
            "documents_count": self.documents_count,
            "chunks_count": len(self.pipeline.chunks),
            "qa_tasks_count": len(self.pipeline.qa_tasks),
            "qa_pairs_count": len(self.pipeline.qa_pairs),
            "sensitive_documents_count": self.sensitive_documents_count,
            "sensitive_chunks_count": self.sensitive_chunks_count,
            "dry_run": self.dry_run,
            "output_files": list(self.output_files),
            "blocked_exports": list(self.blocked_exports),
            "automatic_training": False,
            "external_training": False,
            "human_review_required": True,
        }


def load_document_ai_json_documents(
    document_ai_json_path: str | Path,
    *,
    tenant_id: str,
    fascicolo_ids: Iterable[str] | None = None,
    max_documents: int | None = None,
) -> list[StudioDatasetDocument]:
    """Carica solo testi gia' estratti da Documenti AI Fascicolo."""
    tenant = clean_text(tenant_id)
    if not tenant:
        raise ValueError("tenant_id obbligatorio per leggere i documenti studio Lex.")
    path = Path(document_ai_json_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivio Documenti AI non trovato: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Archivio Documenti AI non valido.")

    allowed_fascicoli = {clean_text(item) for item in (fascicolo_ids or []) if clean_text(item)}
    document_rows = [row for row in raw.get("documents", []) if isinstance(row, dict)]
    text_rows = [row for row in raw.get("texts", []) if isinstance(row, dict)]
    by_document = {
        clean_text(row.get("id")): row
        for row in document_rows
        if clean_text(row.get("tenant_id")) == tenant
        and (not allowed_fascicoli or clean_text(row.get("fascicolo_id")) in allowed_fascicoli)
    }

    documents: list[StudioDatasetDocument] = []
    for text_row in text_rows:
        if clean_text(text_row.get("tenant_id")) != tenant:
            continue
        fascicolo_id = clean_text(text_row.get("fascicolo_id"))
        if allowed_fascicoli and fascicolo_id not in allowed_fascicoli:
            continue
        document_id = clean_text(text_row.get("document_id"))
        source = by_document.get(document_id)
        if not source:
            continue
        text = str(text_row.get("text") or "")
        if not text.strip():
            continue
        documents.append(_document_from_ai_rows(tenant, fascicolo_id, source, text_row))
        if max_documents is not None and len(documents) >= max_documents:
            break
    return documents


def build_studio_dataset_batch(
    documents: Iterable[StudioDatasetDocument],
    options: StudioDatasetBatchOptions,
    *,
    output_dir: str | Path | None = None,
) -> StudioDatasetBatchResult:
    document_rows = tuple(documents)
    pipeline = build_studio_dataset_pipeline(
        options.tenant_id,
        document_rows,
        chunking_options=options.chunking_options,
        qa_policy=options.qa_policy,
    )
    sensitive_documents = sum(
        1
        for row in pipeline.manifest.documents
        if row.privacy_classification in {"sensitive", "highly_sensitive"}
    )
    sensitive_chunks = sum(
        1
        for chunk in pipeline.chunks
        if chunk.privacy_classification in {"sensitive", "highly_sensitive"}
    )
    if options.dry_run or output_dir is None:
        return StudioDatasetBatchResult(
            pipeline=pipeline,
            documents_count=len(document_rows),
            sensitive_documents_count=sensitive_documents,
            sensitive_chunks_count=sensitive_chunks,
            dry_run=True,
        )

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    output_files = [str(_write_json(target / "manifest.json", pipeline.manifest.to_dict()))]
    blocked: list[str] = []
    if sensitive_chunks and not options.allow_sensitive_export:
        blocked.append(
            "Chunk, Q&A ed export non scritti: il batch contiene dati sensibili e manca allow_sensitive_export."
        )
    else:
        output_files.extend(
            [
                str(_write_jsonl(target / "chunks.jsonl", [chunk.to_dict(include_text=True) for chunk in pipeline.chunks])),
                str(_write_jsonl(target / "qa_tasks.jsonl", [task.to_dict() for task in pipeline.qa_tasks])),
                str(_write_json(target / "qa_review_queue.json", [pair.to_dict() for pair in pipeline.qa_pairs])),
            ]
        )
        for dataset_format in options.dataset_formats:
            payload = export_qa_pairs(
                pipeline.qa_pairs,
                dataset_format=dataset_format,
                file_type=options.file_type,
                include_pending_review=options.include_pending_review_export,
                allow_sensitive=options.allow_sensitive_export,
                external_training=False,
            )
            suffix = options.file_type
            output_files.append(str(_write_text(target / f"{dataset_format}.{suffix}", payload)))

    return StudioDatasetBatchResult(
        pipeline=pipeline,
        documents_count=len(document_rows),
        sensitive_documents_count=sensitive_documents,
        sensitive_chunks_count=sensitive_chunks,
        output_files=tuple(output_files),
        dry_run=False,
        blocked_exports=tuple(blocked),
    )


def _document_from_ai_rows(
    tenant_id: str,
    fascicolo_id: str,
    source: dict[str, Any],
    text_row: dict[str, Any],
) -> StudioDatasetDocument:
    pages = tuple(_pages_from_payload(text_row.get("pages")))
    raw_title = clean_text(source.get("original_filename") or source.get("safe_filename") or text_row.get("document_id"))
    title = sanitize_source_name(raw_title) or raw_title
    return StudioDatasetDocument(
        tenant_id=tenant_id,
        document_id=clean_text(text_row.get("document_id")),
        title=title,
        text=str(text_row.get("text") or ""),
        source_name=title,
        mime_type=clean_text(source.get("mime_type")) or "application/octet-stream",
        source_kind="documenti_ai_fascicolo",
        fascicolo_id=fascicolo_id,
        sha256=clean_text(source.get("sha256")),
        pages=pages,
        metadata={
            "document_ai_version_id": clean_text(text_row.get("version_id")),
            "extraction_engine": clean_text(text_row.get("extraction_engine")),
            "status": clean_text(source.get("status")),
            "privacy_classification": classify_privacy(text_row.get("text")),
        },
    )


def _pages_from_payload(payload: Any) -> list[DocumentPage]:
    if not isinstance(payload, list):
        return []
    pages: list[DocumentPage] = []
    for index, row in enumerate(payload, start=1):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "")
        if not text.strip():
            continue
        page_number = row.get("page_number") or index
        pages.append(DocumentPage(page_number=int(page_number), text=text))
    return pages


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    payload = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    return _write_text(path, payload)


def _write_text(path: Path, payload: str) -> Path:
    path.write_text(payload, encoding="utf-8")
    return path


def qa_pairs_from_dicts(rows: Iterable[dict[str, Any]]) -> list[QAPair]:
    """Ricostruisce Q&A serializzate per futuri tool di revisione/import."""
    from .models import SourceMetadata

    pairs: list[QAPair] = []
    for row in rows:
        payload = dict(row or {})
        source_payload = payload.pop("source", {}) or {}
        payload["source"] = SourceMetadata(**source_payload)
        pairs.append(QAPair(**payload))
    return pairs
