"""Guardrail condivisi per runtime esterni instabili."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Callable, TypeVar


T = TypeVar("T")


class CircuitBreakerOpenError(RuntimeError):
    """Errore sollevato quando un runtime esterno e' temporaneamente sospeso."""


class RuntimeCircuitBreaker:
    def __init__(
        self,
        *,
        name: str,
        component: str,
        failure_threshold: int = 2,
        recovery_timeout_seconds: int = 60,
        open_message_template: str | None = None,
    ) -> None:
        self.name = str(name or "").strip() or "runtime"
        self.component = str(component or "").strip() or self.name
        self.failure_threshold = max(1, int(failure_threshold or 1))
        self.recovery_timeout_seconds = max(1, int(recovery_timeout_seconds or 1))
        self.open_message_template = (
            str(open_message_template or "").strip()
            or (
                f"{self.component} temporaneamente sospeso dopo errori ripetuti. "
                "Riprova tra circa {remaining_seconds} secondi."
            )
        )
        self._lock = Lock()
        self._state = "closed"
        self._failure_count = 0
        self._last_error = ""
        self._last_failure_at = 0.0
        self._opened_at = 0.0

    def _remaining_seconds_unlocked(self, now: float | None = None) -> int:
        if self._state != "open" or not self._opened_at:
            return 0
        current = now if now is not None else time.monotonic()
        elapsed = max(0.0, current - self._opened_at)
        return max(0, int(round(self.recovery_timeout_seconds - elapsed)))

    def _open_message_unlocked(self, now: float | None = None) -> str:
        remaining = self._remaining_seconds_unlocked(now)
        return self.open_message_template.format(
            component=self.component,
            name=self.name,
            remaining_seconds=remaining,
        )

    def call(self, operation: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        with self._lock:
            now = time.monotonic()
            if self._state == "open":
                if self._remaining_seconds_unlocked(now) > 0:
                    raise CircuitBreakerOpenError(self._open_message_unlocked(now))
                self._state = "half_open"

        try:
            result = operation(*args, **kwargs)
        except Exception as exc:
            self.record_failure(exc)
            raise

        self.record_success()
        return result

    def record_failure(self, exc: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_error = str(exc or "").strip()
            self._last_failure_at = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                self._state = "open"
                self._opened_at = self._last_failure_at
            else:
                self._state = "closed"

    def record_success(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failure_count = 0
            self._last_error = ""
            self._last_failure_at = 0.0
            self._opened_at = 0.0

    def reset(self) -> None:
        self.record_success()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            return {
                "name": self.name,
                "component": self.component,
                "state": self._state,
                "open": self._state == "open",
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_seconds": self.recovery_timeout_seconds,
                "remaining_seconds": self._remaining_seconds_unlocked(now),
                "last_error": self._last_error,
                "open_message": self._open_message_unlocked(now) if self._state == "open" else "",
            }


_BREAKERS: dict[str, RuntimeCircuitBreaker] = {}
_BREAKERS_LOCK = Lock()


def get_runtime_circuit_breaker(
    name: str,
    *,
    component: str,
    failure_threshold: int = 2,
    recovery_timeout_seconds: int = 60,
    open_message_template: str | None = None,
) -> RuntimeCircuitBreaker:
    key = str(name or "").strip() or "runtime"
    with _BREAKERS_LOCK:
        breaker = _BREAKERS.get(key)
        if breaker is None:
            breaker = RuntimeCircuitBreaker(
                name=key,
                component=component,
                failure_threshold=failure_threshold,
                recovery_timeout_seconds=recovery_timeout_seconds,
                open_message_template=open_message_template,
            )
            _BREAKERS[key] = breaker
        return breaker


def clear_runtime_circuit_breakers(*names: str) -> None:
    with _BREAKERS_LOCK:
        if not names:
            _BREAKERS.clear()
            return
        for name in names:
            _BREAKERS.pop(str(name or "").strip(), None)


def runtime_circuit_breaker_snapshots() -> dict[str, dict[str, Any]]:
    with _BREAKERS_LOCK:
        return {name: breaker.snapshot() for name, breaker in _BREAKERS.items()}
