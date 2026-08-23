from __future__ import annotations

from pathlib import Path

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def test_product_readiness_api_richiede_sessione_e_restituisce_catalogo_read_only(tmp_path) -> None:
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        anonymous = client.get("/api/v1/ui/amministrazione/prontezza-prodotto")
        client.get("/login")
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        administration = client.get("/api/v1/ui/amministrazione")
        response = client.get("/api/v1/ui/amministrazione/prontezza-prodotto")
        page = client.get("/amministrazione?tab=prontezza-prodotto")

    assert anonymous.status_code in {302, 401, 403}
    assert login.status_code == 200
    assert administration.status_code == 200
    assert any(action["id"] == "product-readiness" for action in administration.get_json()["actions"])
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["summary"]["total"] == 17
    assert payload["summary"]["verified"] == 0
    assert payload["contracts"]["writes"] == "none"
    assert payload["contracts"]["providerCalls"] is False
    assert payload["navigation"]["href"] == "/amministrazione?tab=prontezza-prodotto"
    assert all(item["status"] != "verificata" for item in payload["capabilities"])
    assert page.status_code == 200


def test_amministrazione_react_formatta_la_data_generata_del_registro() -> None:
    source = Path("frontend/src/components/AmministrazionePage.tsx").read_text(encoding="utf-8")

    assert "formatDateTimeIt(data.generated_at, 'Non disponibile')" in source
    assert "{data.generated_at || 'Non disponibile'}" not in source
