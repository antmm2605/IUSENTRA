"""Chunking testuale per il retrieval Lex.

Il modulo mantiene il vecchio helper string-based, ma accetta anche chunk gia'
strutturati prodotti da parser di documento come Docling.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    safe = str(text or "")
    return [safe[index : index + max_chars] for index in range(0, len(safe), max_chars)] or [""]


def _to_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return dict(asdict(value))
    payload: dict[str, Any] = {}
    for name in (
        "chunk_index",
        "text",
        "markdown",
        "page_no",
        "section_path",
        "bbox_json",
        "table_json",
        "ocr_used",
        "confidence",
        "metadata",
    ):
        if hasattr(value, name):
            payload[name] = getattr(value, name)
    return payload


def normalize_structured_chunks(chunks: list[Any] | tuple[Any, ...] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, chunk in enumerate(list(chunks or []), start=1):
        payload = _to_mapping(chunk)
        text = str(payload.get("text") or payload.get("markdown") or "").strip()
        if not text:
            continue
        payload["text"] = text
        payload["markdown"] = str(payload.get("markdown") or text)
        payload["chunk_index"] = int(payload.get("chunk_index") or index)
        rows.append(payload)
    return rows


def chunk_structured_text(
    text: str,
    *,
    structured_chunks: list[Any] | tuple[Any, ...] | None = None,
    max_chars: int = 1200,
) -> list[dict[str, Any]]:
    rows = normalize_structured_chunks(structured_chunks)
    if rows:
        return rows
    return [
        {
            "chunk_index": index,
            "text": chunk,
            "markdown": chunk,
            "page_no": None,
            "section_path": "",
            "bbox_json": "",
            "table_json": "",
            "ocr_used": False,
            "confidence": 0.75,
            "metadata": {},
        }
        for index, chunk in enumerate(chunk_text(text, max_chars=max_chars), start=1)
        if str(chunk or "").strip()
    ] or [
        {
            "chunk_index": 1,
            "text": "",
            "markdown": "",
            "page_no": None,
            "section_path": "",
            "bbox_json": "",
            "table_json": "",
            "ocr_used": False,
            "confidence": 0.0,
            "metadata": {},
        }
    ]
