from __future__ import annotations

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def test_end_to_end_studio_bootstrap_login_e_superfici_core(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        login_page = client.get("/login")
        assert login_page.status_code == 200

        login = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code == 302

        for path in (
            "/clienti",
            "/agenda",
            "/scadenziario",
            "/timesheet",
            "/admin/governance",
            "/admin/assistente-migrazione",
            "/admin/copertura-ai",
            "/legal-intelligence/news",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
