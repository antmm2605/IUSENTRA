"""Orchestrazione pura della pipeline dataset Lex."""

from __future__ import annotations

from typing import Iterable

from .chunking import ChunkingOptions, DocumentTextExtractor, chunk_documents
from .manifest import build_ingestion_manifest
from .models import DatasetPipelineResult, StudioDatasetDocument
from .qa import QAGenerationPolicy, build_qa_generation_tasks, generate_mock_qa_pairs


def build_studio_dataset_pipeline(
    tenant_id: str,
    documents: Iterable[StudioDatasetDocument],
    *,
    created_at: str | None = None,
    chunking_options: ChunkingOptions | None = None,
    qa_policy: QAGenerationPolicy | None = None,
    text_extractor: DocumentTextExtractor | None = None,
) -> DatasetPipelineResult:
    document_rows = tuple(documents)
    manifest = build_ingestion_manifest(tenant_id, document_rows, created_at=created_at)
    chunks = tuple(
        chunk_documents(
            document_rows,
            options=chunking_options or ChunkingOptions(),
            text_extractor=text_extractor,
        )
    )
    policy = qa_policy or QAGenerationPolicy()
    tasks = tuple(build_qa_generation_tasks(chunks, policy=policy))
    pairs = tuple(generate_mock_qa_pairs(tasks, policy=policy))
    return DatasetPipelineResult(
        manifest=manifest,
        chunks=chunks,
        qa_tasks=tasks,
        qa_pairs=pairs,
    )
