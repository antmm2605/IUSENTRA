from __future__ import annotations

from tests.test_web_bootstrap import _cfg_web, _seed_tenant_admin, _write_studio_config
from web.app import create_app


def test_end_to_end_studio_bootstrap_login_e_superfici_core(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    tenant_paths = (
        "/clienti",
        "/agenda",
        "/scadenziario",
        "/timesheet",
        "/ricerca-legale/news",
    )
    platform_paths = (
        "/admin/governance",
        "/admin/assistente-migrazione",
        "/admin/copertura-ai",
    )

    with app.test_client() as tenant_client:
        login_page = tenant_client.get("/login")
        assert login_page.status_code == 200
        login = tenant_client.post(
            "/login",
            data={
                "username": tenant_admin.username,
                "password": "PasswordSicura!123",
                "studio_slug": studio.slug,
            },
            follow_redirects=False,
        )
        assert login.status_code == 302

        for path in tenant_paths:
            response = tenant_client.get(path)
            assert response.status_code == 200, path

    with app.test_client() as platform_client:
        login = platform_client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code == 302

        for path in platform_paths:
            response = platform_client.get(path)
            assert response.status_code == 200, path
