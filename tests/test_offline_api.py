"""Actual Flask JSON endpoints, isolated synthetic users/studios/database."""

from types import SimpleNamespace

import pytest
from flask import Flask, g

from pct.offline.crypto import digest
from tests.test_offline_sync import credential, make_repo, operation, signed
from tests.test_offline_sync import release_synthetic_postgres as release_synthetic_postgres  # noqa: PLC0414 — pytest fixture re-export
from web.bootstrap.offline_routes import register_offline_routes


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "synthetic-test-only"
    app.config.update(OFFLINE_WORKSPACE_ENABLED=True, MULTI_TENANT=True)
    repo = make_repo(tenant="synthetic-studio", actor="synthetic-admin")
    db = repo.db
    db.conn.execute("CREATE TABLE fascicoli(id TEXT PRIMARY KEY,numero TEXT,oggetto TEXT)")
    db.conn.execute("INSERT INTO fascicoli VALUES ('synthetic-case','TEST/2026','Dati sintetici')")
    (getattr(db, "raw_conn", None) or db.conn).commit()
    # The selected storage backend is injected; no tenant archives are opened.
    monkeypatch.setattr("web.services.storage_runtime.get_request_studio_db", lambda _: db)
    permissions = {"fascicoli.leggi", "fascicoli.scrivi", "utenti.scrivi"}
    app.config["TEST_ACTOR"] = "synthetic-admin"
    app.config["TEST_ROLE"] = "AMMINISTRATORE"
    app.config["TEST_TENANT"] = "synthetic-studio"

    @app.before_request
    def synthetic_context():
        g.tenant = SimpleNamespace(slug=app.config["TEST_TENANT"])
        g.data_paths = {"CLIENTI_DB": "/synthetic/tenants/" + g.tenant.slug + "/clienti.json"}
        g.utente_corrente = SimpleNamespace(
            id=app.config["TEST_ACTOR"],
            attivo=True,
            ruolo=SimpleNamespace(value=app.config["TEST_ROLE"]),
            ha_permesso=lambda p: p in permissions,
        )

    monkeypatch.setattr("web.services.tenant_isolation_runtime.assert_tenant_data_path", lambda path, **_: path)
    manager = SimpleNamespace(get=lambda case: SimpleNamespace(id=case) if case == "synthetic-case" else None)
    register_offline_routes(
        app, get_fascicoli=lambda: manager, get_utenti=lambda: None, audit=lambda *args, **kwargs: None
    )
    client = app.test_client()
    with client.session_transaction() as session:
        session["_csrf_token"] = "synthetic-csrf"
    return client, app, permissions


def post(client, path, data):
    return client.post("/api/v1/offline" + path, json=data, headers={"X-CSRF-Token": "synthetic-csrf"})


def enroll(client):
    key, public = credential()
    registered = post(client, "/devices", {"label": "PC sintetico", "public_key": public}).get_json()
    device = registered["id"]
    nonce = post(client, f"/devices/{device}/challenge", {"purpose": "enroll"}).get_json()
    assert post(client, f"/devices/{device}/prove", {"proof": signed(key, nonce)}).status_code == 200
    return device, key, registered["fingerprint"]


def exchange(client, device, key, intent):
    nonce = post(client, f"/devices/{device}/challenge", {"purpose": "sync:" + digest(intent)}).get_json()
    return post(client, f"/devices/{device}/sync", {"intent": intent, "proof": signed(key, nonce)})


def test_full_api_registration_approval_sync_and_revocation(client):
    browser, _app, _ = client
    assert browser.get("/api/v1/offline/context").get_json()["admin"]
    device, key, fingerprint = enroll(browser)
    assert (
        post(browser, f"/devices/{device}/sync", {"intent": {"cursor": 0, "operations": []}, "proof": {}}).status_code
        == 403
    )
    assert post(browser, f"/devices/{device}/approve", {"fingerprint": fingerprint}).status_code == 200
    op = operation()
    result = exchange(browser, device, key, {"cursor": 0, "operations": [op]})
    assert result.status_code == 200 and result.get_json()["changes"][0]["payload"] == op["payload"]
    assert result.get_json()["cases"][0]["label"] == "TEST/2026 — Dati sintetici"
    assert "no-store" in result.headers["Cache-Control"]
    assert post(browser, f"/devices/{device}/revoke", {}).status_code == 200
    assert post(browser, f"/devices/{device}/challenge", {"purpose": "sync:a"}).status_code == 403
    assert browser.get("/api/v1/offline/audit").get_json()["events"]


def test_csrf_tenant_and_rbac_fail_closed(client):
    browser, app, permissions = client
    assert browser.post("/api/v1/offline/devices", json={}).status_code == 403
    device, _key, fingerprint = enroll(browser)
    app.config["TEST_ROLE"] = "AVVOCATO"
    assert post(browser, f"/devices/{device}/approve", {"fingerprint": fingerprint}).status_code == 403
    assert browser.get("/api/v1/offline/audit").status_code == 403
    app.config["TEST_TENANT"] = "other-synthetic-studio"
    assert browser.get("/api/v1/offline/context").get_json()["devices"] == []
    assert post(browser, f"/devices/{device}/revoke", {}).status_code == 403
    app.config["TEST_TENANT"] = "synthetic-studio"
    app.config["TEST_ACTOR"] = "other-actor"
    assert post(browser, f"/devices/{device}/revoke", {}).status_code == 403
    permissions.clear()
    assert browser.get("/api/v1/offline/context").status_code == 403


def test_disabled_and_sql_unavailable_never_fallback(client, monkeypatch):
    browser, app, _ = client
    app.config["OFFLINE_WORKSPACE_ENABLED"] = False
    assert browser.get("/api/v1/offline/context").status_code == 503
    app.config["OFFLINE_WORKSPACE_ENABLED"] = True
    monkeypatch.setattr("web.services.storage_runtime.get_request_studio_db", lambda _: None)
    assert browser.get("/api/v1/offline/context").status_code == 503
