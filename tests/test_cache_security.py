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


def test_cache_blocca_chiavi_private_in_json_chiaro(tmp_path):
    cache.clear()
    target = tmp_path / "calendario" / "provider.json"
    sensitive_key = "".join(("pri", "vate"))
    payload = {
        "eventi": [
            {
                "id": "google-1",
                "extendedProperties": {
                    sensitive_key: {
                        "iusentra_categories": "IUSENTRA-SCADENZA,IUSENTRA-PERENTORIA",
                    }
                },
            }
        ]
    }

    try:
        cache.save(target, payload)
    except ValueError as exc:
        assert "chiavi sensibili in chiaro" in str(exc)
        assert f"extendedProperties.{sensitive_key}" in str(exc)
    else:  # pragma: no cover - esplicita il contratto anti-segreti
        raise AssertionError("cache.save ha scritto un contenitore provider private in JSON")
    assert not target.exists()


def test_cache_blocca_chiavi_private_key_in_json_chiaro(tmp_path):
    cache.clear()
    target = tmp_path / "segreti" / "chiavi.json"
    sensitive_key = "".join(("pri", "vate", "_", "key"))

    try:
        cache.save(target, {"firma": {sensitive_key: "-----BEGIN PRIVATE KEY-----"}})
    except ValueError as exc:
        assert "chiavi sensibili in chiaro" in str(exc)
        assert f"firma.{sensitive_key}" in str(exc)
    else:  # pragma: no cover - esplicita il contratto anti-segreti
        raise AssertionError("cache.save ha scritto una chiave privata in JSON")
    assert not target.exists()


def test_save_produce_byte_identici_a_json_dump(tmp_path):
    """La scrittura via `json.dumps` + write deve dare gli stessi byte di `json.dump`."""

    import json

    from pct import cache as _cache

    payload = {
        "tables": {f"t{i}": {"rows": list(range(20)), "note": "àèìòù \"quotato\""} for i in range(50)},
        "sync_runs": [{"id": i, "status": "bootstrap"} for i in range(30)],
        "misto": [1, 2.5, None, True, {"nested": {"deep": ["a", "b"]}}],
    }

    for indent in (None, 2):
        atteso = tmp_path / f"atteso-{indent}.json"
        with atteso.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=indent, default=str)

        prodotto = tmp_path / f"prodotto-{indent}.json"
        _cache.save(prodotto, payload, indent=indent)

        assert prodotto.read_bytes() == atteso.read_bytes()
        assert json.loads(prodotto.read_text(encoding="utf-8")) == payload


def test_save_serializza_valori_non_json_con_default_str(tmp_path):
    """`default=str` resta attivo: date e oggetti non serializzabili non fanno esplodere il salvataggio."""

    import json
    from datetime import date

    from pct import cache as _cache

    percorso = tmp_path / "con-date.json"
    _cache.save(percorso, {"quando": date(2026, 8, 1)})

    assert json.loads(percorso.read_text(encoding="utf-8")) == {"quando": "2026-08-01"}
