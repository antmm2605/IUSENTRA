from __future__ import annotations

from threading import Barrier, Lock, Thread
from time import sleep

from web.services.react_dashboard_cache import clear_dashboard_payload_cache, get_dashboard_payload_cached


def test_dashboard_cache_singleflight_evita_build_concorrenti():
    clear_dashboard_payload_cache()
    barrier = Barrier(6)
    lock = Lock()
    calls = 0
    results: list[int] = []

    def builder() -> dict[str, int]:
        nonlocal calls
        with lock:
            calls += 1
            value = calls
        sleep(0.05)
        return {"value": value}

    def worker() -> None:
        barrier.wait()
        payload, _cache_hit = get_dashboard_payload_cached("test:singleflight", builder, ttl_seconds=10)
        with lock:
            results.append(int(payload["value"]))

    threads = [Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert calls == 1
    assert results == [1, 1, 1, 1, 1]
