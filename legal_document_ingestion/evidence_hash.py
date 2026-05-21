"""Primitive hash e catena probatoria append-only."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(bytes(data or b"")).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(str(text or "").encode("utf-8"))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def chain_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    envelope = {
        "prev_hash": str(prev_hash or ""),
        "payload": payload,
    }
    return sha256_text(canonical_json(envelope))


def short_hash(value: str, length: int = 12) -> str:
    return str(value or "")[: max(4, int(length or 12))]
