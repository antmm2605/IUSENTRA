"""Validazione payload API del modulo Lex."""

from __future__ import annotations


def validate_ask_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    for key in ("tenant_id", "user_id", "session_id", "query"):
        if not str(payload.get(key, "")).strip():
            errors.append(f"Missing field: {key}")
    return errors
