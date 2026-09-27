"""Redazione conservativa dei dettagli tecnici prima delle risposte JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from flask import current_app


_TECHNICAL_MARKERS = (
    "traceback",
    "stack trace",
    "exception",
    "errno",
    "sqlalchemy",
    "werkzeug",
    "site-packages",
    "/opt/",
    "/home/",
    "\\users\\",
    "c:\\",
)

_TECHNICAL_PATTERNS = (
    re.compile(r"\bsqlite(?:3)?(?:\s+(?:error|database|exception)|[.:])", re.IGNORECASE),
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


_PATH_MARKERS = {"/opt/", "/home/", "\\users\\", "c:\\"}


def _looks_technical(value: str, *, consenti_percorsi: bool = False) -> bool:
    lowered = value.lower()
    marcatori = [m for m in _TECHNICAL_MARKERS if not (consenti_percorsi and m in _PATH_MARKERS)]
    return any(marker in lowered for marker in marcatori) or any(
        pattern.search(value) for pattern in _TECHNICAL_PATTERNS
    )


def redact_exception_details(value: Any, *, consenti_percorsi: bool = False) -> Any:
    """Rimuove stack trace, eccezioni e path interni da payload esposti via API.

    `consenti_percorsi` lascia i percorsi del server nei dati del pannello di
    piattaforma: il superamministratore li vedeva già nelle viste storiche
    (cartelle dei backup, archivi degli studi), mentre tracce ed eccezioni
    restano comunque nascoste.
    """

    if isinstance(value, BaseException):
        return "Operazione non completata."
    if isinstance(value, Path):
        return value.name
    if isinstance(value, str):
        return "Operazione non completata." if _looks_technical(value, consenti_percorsi=consenti_percorsi) else value
    if isinstance(value, list):
        return [redact_exception_details(item, consenti_percorsi=consenti_percorsi) for item in value]
    if isinstance(value, tuple):
        return [redact_exception_details(item, consenti_percorsi=consenti_percorsi) for item in value]
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
                cleaned[key_text] = redact_exception_details(item, consenti_percorsi=consenti_percorsi)
        return cleaned
    return value


def redacted_json_response(payload: Any, status: int = 200, *, consenti_percorsi: bool = False):
    """Risposta JSON con payload sanificato prima della serializzazione."""

    body = json.dumps(redact_exception_details(payload, consenti_percorsi=consenti_percorsi), ensure_ascii=False, default=str)
    return current_app.response_class(body, status=status, mimetype="application/json")
