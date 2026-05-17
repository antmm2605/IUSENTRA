"""Chunking puro per documenti studio, testi e PDF già estratti."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .models import DocumentChunk, StudioDatasetDocument, stable_id
from .privacy import classify_privacy


DocumentTextExtractor = Callable[[StudioDatasetDocument], str]


@dataclass(frozen=True, slots=True)
class ChunkingOptions:
    max_chars: int = 1200
    overlap_chars: int = 120
    min_chars: int = 40

    def __post_init__(self) -> None:
        if self.max_chars < 120:
            raise ValueError("max_chars deve essere almeno 120.")
        if self.overlap_chars < 0:
            raise ValueError("overlap_chars non può essere negativo.")
        if self.overlap_chars >= self.max_chars:
            raise ValueError("overlap_chars deve essere minore di max_chars.")
        if self.min_chars < 0:
            raise ValueError("min_chars non può essere negativo.")


def _normalize_chunk_text(text: str) -> str:
    return "\n\n".join(" ".join(part.split()) for part in str(text or "").split("\n\n") if part.strip()).strip()


def _split_long_token(token: str, options: ChunkingOptions) -> list[str]:
    if len(token) <= options.max_chars:
        return [token]
    step = max(1, options.max_chars - options.overlap_chars)
    return [token[index : index + options.max_chars] for index in range(0, len(token), step)]


def chunk_plain_text(text: str, options: ChunkingOptions | None = None) -> list[str]:
    opts = options or ChunkingOptions()
    normalized = _normalize_chunk_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    current = ""
    for token in normalized.split():
        for part in _split_long_token(token, opts):
            candidate = f"{current} {part}".strip() if current else part
            if len(candidate) <= opts.max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
                carry = current[-opts.overlap_chars :].strip() if opts.overlap_chars else ""
                current = f"{carry} {part}".strip() if carry else part
            else:
                chunks.append(part[: opts.max_chars])
                current = part[opts.max_chars :]
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if len(chunk.strip()) >= opts.min_chars] or ([normalized] if normalized else [])


def _document_text_units(
    document: StudioDatasetDocument,
    *,
    text_extractor: DocumentTextExtractor | None = None,
) -> list[tuple[str, int | None, int | None]]:
    if document.pages:
        return [(page.text, page.page_number, page.page_number) for page in document.pages if page.text.strip()]
    text = document.text
    if not text.strip() and text_extractor is not None:
        text = text_extractor(document)
    return [(text, None, None)] if str(text or "").strip() else []


def chunk_document(
    document: StudioDatasetDocument,
    *,
    options: ChunkingOptions | None = None,
    text_extractor: DocumentTextExtractor | None = None,
) -> list[DocumentChunk]:
    opts = options or ChunkingOptions()
    chunks: list[DocumentChunk] = []
    base_source = document.to_source_metadata()
    for unit_text, page_start, page_end in _document_text_units(document, text_extractor=text_extractor):
        for text in chunk_plain_text(unit_text, opts):
            chunk_index = len(chunks) + 1
            chunk_id = stable_id(document.tenant_id, document.document_id, chunk_index, page_start, text, prefix="lex-chunk-")
            source = base_source.with_chunk(
                chunk_id=chunk_id,
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
            )
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    tenant_id=document.tenant_id,
                    document_id=document.document_id,
                    chunk_index=chunk_index,
                    text=text,
                    source=source,
                    privacy_classification=classify_privacy(text),
                    metadata={
                        "rag_use": "retrieval_immediato_tenant_aware",
                        "fine_tuning_use": "candidato_supervisionato",
                        "source_mime_type": document.mime_type,
                    },
                )
            )
    return chunks


def chunk_documents(
    documents: Iterable[StudioDatasetDocument],
    *,
    options: ChunkingOptions | None = None,
    text_extractor: DocumentTextExtractor | None = None,
) -> list[DocumentChunk]:
    rows: list[DocumentChunk] = []
    for document in documents:
        rows.extend(chunk_document(document, options=options, text_extractor=text_extractor))
    return rows
