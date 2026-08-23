from __future__ import annotations

from pct.storage import StudioDB
from pct.tenant import GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _seed_tenant_admin, _write_studio_config
from web.app import create_app


def test_data_consistency_api_usa_backend_sql_e_non_espone_mirror(tmp_path) -> None:
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _studio, admin = _seed_tenant_admin(app)
    tenant_paths = GestioneTenant(app.config["TENANTS_REGISTRY"]).percorsi_dati(_studio.slug)
    tenant_db = StudioDB.get(tenant_paths["STUDIO_DB"])
    tenant_db.conn.execute("INSERT INTO clienti (id, dati_json) VALUES ('cliente-tenant', '{}')")
    tenant_db.conn.commit()

    with app.test_client() as client:
        anonymous = client.get("/api/v1/ui/amministrazione/consistenza-dati")
        client.get("/login")
        login = client.post(
            "/login",
            data={"username": admin.username, "password": "PasswordSicura!123"},
            follow_redirects=True,
        )
        administration = client.get("/api/v1/ui/amministrazione")
        response = client.get("/api/v1/ui/amministrazione/consistenza-dati")
        page = client.get("/amministrazione?tab=consistenza-dati")

    assert anonymous.status_code in {302, 401, 403}
    assert login.status_code == 200
    assert administration.status_code == 200
    assert any(action["id"] == "consistenza-dati" for action in administration.get_json()["actions"])
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["sourceOfTruth"] == "sqlite"
    assert payload["contracts"]["writes"] == "none"
    assert payload["contracts"]["json_scanned"] is False
    assert payload["contracts"]["fallback_used"] is False
    assert any(domain["id"] == "outbox" for domain in payload["domains"])
    clienti = next(domain for domain in payload["domains"] if domain["id"] == "anagrafiche")
    assert clienti["records"] == 1
    assert page.status_code == 200
