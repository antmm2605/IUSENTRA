"""Pipeline dataset Lex per RAG interno e fine-tuning supervisionato."""

from __future__ import annotations

from .chunking import ChunkingOptions, chunk_document, chunk_documents, chunk_plain_text
from .batch import (
    DATASET_EXPORT_FORMATS,
    StudioDatasetBatchOptions,
    StudioDatasetBatchResult,
    build_studio_dataset_batch,
    load_document_ai_json_documents,
    qa_pairs_from_dicts,
)
from .easy_dataset import (
    EASY_DATASET_REFERENCE,
    build_easy_dataset_external_project_spec,
    easy_dataset_supported_capabilities,
)
from .export import export_qa_pairs, export_qa_pairs_jsonl, qa_pair_to_alpaca, qa_pair_to_multilingual, qa_pair_to_sharegpt
from .llama_factory import (
    LLAMA_FACTORY_REFERENCE,
    LLAMA_FACTORY_VIDEO_REFERENCE,
    build_llama_factory_dataset_info_entry,
    build_llama_factory_project_spec,
    llama_factory_supported_capabilities,
)
from .manifest import build_ingestion_manifest
from .models import (
    DatasetPipelineResult,
    DocumentChunk,
    DocumentPage,
    IngestionManifest,
    IngestionManifestDocument,
    QAGenerationTask,
    QAPair,
    SourceMetadata,
    StudioDatasetDocument,
)
from .nightly import (
    build_lex_dataset_for_document_ai_json,
    infer_document_ai_tenant_ids,
    run_lex_dataset_nightly,
)
from .pipeline import build_studio_dataset_pipeline
from .privacy import classify_privacy, redact_sensitive_for_dataset
from .qa import QAGenerationPolicy, build_qa_generation_tasks, generate_mock_qa_pairs, mark_qa_pair_reviewed

__all__ = [
    "ChunkingOptions",
    "DATASET_EXPORT_FORMATS",
    "DatasetPipelineResult",
    "DocumentChunk",
    "DocumentPage",
    "EASY_DATASET_REFERENCE",
    "IngestionManifest",
    "IngestionManifestDocument",
    "LLAMA_FACTORY_REFERENCE",
    "LLAMA_FACTORY_VIDEO_REFERENCE",
    "QAGenerationPolicy",
    "QAGenerationTask",
    "QAPair",
    "SourceMetadata",
    "StudioDatasetDocument",
    "StudioDatasetBatchOptions",
    "StudioDatasetBatchResult",
    "build_ingestion_manifest",
    "build_easy_dataset_external_project_spec",
    "build_lex_dataset_for_document_ai_json",
    "build_llama_factory_dataset_info_entry",
    "build_llama_factory_project_spec",
    "build_qa_generation_tasks",
    "build_studio_dataset_batch",
    "build_studio_dataset_pipeline",
    "chunk_document",
    "chunk_documents",
    "chunk_plain_text",
    "classify_privacy",
    "easy_dataset_supported_capabilities",
    "export_qa_pairs",
    "export_qa_pairs_jsonl",
    "generate_mock_qa_pairs",
    "infer_document_ai_tenant_ids",
    "llama_factory_supported_capabilities",
    "mark_qa_pair_reviewed",
    "load_document_ai_json_documents",
    "qa_pair_to_alpaca",
    "qa_pair_to_multilingual",
    "qa_pair_to_sharegpt",
    "qa_pairs_from_dicts",
    "redact_sensitive_for_dataset",
    "run_lex_dataset_nightly",
]
