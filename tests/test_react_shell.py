from __future__ import annotations

from pathlib import Path

from web.app import create_app
from web.bootstrap.blueprint_registry import BLUEPRINT_REGISTRY

from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    return app


def test_react_blueprints_registered(tmp_path: Path):
    app = _app(tmp_path)

    assert "react_shell" in app.blueprints
    assert "api_v1_react" in app.blueprints
    assert any(entry.name == "react_shell" for entry in BLUEPRINT_REGISTRY)
    assert any(entry.name == "api_v1_react" for entry in BLUEPRINT_REGISTRY)


def test_react_shell_non_sostituisce_ui_storica_e_richiede_login(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/app-v2")

    assert response.status_code in {302, 303}
    assert "/login" in response.headers["Location"]


def test_react_api_bridge_richiede_autenticazione(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/bootstrap")

    assert response.status_code == 401
    assert response.get_json()["errore"] == "Autenticazione richiesta."


def test_react_api_bootstrap_espone_flag_senza_switch(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/bootstrap", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["product"] == "IUSENTRA"
    assert payload["shell"] == "react"
    assert payload["mounted_at"] == "/app-v2"
    assert payload["route_flags"]["replace_dashboard"] is False
    assert payload["route_flags"]["replace_telematico"] is False


def test_react_dashboard_usa_bridge_reale_senza_mock(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/dashboard", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] in {"workspace_intelligente", "errore_controllato"}
    assert "stats" in payload
    assert set(payload["stats"]) == {
        "todayAppointments",
        "urgentDeadlines",
        "openMatters",
        "unpaidAmount",
        "documentsToReview",
    }
    assert "fascicoli" in payload
