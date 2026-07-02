"""Memoria di apprendimento di Lex: JSONL append-only, ispezionabile a mano.

Ogni collezione è un file `<collezione>.jsonl` dentro `memory_dir`; ogni riga è
`{"schema_version", "record_id", "created_at", "payload"}`. Dedup per
`record_id` (stable_id del modello). Il clock è iniettabile per test
deterministici; `read_only=True` (dry-run) tiene il dedup in memoria senza
scrivere nulla su disco. I record sono dict generici: questo modulo non importa
i modelli di `lex.autonomy` (direzione import garantita).

Lo stato runtime NON vive mai dentro `lex/**` (che è versionato): il default
è `{PCT_DATA_ROOT|IUSENTRA_DATA_DIR}/intelligence/lex_memory/`, con fallback
locale `data/lex_memory` (gitignorato).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_PREFIX = "iusentra.lex_learning"
COLLECTIONS: tuple[str, ...] = (
    "legal_terms",
    "citations",
    "source_readings",
    "source_profiles",
    "unknown_concepts",
    "research_questions",
    "learning_signals",
    "improvement_proposals",
    "trust_assessments",
)


def default_memory_dir(env: Mapping[str, str] | None = None) -> Path:
    """Directory memoria di default: data-root runtime, fallback locale."""

    environ = env if env is not None else os.environ
    for key in ("PCT_DATA_ROOT", "IUSENTRA_DATA_DIR"):
        root = str(environ.get(key) or "").strip()
        if root:
            return Path(root) / "intelligence" / "lex_memory"
    return Path("data") / "lex_memory"


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class KnowledgeBase:
    """Store JSONL per collezione con dedup deterministico per record_id."""

    def __init__(
        self,
        memory_dir: str | Path | None = None,
        *,
        iso_now: Callable[[], str] | None = None,
        read_only: bool = False,
    ) -> None:
        self.memory_dir = Path(memory_dir) if memory_dir else default_memory_dir()
        self.read_only = bool(read_only)
        self._iso_now = iso_now or _iso_now_utc
        self._known_ids: dict[str, set[str]] = {}
        # In modalità read_only (dry-run) i record vivono solo qui: load() li
        # restituisce comunque, così il ciclo si comporta come nella run reale.
        self._memory_records: dict[str, list[dict[str, Any]]] = {}

    def path_for(self, collection: str) -> Path:
        self._require_collection(collection)
        return self.memory_dir / f"{collection}.jsonl"

    def append(self, collection: str, record_id: str, payload: Mapping[str, Any]) -> bool:
        """Aggiunge un record; False se il record_id è già presente (dedup)."""

        self._require_collection(collection)
        record_id = str(record_id or "").strip()
        if not record_id:
            raise ValueError("record_id obbligatorio per la memoria di apprendimento")
        known = self._ids(collection)
        if record_id in known:
            return False
        record = {
            "schema_version": f"{SCHEMA_PREFIX}.{collection}.v1",
            "record_id": record_id,
            "created_at": self._iso_now(),
            "payload": dict(payload),
        }
        if self.read_only:
            self._memory_records.setdefault(collection, []).append(record)
        else:
            path = self.path_for(collection)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        known.add(record_id)
        return True

    def load(self, collection: str) -> list[dict[str, Any]]:
        """Legge tutti i record della collezione (righe malformate saltate)."""

        path = self.path_for(collection)
        records: list[dict[str, Any]] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
        records.extend(dict(record) for record in self._memory_records.get(collection, []))
        return records

    def payloads(self, collection: str) -> list[dict[str, Any]]:
        return [dict(record.get("payload") or {}) for record in self.load(collection)]

    def known_ids(self, collection: str) -> set[str]:
        return set(self._ids(collection))

    def snapshot_counts(self) -> dict[str, int]:
        return {collection: len(self._ids(collection)) for collection in COLLECTIONS}

    def summarize(self) -> dict[str, Any]:
        counts = self.snapshot_counts()
        return {
            "memory_dir": str(self.memory_dir),
            "read_only": self.read_only,
            "counts": counts,
            "total_records": sum(counts.values()),
        }

    def _ids(self, collection: str) -> set[str]:
        self._require_collection(collection)
        cached = self._known_ids.get(collection)
        if cached is None:
            cached = {str(record.get("record_id") or "") for record in self.load(collection)}
            cached.discard("")
            self._known_ids[collection] = cached
        return cached

    @staticmethod
    def _require_collection(collection: str) -> None:
        if collection not in COLLECTIONS:
            raise ValueError(f"Collezione memoria sconosciuta: {collection!r}")


__all__ = ["COLLECTIONS", "KnowledgeBase", "default_memory_dir"]
