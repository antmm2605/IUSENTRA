"""Wrapper sottili per chiamate esterne protette da circuit breaker."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from core.resilience.circuit_breaker import CircuitBreaker

T = TypeVar("T")

_BREAKERS: dict[str, CircuitBreaker] = {}


def call_external_service(
    name: str,
    operation: Callable[[], T],
    *,
    failure_threshold: int = 3,
    recovery_timeout: float = 60.0,
    fallback: Callable[[Exception], T] | None = None,
) -> T:
    breaker = _BREAKERS.setdefault(
        name,
        CircuitBreaker(name, failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
    )
    return breaker.call(operation, fallback=fallback)
