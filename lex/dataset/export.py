"""Export JSONL per dataset Lex supervisionati."""

from __future__ import annotations

import json
import csv
from io import StringIO
from typing import Iterable

from .models import DatasetFileType, DatasetFormat, QAPair


_SENSITIVE_LEVELS = {"sensitive", "highly_sensitive"}


def _training_metadata(pair: QAPair) -> dict:
    return {
        "qa_id": pair.qa_id,
        "tenant_id": pair.tenant_id,
        "document_id": pair.document_id,
        "chunk_id": pair.chunk_id,
        "source": pair.source.to_dict(),
        "dataset_kind": pair.dataset_kind,
        "intended_use": pair.intended_use,
        "review_status": pair.review_status,
        "requires_human_review": pair.requires_human_review,
        "privacy_classification": pair.privacy_classification,
        "automatic_training": False,
        "external_training": False,
    }


def qa_pair_to_alpaca(pair: QAPair) -> dict:
    return {
        "instruction": pair.question,
        "input": "",
        "output": pair.answer,
        "metadata": _training_metadata(pair),
    }


def qa_pair_to_sharegpt(pair: QAPair) -> dict:
    return {
        "conversations": [
            {"from": "human", "value": pair.question},
            {"from": "gpt", "value": pair.answer},
        ],
        "metadata": _training_metadata(pair),
    }


def qa_pair_to_multilingual(pair: QAPair, *, language: str = "it") -> dict:
    return {
        "language": language,
        "dataset_type": pair.dataset_kind,
        "messages": [
            {"role": "user", "content": pair.question},
            {"role": "assistant", "content": pair.answer},
        ],
        "metadata": _training_metadata(pair),
    }


def _eligible_pairs(
    pairs: Iterable[QAPair],
    *,
    include_pending_review: bool,
    allow_sensitive: bool,
) -> list[QAPair]:
    rows: list[QAPair] = []
    for pair in pairs:
        if pair.review_status == "rejected":
            continue
        if pair.review_status != "approved" and not include_pending_review:
            continue
        if pair.privacy_classification in _SENSITIVE_LEVELS and not allow_sensitive:
            continue
        rows.append(pair)
    return rows


def export_qa_pairs_jsonl(
    pairs: Iterable[QAPair],
    *,
    dataset_format: DatasetFormat = "alpaca",
    include_pending_review: bool = False,
    allow_sensitive: bool = False,
    external_training: bool = False,
) -> str:
    return export_qa_pairs(
        pairs,
        dataset_format=dataset_format,
        file_type="jsonl",
        include_pending_review=include_pending_review,
        allow_sensitive=allow_sensitive,
        external_training=external_training,
    )


def export_qa_pairs(
    pairs: Iterable[QAPair],
    *,
    dataset_format: DatasetFormat = "alpaca",
    file_type: DatasetFileType = "jsonl",
    include_pending_review: bool = False,
    allow_sensitive: bool = False,
    external_training: bool = False,
    language: str = "it",
) -> str:
    if external_training:
        raise ValueError("Export Lex non avvia né autorizza training esterno automatico.")
    if dataset_format not in {"alpaca", "sharegpt", "multilingual"}:
        raise ValueError(f"Formato dataset non supportato: {dataset_format!r}.")
    if file_type not in {"jsonl", "json", "csv"}:
        raise ValueError(f"Tipo file dataset non supportato: {file_type!r}.")

    if dataset_format == "alpaca":
        serializer = qa_pair_to_alpaca
    elif dataset_format == "sharegpt":
        serializer = qa_pair_to_sharegpt
    else:
        def serializer(pair: QAPair) -> dict:
            return qa_pair_to_multilingual(pair, language=language)
    rows = _eligible_pairs(
        pairs,
        include_pending_review=include_pending_review,
        allow_sensitive=allow_sensitive,
    )
    serialized = [serializer(pair) for pair in rows]
    if file_type == "jsonl":
        return "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in serialized)
    if file_type == "json":
        return json.dumps(serialized, ensure_ascii=False, sort_keys=True, indent=2)
    return _export_csv(serialized)


def _export_csv(rows: list[dict]) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["question", "answer", "format", "dataset_kind", "metadata_json"],
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        if "instruction" in row:
            question = row.get("instruction", "")
            answer = row.get("output", "")
            dataset_format = "alpaca"
        elif "conversations" in row:
            question = row["conversations"][0].get("value", "") if row.get("conversations") else ""
            answer = row["conversations"][1].get("value", "") if len(row.get("conversations") or []) > 1 else ""
            dataset_format = "sharegpt"
        else:
            messages = row.get("messages") or []
            question = messages[0].get("content", "") if messages else ""
            answer = messages[1].get("content", "") if len(messages) > 1 else ""
            dataset_format = "multilingual"
        metadata = row.get("metadata") or {}
        writer.writerow(
            {
                "question": question,
                "answer": answer,
                "format": dataset_format,
                "dataset_kind": metadata.get("dataset_kind") or row.get("dataset_type") or "",
                "metadata_json": json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            }
        )
    return output.getvalue()
