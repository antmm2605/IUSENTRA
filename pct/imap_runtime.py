"""Helper condivisi per connessioni IMAP affidabili."""

from __future__ import annotations

import os
import secrets
import socket
from threading import Lock
from typing import Any, Callable, TypeVar

from pct.runtime_resilience import (
    CircuitBreakerOpenError,
    RuntimeCircuitBreaker,
    get_runtime_circuit_breaker,
    runtime_circuit_breaker_snapshots,
)


DEFAULT_IMAP_TIMEOUT_SECONDS = 15
MIN_IMAP_TIMEOUT_SECONDS = 5
MAX_IMAP_TIMEOUT_SECONDS = 60
DEFAULT_IMAP_CIRCUIT_THRESHOLD = 2
DEFAULT_IMAP_CIRCUIT_TIMEOUT_SECONDS = 60
T = TypeVar("T")
_IMAP_ACCOUNT_KEYS: dict[tuple[str, int, str], str] = {}
_IMAP_ACCOUNT_KEYS_LOCK = Lock()


def resolve_imap_timeout_seconds(value: object | None = None) -> int:
    raw = value if value is not None else os.environ.get("PCT_IMAP_TIMEOUT", "")
    try:
        timeout = int(float(str(raw).strip() or DEFAULT_IMAP_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout = DEFAULT_IMAP_TIMEOUT_SECONDS
    return max(MIN_IMAP_TIMEOUT_SECONDS, min(MAX_IMAP_TIMEOUT_SECONDS, timeout))


def resolve_imap_circuit_threshold(value: object | None = None) -> int:
    raw = value if value is not None else os.environ.get("PCT_IMAP_CIRCUIT_FAILURE_THRESHOLD", "")
    try:
        threshold = int(float(str(raw).strip() or DEFAULT_IMAP_CIRCUIT_THRESHOLD))
    except (TypeError, ValueError):
        threshold = DEFAULT_IMAP_CIRCUIT_THRESHOLD
    return max(1, min(10, threshold))


def resolve_imap_circuit_timeout_seconds(value: object | None = None) -> int:
    raw = value if value is not None else os.environ.get("PCT_IMAP_CIRCUIT_TIMEOUT", "")
    try:
        timeout = int(float(str(raw).strip() or DEFAULT_IMAP_CIRCUIT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout = DEFAULT_IMAP_CIRCUIT_TIMEOUT_SECONDS
    return max(5, min(600, timeout))


def get_imap_circuit_breaker(*, account: tuple[str, int, str] | None = None) -> RuntimeCircuitBreaker:
    key = "pec_imap"
    if account:
        host, port, username = account
        identity = (host.strip().lower(), port, username.strip())
        # I nomi dei circuiti compaiono nella diagnostica. L'identificativo
        # resta stabile nel processo senza contenere dati della casella.
        with _IMAP_ACCOUNT_KEYS_LOCK:
            alias = _IMAP_ACCOUNT_KEYS.get(identity)
            if alias is None:
                alias = secrets.token_hex(16)
                _IMAP_ACCOUNT_KEYS[identity] = alias
        key += ":" + alias
    return get_runtime_circuit_breaker(
        key,
        component="PEC / IMAP",
        failure_threshold=resolve_imap_circuit_threshold(),
        recovery_timeout_seconds=resolve_imap_circuit_timeout_seconds(),
        open_message_template=(
            "Connessione IMAP temporaneamente sospesa dopo errori ripetuti. "
            "Verifica server PEC o rete e riprova tra circa {remaining_seconds} secondi."
        ),
    )


def run_imap_runtime_operation(
    operation: Callable[..., T], *args: Any, account: tuple[str, int, str] | None = None, **kwargs: Any
) -> T:
    return get_imap_circuit_breaker(account=account).call(operation, *args, **kwargs)


def imap_breaker_snapshot() -> dict[str, Any]:
    snapshots = runtime_circuit_breaker_snapshots()
    accounts = [state for key, state in snapshots.items() if key.startswith("pec_imap:")]
    if not accounts:
        return get_imap_circuit_breaker().snapshot()
    return max(accounts, key=lambda state: (state["open"], state["failure_count"], state["remaining_seconds"]))


def describe_imap_connection_error(exc: Exception, *, timeout_seconds: int) -> str:
    if isinstance(exc, CircuitBreakerOpenError):
        return "Connessione IMAP temporaneamente sospesa dopo errori ripetuti. Verifica server PEC o rete e riprova."
    lowered = str(exc or "").lower()
    if isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in lowered or "timeout" in lowered:
        return (
            f"Connessione IMAP non completata entro {timeout_seconds} secondi. "
            "Verifica server PEC, rete o credenziali e riprova."
        )
    return "Connessione IMAP non completata. Verifica server PEC, rete o credenziali e riprova."
