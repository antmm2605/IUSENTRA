"""Interoperabilità governata con LLaMA Factory e Ollama."""

from __future__ import annotations

import re
from typing import Any, Literal

from .models import IngestionManifest


LLaMAFactoryFormat = Literal["alpaca", "sharegpt"]

LLAMA_FACTORY_REFERENCE = {
    "name": "LLaMA Factory",
    "repository": "https://github.com/hiyouga/LLaMA-Factory",
    "documentation": "https://llamafactory.readthedocs.io/en/latest/getting_started/webui.html",
    "dataset_readme": "https://github.com/hiyouga/LLaMA-Factory/blob/main/data/README.md",
    "license": "Apache-2.0",
    "integration_mode": "external_optional_training_tool",
}

LLAMA_FACTORY_VIDEO_REFERENCE = {
    "source": "YouTube",
    "video_id": "8T9epgWmaNI",
    "topic": "LLaMA Factory WebUI per supervised fine-tuning con dataset Alpaca/ShareGPT.",
    "status": "trascrizione analizzata il 2026-05-17",
}


def _safe_dataset_name(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", str(value or "").strip()).strip("_")
    if not slug:
        raise ValueError("Nome dataset LLaMA Factory obbligatorio.")
    return slug[:80]


def _safe_file_name(value: str) -> str:
    file_name = str(value or "").strip().replace("\\", "/").split("/")[-1]
    if not file_name or "." not in file_name:
        raise ValueError("Nome file dataset LLaMA Factory non valido.")
    if not file_name.lower().endswith((".json", ".jsonl", ".csv", ".parquet", ".arrow")):
        raise ValueError("LLaMA Factory accetta dataset json, jsonl, csv, parquet o arrow.")
    return file_name


def build_llama_factory_dataset_info_entry(
    *,
    dataset_name: str,
    file_name: str,
    dataset_format: LLaMAFactoryFormat = "alpaca",
) -> dict[str, Any]:
    """Crea la voce da inserire in `data/dataset_info.json`."""

    name = _safe_dataset_name(dataset_name)
    file = _safe_file_name(file_name)
    if dataset_format == "alpaca":
        return {
            name: {
                "file_name": file,
                "columns": {
                    "prompt": "instruction",
                    "query": "input",
                    "response": "output",
                    "system": "system",
                    "history": "history",
                },
            }
        }
    if dataset_format == "sharegpt":
        return {
            name: {
                "file_name": file,
                "formatting": "sharegpt",
                "columns": {
                    "messages": "conversations",
                    "system": "system",
                    "tools": "tools",
                },
                "tags": {
                    "role_tag": "from",
                    "content_tag": "value",
                    "user_tag": "human",
                    "assistant_tag": "gpt",
                    "system_tag": "system",
                },
            }
        }
    raise ValueError(f"Formato LLaMA Factory non supportato: {dataset_format!r}.")


def llama_factory_supported_capabilities() -> dict[str, Any]:
    return {
        "reference": dict(LLAMA_FACTORY_REFERENCE),
        "video_reference": dict(LLAMA_FACTORY_VIDEO_REFERENCE),
        "interfaces": ["LLaMA Board WebUI", "CLI"],
        "training_stages": ["sft", "pt", "rm", "ppo", "dpo", "kto", "orpo"],
        "recommended_stage_for_lex": "sft",
        "dataset_formats": ["alpaca", "sharegpt"],
        "dataset_files": ["json", "jsonl", "csv", "parquet", "arrow"],
        "recommended_finetuning": ["LoRA", "QLoRA"],
        "ollama": {
            "preferred_runtime": True,
            "export_modelfile_expected": True,
            "automatic_import": False,
            "requires_local_acceptance_test": True,
            "manual_commands": [
                "ollama create <nome-modello-lex> -f Modelfile",
                "ollama show <nome-modello-lex>",
                "ollama run <nome-modello-lex>",
            ],
        },
        "iusentra_policy": {
            "rag_before_finetuning": True,
            "human_review_required": True,
            "no_chain_of_thought_training": True,
            "no_training_on_private_data_without_authorization": True,
            "no_automatic_external_training": True,
            "no_automatic_llama_factory_training": True,
            "no_automatic_ollama_import": True,
            "tenant_dataset_isolation_required": True,
            "approved_pairs_only": True,
        },
    }


def build_llama_factory_project_spec(
    manifest: IngestionManifest,
    *,
    dataset_name: str,
    file_name: str = "iusentra_lex_alpaca.jsonl",
    dataset_format: LLaMAFactoryFormat = "alpaca",
    base_model: str = "qwen2.5:7b-instruct",
) -> dict[str, Any]:
    """Descrive come usare il dataset Lex in LLaMA Factory senza avviare training."""

    name = _safe_dataset_name(dataset_name)
    file = _safe_file_name(file_name)
    return {
        "tool": dict(LLAMA_FACTORY_REFERENCE),
        "video_reference": dict(LLAMA_FACTORY_VIDEO_REFERENCE),
        "tenant_id": manifest.tenant_id,
        "manifest_id": manifest.manifest_id,
        "dataset_name": name,
        "dataset_file": file,
        "dataset_format": dataset_format,
        "dataset_info_json_entry": build_llama_factory_dataset_info_entry(
            dataset_name=name,
            file_name=file,
            dataset_format=dataset_format,
        ),
        "dataset_registration": {
            "target_file": "data/dataset_info.json",
            "dataset_dir_default": "./data",
            "manual_edit_required": True,
            "registered_dataset_name": name,
            "preview_required_before_training": True,
        },
        "workflow": [
            "Esportare da IUSENTRA solo Q&A approvate in formato Alpaca o ShareGPT.",
            "Copiare il file nel dataset_dir di LLaMA Factory.",
            "Registrare la voce in data/dataset_info.json.",
            "Aprire LLaMA Board con llamafactory-cli webui.",
            "Selezionare stage SFT e fine-tuning LoRA/QLoRA.",
            "Usare Preview dataset prima di avviare il training.",
            "Valutare il checkpoint su dataset di test o chat controllata.",
            "Esportare modello/adattatore e Modelfile per Ollama solo dopo approvazione.",
        ],
        "manual_llama_factory_commands": [
            "llamafactory-cli webui",
        ],
        "recommended_training": {
            "stage": "sft",
            "finetuning_type": "lora",
            "dataset": name,
            "template": "auto",
            "output_dir": f"outputs/{name}",
            "num_train_epochs_start": 1,
            "learning_rate_start": "1e-4",
            "preview_required": True,
            "evaluation_required": True,
        },
        "ollama_plan": {
            "base_model": base_model,
            "expected_export_artifacts": ["checkpoint", "adapter_or_merged_model", "Modelfile"],
            "manual_commands_after_export": [
                "ollama create <nome-modello-lex> -f Modelfile",
                "ollama show <nome-modello-lex>",
                "ollama run <nome-modello-lex>",
            ],
            "automatic_import": False,
            "acceptance_tests": [
                "risposte su domande note del dataset",
                "assenza di dati non autorizzati",
                "citazione corretta della fonte interna",
                "confronto con RAG IUSENTRA sullo stesso documento",
            ],
        },
        "acceptance_gate": {
            "required_before_studio_use": True,
            "minimum_manual_checks": [
                "Preview dataset LLaMA Board senza righe vuote, colonne errate o testi sensibili non autorizzati.",
                "Valutazione checkpoint su domande note e risposte attese approvate dallo studio.",
                "Confronto con RAG IUSENTRA: il modello non deve sostituire le citazioni documentali.",
                "Test Ollama locale con Modelfile approvato e modello creato manualmente.",
                "Verifica privacy: nessuna risposta espone dati fuori tenant o fonti non autorizzate.",
            ],
            "reject_if": [
                "training avviato senza revisione umana",
                "import Ollama automatico",
                "dataset con ragionamento interno o dati sensibili non autorizzati",
                "risposte che inventano fonti o superano il perimetro del fascicolo",
            ],
        },
        "privacy_policy": {
            "tenant_id": manifest.tenant_id,
            "source_paths_exported": False,
            "approved_pairs_only": True,
            "sensitive_data_requires_explicit_authorization": True,
            "redaction_required_before_export": True,
            "external_upload_default": False,
            "rag_remains_primary_for_document_facts": True,
            "chain_of_thought_allowed": False,
        },
        "automation_policy": {
            "starts_llama_factory_training": False,
            "starts_ollama_import": False,
            "executes_shell_commands": False,
            "operator_runs_commands_manually": True,
        },
        "safety": {
            "external_training": False,
            "requires_human_review": True,
            "requires_studio_authorization": True,
            "private_data_redaction_required": True,
            "chain_of_thought_saved": False,
            "automatic_training": False,
            "automatic_ollama_import": False,
        },
        "sources": {
            "llama_factory_webui": LLAMA_FACTORY_REFERENCE["documentation"],
            "llama_factory_dataset_readme": LLAMA_FACTORY_REFERENCE["dataset_readme"],
            "video": "https://www.youtube.com/watch?v=8T9epgWmaNI",
        },
    }


__all__ = [
    "LLAMA_FACTORY_REFERENCE",
    "LLAMA_FACTORY_VIDEO_REFERENCE",
    "build_llama_factory_dataset_info_entry",
    "build_llama_factory_project_spec",
    "llama_factory_supported_capabilities",
]
