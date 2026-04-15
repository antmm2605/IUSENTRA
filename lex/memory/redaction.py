"""Redazione contenuti sensibili in memoria Lex."""

from __future__ import annotations


def redact_sensitive(text: str) -> str:
    return str(text or "")
