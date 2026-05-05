from __future__ import annotations

from tests.test_global_search_api import _cfg_web, _crea_utente
from web.app import create_app


def _login(client):
    return client.post(
        "/login",
        data={"username": "operatore", "password": "Operatore123!"},
        follow_redirects=True,
    )


def test_global_search_stats_endpoint_non_costruisce_context_completo(tmp_path, monkeypatch):
    import web.blueprints.global_search as routes

    app = create_app(_cfg_web(tmp_path))
    _crea_utente(app)
    monkeypatch.setattr(routes, "_context", lambda: (_ for _ in ()).throw(AssertionError("_context non deve essere chiamato")))

    with app.test_client() as client:
        _login(client)
        response = client.get("/api/global-search/stats")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "stats" in payload


def test_global_search_indice_vuoto_non_reindicizza_sincrono(tmp_path, monkeypatch):
    from pct.global_search.service import GlobalSearchService

    app = create_app(_cfg_web(tmp_path))
    _crea_utente(app)

    def _forbidden_reindex(self, ctx):
        raise AssertionError("reindex sincrono non consentito durante la ricerca")

    monkeypatch.setattr(GlobalSearchService, "reindex", _forbidden_reindex)

    with app.test_client() as client:
        _login(client)
        response = client.get("/api/global-search?q=Rossi")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["indexing_required"] is True
    assert payload["results"] == []


def test_global_search_reindex_esplicito_resta_operativo(tmp_path, monkeypatch):
    from pct.global_search.service import GlobalSearchService

    app = create_app(_cfg_web(tmp_path))
    _crea_utente(app)
    called = {"value": False}

    def _fake_reindex(self, ctx):
        called["value"] = True
        return {"tenant_id": ctx["tenant_id"], "total": 0, "by_type": {}, "last_indexed_at": ""}

    monkeypatch.setattr(GlobalSearchService, "reindex", _fake_reindex)

    with app.test_client() as client:
        _login(client)
        response = client.post("/api/global-search/reindex")

    assert response.status_code == 200
    assert called["value"] is True
    assert response.get_json()["ok"] is True
