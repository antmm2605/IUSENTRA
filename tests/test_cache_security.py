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


def test_cache_blocca_scritture_json_su_percorsi_sqlite(tmp_path):
    cache.clear()

    for filename in (
        "studio.db",
        "pec_audit.sqlite",
        "scheduler.sqlite3",
        "studio.db-wal",
        "studio.db-shm",
        "studio.db-journal",
    ):
        target = tmp_path / filename
        try:
            cache.save(target, {"x": 1})
        except ValueError as exc:
            assert "percorso SQLite" in str(exc)
        else:  # pragma: no cover - esplicita il contratto anti-corruzione
            raise AssertionError(f"cache.save ha scritto JSON su {filename}")
        assert not target.exists()


def test_cache_blocca_letture_json_da_percorsi_sqlite_anche_se_contengono_json(tmp_path):
    cache.clear()
    target = tmp_path / "studio.db"
    target.write_text('{"x": 1}', encoding="utf-8")

    try:
        cache.load(target)
    except ValueError as exc:
        assert "percorso SQLite" in str(exc)
    else:  # pragma: no cover - esplicita il contratto anti-corruzione
        raise AssertionError("cache.load ha interpretato un database SQLite come JSON")
