from __future__ import annotations

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.product_governance_surface import build_product_governance_surface


def test_product_governance_surface_espone_le_cinque_aree_prioritarie(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.app_context():
        payload = build_product_governance_surface()

    assert payload["headline"]["storage_domains"] >= 10
    assert payload["storage"]["summary"]["domains_total"] >= 10
    assert payload["authorization"]["summary"]["surfaces_total"] >= 4
    assert payload["migration"]["summary"]["phases_total"] == 4
    assert payload["e2e"]["summary"]["flows_total"] >= 4
    assert payload["observability"]["summary"]["capabilities_total"] >= 4


def test_admin_governance_page_e_api_sono_accessibili_al_superadmin(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.get("/login")
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        page = client.get("/admin/governance")
        api = client.get("/admin/api/governance")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Governance prodotto" in html
    assert "Matrice storage e read/write parity" in html
    assert "Percorso di migrazione JSON / SQLite -> PostgreSQL" in html
    assert "Superfici autorizzative" in html

    assert api.status_code == 200
    payload = api.get_json()
    assert payload["storage"]["summary"]["domains_total"] >= 10
    assert payload["authorization"]["summary"]["surfaces_total"] >= 4
    assert payload["observability"]["summary"]["capabilities_total"] >= 4
