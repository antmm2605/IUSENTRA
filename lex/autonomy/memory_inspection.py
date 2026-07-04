"""Ispezione read-only della memoria di apprendimento autonomo di Lex.

Serve la superficie web (`/api/v1/ui/lex-learning`): conteggi per collezione,
ultime proposte in revisione umana e ultime letture di fonti — SENZA mai
creare directory o file (la memoria durevole nasce solo dal ciclo, qui si
guarda soltanto). Memoria assente o righe corrotte → payload onesto con zeri
e liste vuote, mai eccezioni verso la superficie.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lex.knowledge.knowledge_base import COLLECTIONS, default_memory_dir


def _count_lines(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _tail_records(path: Path, limit: int) -> list[dict[str, Any]]:
    """Ultimi ``limit`` record del JSONL, dal più recente; righe rotte saltate."""

    if limit <= 0:
        return []
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in reversed(lines[-limit:]):
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _text(value: Any) -> str:
    return str(value or "").strip()


def _proposal_row(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    return {
        "titolo": _text(payload.get("title")),
        "tipo": _text(payload.get("kind")),
        "descrizione": _text(payload.get("description")),
        "modulo": _text(payload.get("target_module")),
        "confidenza": float(payload.get("confidence") or 0.0),
        "revisione_umana": bool(payload.get("requires_human_review", True)),
        "creato_il": _text(record.get("created_at")),
    }


def _reading_row(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    citations = payload.get("citations_normalized")
    return {
        "titolo": _text(payload.get("title")) or _text(payload.get("url")),
        "url": _text(payload.get("url")),
        "stato": _text(payload.get("status")),
        "area": _text(payload.get("area")),
        "fonte": _text(payload.get("source_id")),
        "caratteri": int(payload.get("text_characters") or 0),
        "citazioni": len(citations) if isinstance(citations, list) else 0,
        "letto_il": _text(payload.get("fetched_at")) or _text(record.get("created_at")),
    }


def inspect_memory(
    memory_dir: str | Path | None = None,
    *,
    proposals_limit: int = 20,
    readings_limit: int = 10,
) -> dict[str, Any]:
    """Fotografia read-only della memoria: mai side-effect su disco."""

    base = Path(memory_dir) if memory_dir else default_memory_dir()
    conteggi = {collection: _count_lines(base / f"{collection}.jsonl") for collection in COLLECTIONS}
    proposte = [
        _proposal_row(record)
        for record in _tail_records(base / "improvement_proposals.jsonl", proposals_limit)
    ]
    letture = [
        _reading_row(record)
        for record in _tail_records(base / "source_readings.jsonl", readings_limit)
    ]
    return {
        "directory": str(base),
        "memoria_presente": any(conteggi.values()),
        "conteggi": conteggi,
        "proposte": proposte,
        "letture": letture,
    }


__all__ = ["inspect_memory"]
