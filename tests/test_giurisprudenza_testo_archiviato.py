import importlib
from types import SimpleNamespace

import pytest
from flask import Flask, g, request

module = importlib.import_module("web.blueprints.giurisprudenza")


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(module.giurisprudenza)
    app.add_url_rule("/login", "login", lambda: "login")
    calls = []

    @app.before_request
    def identity():
        g.utente_corrente = {"id": "reader"} if request.headers.get("X-Test-User") else None

    def manager():
        calls.append("readonly")
        texts = {
            "tenant-a": {"a": {"testo_integrale": "Testo completo. " * 1000}},
            "tenant-b": {"b": {"testo_integrale": "<script>private()</script>"}},
        }
        tenant = request.headers.get("X-Test-Tenant", "tenant-a")
        return SimpleNamespace(get=lambda record: texts[tenant].get(record))

    monkeypatch.setattr(module, "get_giurisprudenza_readonly", manager)
    return app.test_client(), calls


def test_stored_text_is_complete_plain_and_not_cached(client):
    browser, calls = client
    response = browser.get("/giurisprudenza/a/testo", headers={"X-Test-User": "yes"})
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "Testo completo. " * 1000
    assert response.mimetype == "text/plain"
    assert "no-store" in response.headers["Cache-Control"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in response.headers["Content-Security-Policy"]
    assert calls == ["readonly"]


def test_login_required_before_read(client):
    browser, calls = client
    assert browser.get("/giurisprudenza/a/testo").status_code == 302
    assert calls == []


def test_record_is_resolved_only_in_current_tenant(client):
    browser, _ = client
    assert (
        browser.get("/giurisprudenza/b/testo", headers={"X-Test-User": "yes", "X-Test-Tenant": "tenant-a"}).status_code
        == 404
    )
    response = browser.get("/giurisprudenza/b/testo", headers={"X-Test-User": "yes", "X-Test-Tenant": "tenant-b"})
    assert response.status_code == 200 and response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == "<script>private()</script>"


def test_real_body_is_projected_into_native_sql_without_turning_notes_into_body(tmp_path):
    from pct.giurisprudenza import GestioneGiurisprudenza
    manager = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    base = {"titolo": "Decisione sintetica di prova", "source_system": "manuale_interno",
            "organo_giudicante": "Tribunale sintetico", "numero_provvedimento": "12/2026",
            "massima": "Nota redazionale, non testo della decisione."}
    record = manager.salva(base)
    assert manager.get(record["id"])["testo_integrale"] == ""
    body = "Testo della decisione presente nel documento. " * 45
    record = manager.salva({**base, "id": record["id"], "text_original": body})
    assert manager.get(record["id"])["testo_integrale"] == body.strip()
    projected = manager._corpus_payload_from_record(record)
    assert projected["testo_integrale"] == body.strip()
    assert projected["testo_integrale_presente"] is True
    manager.salva({**base, "id": record["id"], "massima": "Nota modificata"})
    assert manager.get(record["id"])["testo_integrale"] == body.strip()
    assert len(manager.judgment_text_versions(record["id"])) == 1
