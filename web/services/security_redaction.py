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

_BASE64_PAYLOAD_KEYS = {
    "base64",
    "content_base64",
    "contenuto_base64",
    "documento_b64",
    "file_base64",
    "firmato_b64",
    "bytes_base64",
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
            key_lower = key_text.lower()
            if key_lower in _SENSITIVE_KEYS:
                cleaned[key_text] = "Dettaglio tecnico registrato nei log server."
            elif key_lower in _BASE64_PAYLOAD_KEYS and isinstance(item, str):
                # I payload binari leciti, come Atto.enc per il Local Signer, possono
                # contenere casualmente parole che sembrano marker tecnici: non vanno
                # alterati, altrimenti il browser consegna allegati non validi.
                cleaned[key_text] = item
            else:
                cleaned[key_text] = redact_exception_details(item)
        return cleaned
    return value


def redacted_json_response(payload: Any, status: int = 200):
    """Risposta JSON con payload sanificato prima della serializzazione."""

    body = json.dumps(redact_exception_details(payload), ensure_ascii=False, default=str)
    return current_app.response_class(body, status=status, mimetype="application/json")
