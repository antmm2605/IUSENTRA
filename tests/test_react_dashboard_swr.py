"""Panoramica rapida dopo il login: ultimo quadro valido condiviso e costruzione misurata."""

from __future__ import annotations

import time

import pytest

from web.services import react_dashboard_cache as cache
from web.services import react_dashboard_shared_cache as shared
from web.services.react_dashboard_build_context import (
    contesto_costruzione_panoramica,
    fabbrica_panoramica,
    gestore_panoramica,
    misura_sorgente,
    server_timing_header,
)


@pytest.fixture(autouse=True)
def _cache_in_memoria(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("PCT_REDIS_URL", raising=False)
    shared.reset_shared_dashboard_client()
    with cache._LOCK:
        cache._CACHE.clear()
    yield
    shared.reset_shared_dashboard_client()
    with cache._LOCK:
        cache._CACHE.clear()


def _builder(calls: list[int], value: str = "nuovo"):
    def build() -> dict[str, object]:
        calls.append(1)
        return {"status": "ok", "value": value}

    return build


def _svuota_cache_worker() -> None:
    # Simula un altro worker Gunicorn: nessuna cache in processo, archivio condiviso intatto.
    with cache._LOCK:
        cache._CACHE.clear()


def test_quadro_fresco_di_un_altro_worker_non_viene_ricalcolato():
    calls: list[int] = []
    payload, meta = cache.get_dashboard_payload_swr("k1", "utente-a", _builder(calls), day="2026-09-10")
    assert payload["value"] == "nuovo" and meta["hit"] is False and calls == [1]

    _svuota_cache_worker()
    payload, meta = cache.get_dashboard_payload_swr("k1", "utente-a", _builder(calls, "altro"), day="2026-09-10")
    assert calls == [1]
    assert payload["value"] == "nuovo"
    assert meta == {"hit": True, "stale": False, "shared": True, "age_seconds": 0}


def test_impronte_cambiate_mostrano_subito_l_ultimo_quadro_dichiarato_stale():
    calls: list[int] = []
    cache.get_dashboard_payload_swr("k-vecchia", "utente-a", _builder(calls, "vecchio"), day="2026-09-10")
    _svuota_cache_worker()

    payload, meta = cache.get_dashboard_payload_swr("k-nuova", "utente-a", _builder(calls, "nuovo"), day="2026-09-10")
    assert payload["value"] == "vecchio"
    assert meta["stale"] is True and meta["hit"] is True
    assert calls == [1]

    # Riallineamento del client (`stale=0`): ricalcolo e aggiornamento dell'archivio condiviso.
    payload, meta = cache.get_dashboard_payload_swr(
        "k-nuova", "utente-a", _builder(calls, "nuovo"), day="2026-09-10", allow_stale=False
    )
    assert payload["value"] == "nuovo" and meta["stale"] is False and calls == [1, 1]
    assert shared.read_shared_dashboard("utente-a")["cache_key"] == "k-nuova"


def test_quadro_di_un_altro_giorno_o_di_un_altro_utente_non_viene_mostrato():
    calls: list[int] = []
    cache.get_dashboard_payload_swr("k", "utente-a", _builder(calls, "ieri"), day="2026-09-09")
    _svuota_cache_worker()

    payload, meta = cache.get_dashboard_payload_swr("k2", "utente-a", _builder(calls, "oggi"), day="2026-09-10")
    assert payload["value"] == "oggi" and meta["stale"] is False and calls == [1, 1]

    _svuota_cache_worker()
    payload, meta = cache.get_dashboard_payload_swr("k3", "utente-b", _builder(calls, "utente-b"), day="2026-09-10")
    assert payload["value"] == "utente-b" and meta["stale"] is False and calls == [1, 1, 1]


def test_dopo_una_scrittura_esplicita_si_ricalcola_senza_quadro_precedente():
    calls: list[int] = []
    cache.get_dashboard_payload_swr("k", "utente-a", _builder(calls, "prima"), day="2026-09-10")
    time.sleep(0.01)
    cache.clear_dashboard_payload_cache()

    payload, meta = cache.get_dashboard_payload_swr("k", "utente-a", _builder(calls, "dopo"), day="2026-09-10")
    assert payload["value"] == "dopo" and meta["stale"] is False and calls == [1, 1]


def test_quadro_in_errore_non_diventa_ultimo_quadro_valido():
    calls: list[int] = []

    def errore() -> dict[str, object]:
        calls.append(1)
        return {"status": "errore"}

    cache.get_dashboard_payload_swr("k", "utente-a", errore, day="2026-09-10")
    assert shared.read_shared_dashboard("utente-a") is None


def test_gestori_aperti_una_volta_per_costruzione_e_tempi_misurati():
    aperture: list[int] = []

    def factory() -> object:
        aperture.append(1)
        return object()

    assert gestore_panoramica(factory) is not gestore_panoramica(factory)
    assert len(aperture) == 2

    with contesto_costruzione_panoramica() as costruzione:
        primo = gestore_panoramica(factory)
        assert fabbrica_panoramica(factory)() is primo
        assert misura_sorgente("agenda", lambda: 7) == 7
        misura_sorgente("agenda", lambda: time.sleep(0.01))
        riepilogo = costruzione.riepilogo()
    assert len(aperture) == 3
    assert riepilogo["sources"]["agenda"] >= 0.01
    header = server_timing_header(riepilogo)
    assert header.startswith("panoramica;dur=") and "agenda;dur=" in header


def test_endpoint_panoramica_serve_il_quadro_condiviso_e_misura_la_costruzione(tmp_path):
    from tests.test_email_client import _cfg_web
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    cfg["MULTI_TENANT"] = False
    app = create_app(cfg)
    app.config["API_KEY"] = "react-test-key"
    headers = {"X-API-Key": "react-test-key"}

    with app.test_client() as client:
        first = client.get("/api/v1/ui/dashboard", headers=headers)
        _svuota_cache_worker()
        second = client.get("/api/v1/ui/dashboard", headers=headers)
        revalidate = client.get("/api/v1/ui/dashboard?stale=0", headers=headers)

    assert first.status_code == 200
    assert first.headers["X-IUSENTRA-Cache"] == "MISS"
    assert first.headers["Server-Timing"].startswith("panoramica;dur=")
    build = first.get_json()["build"]
    assert build["seconds"] >= 0 and "workspace" in build["sources"] and "email" in build["sources"]
    assert second.headers["X-IUSENTRA-Cache"] == "HIT"
    assert second.get_json()["cache"]["shared"] is True
    assert revalidate.status_code == 200 and revalidate.get_json()["cache"]["stale"] is False
