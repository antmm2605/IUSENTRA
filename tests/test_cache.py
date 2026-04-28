from __future__ import annotations

import time

from core.cache import CacheClient


def test_cache_memory_hit_miss_and_delete() -> None:
    cache = CacheClient("", default_ttl=30)
    assert cache.backend == "memory"
    assert cache.get("missing") is None
    cache.set("k", {"value": 1})
    assert cache.get("k") == {"value": 1}
    cache.delete("k")
    assert cache.get("k") is None


def test_cache_memory_expiry() -> None:
    cache = CacheClient("", default_ttl=1)
    cache.set("k", "v", ttl=1)
    assert cache.get("k") == "v"
    time.sleep(1.05)
    assert cache.get("k") is None


def test_cache_status_degrades_to_memory_without_redis() -> None:
    cache = CacheClient("redis://127.0.0.1:1/0")
    status = cache.status()
    assert status.ok
    assert status.backend == "memory"
