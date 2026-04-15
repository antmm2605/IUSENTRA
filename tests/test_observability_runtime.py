from __future__ import annotations

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def test_runtime_metrics_endpoint_restituisce_payload_strutturato(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.get("/login")
        client.get("/api/health")
        response = client.get("/api/metriche/runtime")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["runtime"]["http"]["buckets"]
    assert "ocr" in payload
    assert "providers" in payload


def test_admin_osservabilita_page_e_accessibile_al_superadmin(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.get("/login")
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/admin/osservabilita")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Osservabilit" in html
    assert "Pipeline OCR" in html
