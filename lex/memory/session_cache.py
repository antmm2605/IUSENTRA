"""Cache leggera di sessione per Lex."""

from __future__ import annotations

from typing import Any


def cache_key(*parts: object) -> str:
    return "::".join(str(part or "").strip() for part in parts if str(part or "").strip())


def snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict(payload or {})
