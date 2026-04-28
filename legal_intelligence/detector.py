"""Rilevazione variazioni tra snapshot ufficiali."""

from __future__ import annotations

import difflib
import hashlib


def content_hash(normalized_text: str) -> str:
    return hashlib.sha256((normalized_text or "").encode("utf-8")).hexdigest()


def has_changed(previous_hash: str | None, new_hash: str) -> bool:
    return bool(previous_hash and new_hash and previous_hash != new_hash)


def build_diff(previous_text: str, new_text: str, *, max_lines: int = 120) -> str:
    old_lines = (previous_text or "").splitlines() or [(previous_text or "")[:2000]]
    new_lines = (new_text or "").splitlines() or [(new_text or "")[:2000]]
    lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="snapshot_precedente",
            tofile="snapshot_corrente",
            lineterm="",
        )
    )
    return "\n".join(lines[:max_lines])
