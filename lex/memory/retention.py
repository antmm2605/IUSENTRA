"""Retention memoria del bounded context Lex."""

from __future__ import annotations


def should_retain_memory(kind: str) -> bool:
    return kind in {"session", "case", "profile"}
