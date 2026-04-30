from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from pct.scadenziario import PrioritaTermine, TipoTermine
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.helpers import get_scadenziario


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    return app


def test_react_scadenziario_page_collegata_nav_api_e_lex():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/components/ScadenziarioPage.tsx").read_text(encoding="utf-8")
    data_source = Path("frontend/src/scadenziarioData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/ScadenziarioPage.css").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")

    assert "/scadenziario" in app_source
    assert "isScadenziarioPage?<ScadenziarioPage/>" in app_source
    assert "Scadenziario Legale" in page_source
    assert "OperativeCards" in page_source
    assert "Completa selezionate" in page_source
    assert "FloatingLex" in page_source
    assert 'context="scadenziario"' in page_source
    assert "postDeadlineAction" in page_source
    assert "getScadenziarioPage" in data_source
    assert "/api/v1/ui/scadenziario" in data_source
    assert '@api_v1_react.get("/scadenziario")' in api_source
    assert ".iu-scad-page" in css
    assert "@media(max-width:760px)" in css
    assert "prefers-reduced-motion" in css


def test_react_scadenziario_bridge_usa_repository_reale(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    with app.app_context():
        gestione = get_scadenziario()
        scadenza = gestione.nuova(
            "Deposito memoria conclusionale",
            TipoTermine.DEPOSITO_MEMORIA,
            (date.today() + timedelta(days=2)).isoformat(),
            descrizione="Termine da fascicolo test React",
            perentorio=True,
        )
        gestione.aggiorna(scadenza.id, priorita=PrioritaTermine.CRITICA)

    response = client.get("/api/v1/ui/scadenziario", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["read_only"] is False
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["summary"]["open"] >= 1
    assert payload["summary"]["critical"] >= 1
    assert any(item["title"] == "Deposito memoria conclusionale" for item in payload["items"])
    row = next(item for item in payload["items"] if item["title"] == "Deposito memoria conclusionale")
    assert row["priority"] == "CRITICA"
    assert row["peremptory"] is True
    assert row["completeHref"].endswith(f"/{scadenza.id}/completa")
    assert payload["actions"]["exportCsv"] == "/scadenziario/export.csv"
    assert payload["actions"]["exportPdf"] == "/scadenziario/pdf"
    assert payload["actions"]["exportIcs"] == "/scadenziario/export.ics"
    assert payload["operativeCards"]


def test_route_ufficiale_scadenziario_serve_react_con_vista_classica_tecnica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/scadenziario")
        classic = client.get("/scadenziario?_legacy=1")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in html
    assert 'id="root"' in html
    assert classic.status_code == 200
    assert 'id="root"' not in classic.get_data(as_text=True)
