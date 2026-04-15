"""Healthcheck del bounded context Lex."""

from __future__ import annotations


def lex_health() -> dict:
    return {"ok": True}
