"""SHA-256 helpers for canonical events and binary evidence files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

from .canonical import canonicalize


HASH_ALG = "SHA-256"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_canonical(value: object) -> str:
    return sha256_bytes(canonicalize(value))


def sha256_stream(stream: BinaryIO, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: str | Path) -> str:
    with Path(path).open("rb") as handle:
        return sha256_stream(handle)


def is_sha256_hex(value: str) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)
