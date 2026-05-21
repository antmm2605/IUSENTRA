"""Redazione conservativa dei dettagli tecnici prima delle risposte JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import current_app


_TECHNICAL_MARKERS = (
    "traceback",
    "stack trace",
    "exception",
    "errno",
    "sqlite",
    "sqlalchemy",
    "werkzeug",
    "site-packages",
    "/opt/",
    "/home/",
    "\\users\\",
    "c:\\",
)

_SENSITIVE_KEYS = {
    "traceback",
    "stack",
    "stacktrace",
    "exception",
    "exc",
    "raw_exception",
    "debug",
}


def _looks_technical(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _TECHNICAL_MARKERS)


def redact_exception_details(value: Any) -> Any:
    """Rimuove stack trace, eccezioni e path interni da payload esposti via API."""

    if isinstance(value, BaseException):
        return "Operazione non completata."
    if isinstance(value, Path):
        return value.name
    if isinstance(value, str):
        return "Operazione non completata." if _looks_technical(value) else value
    if isinstance(value, list):
        return [redact_exception_details(item) for item in value]
    if isinstance(value, tuple):
        return [redact_exception_details(item) for item in value]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in _SENSITIVE_KEYS:
                cleaned[key_text] = "Dettaglio tecnico registrato nei log server."
            else:
                cleaned[key_text] = redact_exception_details(item)
        return cleaned
    return value


def redacted_json_response(payload: Any, status: int = 200):
    """Risposta JSON con payload sanificato prima della serializzazione."""

    body = json.dumps(redact_exception_details(payload), ensure_ascii=False, default=str)
    return current_app.response_class(body, status=status, mimetype="application/json")
