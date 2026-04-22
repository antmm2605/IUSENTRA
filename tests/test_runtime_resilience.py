from __future__ import annotations

import time

import pytest

from pct.runtime_resilience import (
    CircuitBreakerOpenError,
    clear_runtime_circuit_breakers,
    get_runtime_circuit_breaker,
)


def test_runtime_circuit_breaker_apre_e_recupera():
    clear_runtime_circuit_breakers("test-runtime")
    breaker = get_runtime_circuit_breaker(
        "test-runtime",
        component="Runtime test",
        failure_threshold=2,
        recovery_timeout_seconds=30,
        open_message_template="Runtime test sospeso per {remaining_seconds} secondi.",
    )

    def _fail():
        raise RuntimeError("runtime non disponibile")

    with pytest.raises(RuntimeError):
        breaker.call(_fail)
    with pytest.raises(RuntimeError):
        breaker.call(_fail)
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(lambda: "ok")

    snapshot = breaker.snapshot()
    assert snapshot["open"] is True
    assert snapshot["failure_count"] >= 2
    assert "sospeso" in snapshot["open_message"]

    breaker._opened_at = time.monotonic() - 31  # type: ignore[attr-defined]
    assert breaker.call(lambda: "ripristinato") == "ripristinato"
    assert breaker.snapshot()["state"] == "closed"
