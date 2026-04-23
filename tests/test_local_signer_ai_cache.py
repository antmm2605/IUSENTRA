from local_signer_mod.ai_cache import TimedResultCache


def test_timed_result_cache_returns_cached_value():
    cache = TimedResultCache(ttl_seconds=60, max_items=4)
    payload = {"model": "gemma3:1b", "prompt": "ciao"}

    calls = {"count": 0}

    def factory():
        calls["count"] += 1
        return {"ok": True, "text": "risposta"}

    first = cache.get_or_set("chat", payload, factory)
    second = cache.get_or_set("chat", payload, factory)

    assert first == second
    assert calls["count"] == 1
