"""Compatibilità governata con Easy Dataset come strumento esterno."""

from __future__ import annotations

from typing import Any

from .models import IngestionManifest


EASY_DATASET_REFERENCE = {
    "name": "Easy Dataset",
    "repository": "https://github.com/ConardLi/easy-dataset",
    "license": "AGPL-3.0",
    "integration_mode": "external_optional_tool",
    "code_reuse_allowed": False,
}

_INPUT_FORMATS = ("PDF", "Markdown", "DOCX", "TXT", "EPUB")
_DATASET_TYPES = ("single_turn_qa", "multi_turn_dialogue", "eval")
_EXPORT_FORMATS = ("alpaca", "sharegpt", "multilingual", "json", "jsonl", "csv")
_MODEL_ENDPOINTS = ("ollama_local", "openai_compatible")


def easy_dataset_supported_capabilities() -> dict[str, Any]:
    return {
        "reference": dict(EASY_DATASET_REFERENCE),
        "input_formats": list(_INPUT_FORMATS),
        "dataset_types": list(_DATASET_TYPES),
        "export_formats": list(_EXPORT_FORMATS),
        "model_endpoints": list(_MODEL_ENDPOINTS),
        "iusentra_policy": {
            "no_agpl_code_import": True,
            "review_required_before_import": True,
            "no_external_training_automation": True,
            "no_saved_internal_reasoning": True,
            "preferred_model_endpoint": "ollama_local",
            "openai_compatible_requires_lex_policy": True,
        },
    }


def build_easy_dataset_external_project_spec(
    manifest: IngestionManifest,
    *,
    domain_label_tree: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Produce una specifica di interoperabilità, non un adapter runtime AGPL."""
    return {
        "tool": dict(EASY_DATASET_REFERENCE),
        "tenant_id": manifest.tenant_id,
        "manifest_id": manifest.manifest_id,
        "license_boundary": {
            "easy_dataset_runs_outside_iusentra": True,
            "copy_agpl_code_into_iusentra": False,
            "allowed_exchange": "file import/export di dati revisionabili",
        },
        "documents": [
            {
                "document_id": document.document_id,
                "title": document.title,
                "source_name": document.source_name,
                "mime_type": document.mime_type,
                "privacy_classification": document.privacy_classification,
            }
            for document in manifest.documents
        ],
        "domain_label_tree": domain_label_tree or [],
        "dataset_targets": {
            "rag": {
                "enabled": True,
                "mode": "chunk tenant-aware in IUSENTRA",
                "fine_tuning_required": False,
            },
            "fine_tuning": {
                "enabled": True,
                "mode": "Q&A supervisionate, approvate e importabili",
                "human_review_required": True,
                "automatic_training": False,
            },
            "evaluation": {
                "enabled": True,
                "mode": "dataset di valutazione importabile come artefatto revisionato",
            },
        },
        "generation_steps": [
            "document_parsing",
            "segmentation",
            "data_cleaning",
            "domain_label_tree",
            "question_generation",
            "answer_generation",
            "human_review",
            "iusentra_import",
        ],
        "exports": {
            "preferred": ["alpaca.jsonl", "sharegpt.jsonl", "multilingual.jsonl", "csv"],
            "supported_by_iusentra": list(_EXPORT_FORMATS),
        },
        "model_policy": {
            "ollama_local": "consentito come default locale governato",
            "openai_compatible": "solo se LEX_EXTERNAL_ALLOWED e policy privacy lo consentono",
        },
    }
