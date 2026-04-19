from __future__ import annotations

from pct.tenant import GestioneTenant
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


def test_product_governance_surface_distingue_backend_effettivo_e_capability_piattaforma(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Studio SQLite", "studio-sqlite", db_config={"mode": "SQLITE"})
    app = create_app(cfg)

    with app.app_context():
        payload = build_product_governance_surface(selected_slug=studio.slug)

    assert payload["backend_policy"]["selected_studio"]["slug"] == studio.slug
    assert payload["backend_policy"]["selected_mode_label"] == "SQLite per studio"
    assert payload["backend_policy"]["effective_backend_label"] == "SQL locale tenant-aware"
    assert payload["backend_policy"]["alignment_status"] == "success"
    assert payload["backend_policy"]["aligned_domains"] == payload["backend_policy"]["structured_domains_total"]
    assert len(payload["backend_policy"]["explicit_exceptions"]) >= 3


def test_admin_governance_page_e_api_sono_accessibili_al_superadmin(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Studio SQLite", "studio-sqlite", db_config={"mode": "SQLITE"})
    app = create_app(cfg)

    with app.test_client() as client:
        client.get("/login")
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        page = client.get(f"/admin/governance?slug={studio.slug}")
        api = client.get(f"/admin/api/governance?slug={studio.slug}")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Governance prodotto" in html
    assert "Backend strutturato effettivo dello studio" in html
    assert "Matrice storage e read/write parity della piattaforma" in html
    assert "Percorso di migrazione JSON / SQLite -> PostgreSQL" in html
    assert "Superfici autorizzative" in html
    assert "SQL locale tenant-aware" in html

    assert api.status_code == 200
    payload = api.get_json()
    assert payload["storage"]["summary"]["domains_total"] >= 10
    assert payload["authorization"]["summary"]["surfaces_total"] >= 4
    assert payload["observability"]["summary"]["capabilities_total"] >= 4
    assert payload["backend_policy"]["selected_studio"]["slug"] == studio.slug
