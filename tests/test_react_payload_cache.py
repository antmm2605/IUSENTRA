"""Cache TTL dei payload React: hit, scadenza, limite voci e disattivazione."""

from web.services import react_payload_cache
from web.services.react_payload_cache import ReactPayloadTTLCache


def test_hit_entro_il_ttl_e_chiavi_distinte():
    cache = ReactPayloadTTLCache(ttl_seconds=60, max_entries=4)
    cache.set(("ricerca-legale", "studio-a"), b'{"ok": true}')
    assert cache.get(("ricerca-legale", "studio-a")) == b'{"ok": true}'
    assert cache.get(("ricerca-legale", "studio-b")) is None
    assert len(cache) == 1


def test_voce_scaduta_non_viene_servita(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(react_payload_cache.time, "monotonic", lambda: clock["now"])
    cache = ReactPayloadTTLCache(ttl_seconds=30, max_entries=4)
    cache.set(("news", ""), b"{}")
    clock["now"] += 29
    assert cache.get(("news", "")) == b"{}"
    clock["now"] += 2
    assert cache.get(("news", "")) is None
    assert len(cache) == 0


def test_limite_voci_espelle_le_piu_vicine_alla_scadenza(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr(react_payload_cache.time, "monotonic", lambda: clock["now"])
    cache = ReactPayloadTTLCache(ttl_seconds=100, max_entries=2)
    cache.set(("a",), b"a")
    clock["now"] += 1
    cache.set(("b",), b"b")
    clock["now"] += 1
    cache.set(("c",), b"c")
    assert len(cache) == 2
    assert cache.get(("a",)) is None
    assert cache.get(("b",)) == b"b"
    assert cache.get(("c",)) == b"c"


def test_ttl_zero_disattiva_la_cache():
    cache = ReactPayloadTTLCache(ttl_seconds=0, max_entries=4)
    assert not cache.enabled
    cache.set(("x",), b"x")
    assert cache.get(("x",)) is None
    assert len(cache) == 0


def test_payload_non_bytes_viene_ignorato():
    cache = ReactPayloadTTLCache(ttl_seconds=60, max_entries=4)
    cache.set(("x",), "stringa")  # type: ignore[arg-type]
    assert cache.get(("x",)) is None
