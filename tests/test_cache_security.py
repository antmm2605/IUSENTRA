from pct import cache


def test_cache_memorizza_payload_cifrato_senza_json_in_chiaro(tmp_path):
    cache.clear()
    target = tmp_path / "auth" / "utenti.json"
    marker = "valore-riservato-123"

    cache.save(target, {"utente": {"campo": marker}})

    assert cache.load(target) == {"utente": {"campo": marker}}
    assert cache._store
    cached_payloads = [payload for _, payload in cache._store.values()]
    assert all(isinstance(payload, bytes) for payload in cached_payloads)
    assert all(marker.encode("utf-8") not in payload for payload in cached_payloads)
