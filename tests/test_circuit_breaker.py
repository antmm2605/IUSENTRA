from __future__ import annotations

import pytest

from core.resilience.circuit_breaker import CircuitBreaker


def test_circuit_breaker_opens_after_failures() -> None:
    breaker = CircuitBreaker("ollama", failure_threshold=2, recovery_timeout=30)

    def fail() -> str:
        raise RuntimeError("servizio giu")

    with pytest.raises(RuntimeError):
        breaker.call(fail)
    with pytest.raises(RuntimeError):
        breaker.call(fail)

    snapshot = breaker.snapshot()
    assert snapshot.state == "open"
    assert snapshot.failures == 2


def test_circuit_breaker_uses_fallback_when_open() -> None:
    breaker = CircuitBreaker("smtp", failure_threshold=1, recovery_timeout=30)

    def fail() -> str:
        raise RuntimeError("smtp down")

    result = breaker.call(fail, fallback=lambda exc: "fallback")
    assert result == "fallback"
    assert breaker.snapshot().state == "open"


def test_circuit_breaker_recovers_after_success_in_half_open() -> None:
    breaker = CircuitBreaker("redis", failure_threshold=1, recovery_timeout=1)
    breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("down")), fallback=lambda exc: "ko")
    breaker.opened_at = 0
    assert breaker.call(lambda: "ok") == "ok"
    assert breaker.snapshot().state == "closed"
