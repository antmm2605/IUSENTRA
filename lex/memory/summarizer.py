"""Sintesi memoria del bounded context Lex."""

from __future__ import annotations


def summarize_memory(items):
    return " | ".join(str(item) for item in list(items or []))
