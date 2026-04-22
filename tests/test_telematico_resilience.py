from __future__ import annotations

import time

import pytest

from pct.runtime_resilience import CircuitBreakerOpenError, clear_runtime_circuit_breakers
from web.services.telematico_resilience import (
    describe_portale_runtime_error,
    get_portale_circuit_breaker,
    portale_breaker_snapshots,
    run_portale_runtime_operation,
)


def test_portale_runtime_operation_apre_circuito_e_restituisce_messaggio_operativo():
    clear_runtime_circuit_breakers("portale:pst:search")
    breaker = get_portale_circuit_breaker("pst", operation="search")

    def _fail():
        raise TimeoutError("request timed out")

    with pytest.raises(TimeoutError):
        run_portale_runtime_operation("pst", operation="search", callable_=_fail)
    with pytest.raises(TimeoutError):
        run_portale_runtime_operation("pst", operation="search", callable_=_fail)
    with pytest.raises(CircuitBreakerOpenError):
        run_portale_runtime_operation("pst", operation="search", callable_=lambda: [])

    snapshot = breaker.snapshot()
    assert snapshot["open"] is True
    assert "PST / PolisWeb" in snapshot["component"]
    message = describe_portale_runtime_error("pst", operation="search", exc=CircuitBreakerOpenError(snapshot["open_message"]))
    assert "PST / PolisWeb" in message or "sospeso" in message

    breaker._opened_at = time.monotonic() - 61  # type: ignore[attr-defined]
    assert run_portale_runtime_operation("pst", operation="search", callable_=lambda: ["ok"]) == ["ok"]


def test_portale_breaker_snapshots_espone_chiavi_attese():
    snapshots = portale_breaker_snapshots()
    assert "pst:search" in snapshots
    assert "pdp:preview" in snapshots
