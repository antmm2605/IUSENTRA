"""Helper condivisi per connessioni IMAP affidabili."""

from __future__ import annotations

import os
import socket


DEFAULT_IMAP_TIMEOUT_SECONDS = 15
MIN_IMAP_TIMEOUT_SECONDS = 5
MAX_IMAP_TIMEOUT_SECONDS = 60


def resolve_imap_timeout_seconds(value: object | None = None) -> int:
    raw = value if value is not None else os.environ.get("PCT_IMAP_TIMEOUT", "")
    try:
        timeout = int(float(str(raw).strip() or DEFAULT_IMAP_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout = DEFAULT_IMAP_TIMEOUT_SECONDS
    return max(MIN_IMAP_TIMEOUT_SECONDS, min(MAX_IMAP_TIMEOUT_SECONDS, timeout))


def describe_imap_connection_error(exc: Exception, *, timeout_seconds: int) -> str:
    message = str(exc or "").strip()
    lowered = message.lower()
    if isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in lowered or "timeout" in lowered:
        return (
            f"Connessione IMAP non completata entro {timeout_seconds} secondi. "
            "Verifica server PEC, rete o credenziali e riprova."
        )
    if message:
        return f"Connessione IMAP fallita: {message}"
    return "Connessione IMAP fallita."
