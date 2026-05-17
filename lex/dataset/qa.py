"""Generazione governata di task Q&A senza dipendere da LLM reali."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .models import DocumentChunk, QAGenerationTask, QAPair, clean_text, stable_id
from .privacy import classify_privacy, redact_sensitive_for_dataset


@dataclass(frozen=True, slots=True)
class QAGenerationPolicy:
    max_pairs_per_chunk: int = 1
    min_chunk_chars: int = 80
    require_human_review: bool = True
    redact_sensitive: bool = True
    external_training_allowed: bool = False
    save_internal_reasoning: bool = False

    def __post_init__(self) -> None:
        if self.max_pairs_per_chunk < 1:
            raise ValueError("max_pairs_per_chunk deve essere almeno 1.")
        if self.min_chunk_chars < 0:
            raise ValueError("min_chunk_chars non può essere negativo.")
        if self.external_training_allowed:
            raise ValueError("La pipeline Lex non consente training esterno automatico.")
        if self.save_internal_reasoning:
            raise ValueError("La pipeline Lex non salva ragionamento interno nei dataset.")


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _extractive_answer(text: str, *, max_chars: int = 420) -> str:
    value = clean_text(text)
    if not value:
        return "Nessuna risposta generabile dal frammento."
    sentences = [sentence.strip() for sentence in _SENTENCE_RE.split(value) if sentence.strip()]
    answer = " ".join(sentences[:2]) if sentences else value
    if len(answer) > max_chars:
        answer = answer[: max_chars - 3].rstrip() + "..."
    return answer


def build_qa_generation_tasks(
    chunks: Iterable[DocumentChunk],
    *,
    policy: QAGenerationPolicy | None = None,
) -> list[QAGenerationTask]:
    opts = policy or QAGenerationPolicy()
    tasks: list[QAGenerationTask] = []
    for chunk in chunks:
        if len(chunk.text) < opts.min_chunk_chars:
            continue
        task_id = stable_id(chunk.chunk_id, "qa-task", opts.max_pairs_per_chunk, prefix="lex-qa-task-")
        tasks.append(
            QAGenerationTask(
                task_id=task_id,
                chunk_id=chunk.chunk_id,
                tenant_id=chunk.tenant_id,
                document_id=chunk.document_id,
                chunk_text=chunk.text,
                source=chunk.source,
                instructions=(
                    "Usa solo il frammento indicato come fonte.",
                    "Produci domande e risposte verificabili, brevi e senza contenuti inventati.",
                    "Non salvare ragionamento interno: conserva solo domanda, risposta e metadati fonte.",
                    "Marca l'esempio come candidato da revisione umana.",
                ),
                max_pairs=opts.max_pairs_per_chunk,
                requires_human_review=opts.require_human_review,
                privacy_classification=chunk.privacy_classification,
                metadata={
                    "rag_boundary": "chunk utilizzabile subito nel retrieval tenant-aware",
                    "fine_tuning_boundary": "solo candidato supervisionato dopo revisione",
                    "automatic_training": False,
                },
            )
        )
    return tasks


def generate_mock_qa_pairs(
    tasks: Iterable[QAGenerationTask],
    *,
    policy: QAGenerationPolicy | None = None,
) -> list[QAPair]:
    opts = policy or QAGenerationPolicy()
    pairs: list[QAPair] = []
    for task in tasks:
        privacy = classify_privacy(task.chunk_text, default=task.privacy_classification)
        answer = _extractive_answer(task.chunk_text)
        if opts.redact_sensitive and privacy in {"sensitive", "highly_sensitive"}:
            answer = redact_sensitive_for_dataset(answer)
        for pair_index in range(1, task.max_pairs + 1):
            question = "Quale informazione operativa risulta dal documento indicato?"
            if task.max_pairs > 1:
                question = f"{question} (punto {pair_index})"
            qa_id = stable_id(task.task_id, pair_index, question, answer, prefix="lex-qa-")
            pairs.append(
                QAPair(
                    qa_id=qa_id,
                    question=question,
                    answer=answer,
                    tenant_id=task.tenant_id,
                    document_id=task.document_id,
                    chunk_id=task.chunk_id,
                    source=task.source,
                    review_status="pending_human_review",
                    requires_human_review=opts.require_human_review,
                    privacy_classification=privacy,
                    metadata={
                        "generator": "deterministic_mock",
                        "automatic_training": False,
                        "external_training": False,
                    },
                )
            )
    return pairs


def mark_qa_pair_reviewed(
    pair: QAPair,
    *,
    approved: bool,
    reviewer_id: str = "",
    note: str = "",
) -> QAPair:
    return pair.reviewed(approved=approved, reviewer_id=reviewer_id, note=note)
