"""Guardrail e messaggi operativi per i canali telematici esterni."""

from __future__ import annotations

import os
import socket
from typing import Any, Callable, TypeVar

from pct.runtime_resilience import (
    CircuitBreakerOpenError,
    RuntimeCircuitBreaker,
    get_runtime_circuit_breaker,
)


T = TypeVar("T")

_PORTALE_LABELS = {
    "pst": "PST / PolisWeb",
    "pdp": "PDP Penale",
    "pat": "PAT",
    "ptt": "PTT / SIGIT",
}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _resolve_guardrail_int(env_name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = str(os.getenv(env_name, "") or "").strip()
    try:
        value = int(float(raw or default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _portale_label(portale: str) -> str:
    normalized = _clean_spaces(portale).lower()
    return _PORTALE_LABELS.get(normalized, normalized.upper() or "Portale telematico")


def get_portale_circuit_breaker(portale: str, *, operation: str) -> RuntimeCircuitBreaker:
    normalized_portale = _clean_spaces(portale).lower() or "portale"
    normalized_operation = _clean_spaces(operation).lower() or "runtime"
    return get_runtime_circuit_breaker(
        f"portale:{normalized_portale}:{normalized_operation}",
        component=f"{_portale_label(normalized_portale)} ({normalized_operation})",
        failure_threshold=_resolve_guardrail_int(
            "PCT_PORTALE_CIRCUIT_FAILURE_THRESHOLD",
            2,
            minimum=1,
            maximum=10,
        ),
        recovery_timeout_seconds=_resolve_guardrail_int(
            "PCT_PORTALE_CIRCUIT_TIMEOUT",
            60,
            minimum=5,
            maximum=600,
        ),
        open_message_template=(
            "{component} temporaneamente sospeso dopo errori ripetuti. "
            "Verifica rete, certificati o disponibilita' del canale ufficiale e riprova tra circa "
            "{remaining_seconds} secondi."
        ),
    )


def run_portale_runtime_operation(
    portale: str,
    operation: str,
    callable_: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    return get_portale_circuit_breaker(portale, operation=operation).call(callable_, *args, **kwargs)


def describe_portale_runtime_error(portale: str, *, operation: str, exc: Exception) -> str:
    if isinstance(exc, CircuitBreakerOpenError):
        return str(exc)
    message = _clean_spaces(exc)
    lowered = message.lower()
    label = _portale_label(portale)
    action = "ricerca fascicoli" if str(operation or "").strip().lower() == "search" else "anteprima documenti"
    if isinstance(exc, (socket.timeout, TimeoutError)) or "timeout" in lowered or "timed out" in lowered:
        return (
            f"{label}: la {action} non ha risposto entro il tempo operativo atteso. "
            "Verifica rete, disponibilita' del canale ufficiale o credenziali e riprova."
        )
    if "subpro" in lowered or "sotto-procedimento" in lowered:
        return (
            f"{label}: il portale richiede il sotto-procedimento/registro corretto della pratica. "
            "IUSENTRA prosegue con l'acquisizione assistita: verifica ufficio, RG e anno sul portale "
            "ufficiale e completa il collegamento guidato senza perdere i dati gia inseriti."
        )
    if "soap fault" in lowered or "soap-env:client" in lowered:
        return (
            f"{label}: il portale ha respinto la richiesta SOAP. Verifica ufficio, RG, anno e canale "
            "autenticato; se il fascicolo e' visibile nel portale ufficiale, prosegui con acquisizione "
            "assistita e import dei file gia scaricati."
        )
    if message:
        return f"{label}: {message}"
    return f"{label}: canale temporaneamente non disponibile."


def portale_breaker_snapshots() -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for portale in ("pst", "pdp", "pat", "ptt"):
        for operation in ("search", "preview"):
            breaker = get_portale_circuit_breaker(portale, operation=operation)
            snapshots[f"{portale}:{operation}"] = breaker.snapshot()
    return snapshots
