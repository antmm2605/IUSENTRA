"""Circuit breaker closed/open/half-open per servizi esterni."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass
class CircuitBreakerSnapshot:
    name: str
    state: str
    failures: int
    last_error: str = ""


class CircuitBreaker:
    def __init__(self, name: str, *, failure_threshold: int = 3, recovery_timeout: float = 60.0) -> None:
        self.name = name
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_timeout = max(1.0, float(recovery_timeout))
        self.state = "closed"
        self.failures = 0
        self.opened_at = 0.0
        self.last_error = ""

    def call(self, func: Callable[[], T], *, fallback: Callable[[Exception], T] | None = None) -> T:
        if self.state == "open":
            if time.time() - self.opened_at < self.recovery_timeout:
                exc = RuntimeError(f"Circuito {self.name} temporaneamente aperto")
                if fallback:
                    return fallback(exc)
                raise exc
            self.state = "half-open"
        try:
            result = func()
        except Exception as exc:
            self._record_failure(exc)
            if fallback:
                return fallback(exc)
            raise
        self._record_success()
        return result

    def _record_failure(self, exc: Exception) -> None:
        self.failures += 1
        self.last_error = str(exc)
        if self.failures >= self.failure_threshold:
            self.state = "open"
            self.opened_at = time.time()

    def _record_success(self) -> None:
        self.failures = 0
        self.last_error = ""
        self.state = "closed"

    def snapshot(self) -> CircuitBreakerSnapshot:
        return CircuitBreakerSnapshot(self.name, self.state, self.failures, self.last_error)
