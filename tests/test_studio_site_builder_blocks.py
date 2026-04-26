from pathlib import Path

from pct.studio_site_blocks import default_block, normalize_blocks
from web.app import create_app
from web.services.studio_site_runtime import studio_site_repository

from tests.test_studio_site import _cfg_web, _login_tenant_admin, _seed_tenant_admin, _write_studio_config


def _app_and_site(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)
    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")
    return app, studio, tenant_admin


def test_blocco_hero_slider_ha_default_professionali():
    block = default_block("hero_slider")
    assert block["type"] == "hero_slider"
    assert len(block["items"]) >= 2
    assert block["button_text"]


def test_builder_salva_blocchi_pagina(tmp_path: Path):
    app, studio, tenant_admin = _app_and_site(tmp_path)
    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        with app.app_context():
            site = studio_site_repository().get_site_by_tenant_slug(studio.slug)
            page = studio_site_repository().list_pages(int(site["id"]))[0]
        blocks = normalize_blocks([default_block("hero_slider"), default_block("gallery_grid")])
        response = client.post(f"/sito-studio/api/pages/{page['id']}/blocks", json={"blocks": blocks})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["blocks"][0]["type"] == "hero_slider"

        with app.app_context():
            saved = studio_site_repository().get_page(int(site["id"]), int(page["id"]))
            assert saved["body_json"][0]["type"] == "hero_slider"


def test_builder_pagina_espone_editor_visuale(tmp_path: Path):
    app, studio, tenant_admin = _app_and_site(tmp_path)
    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        response = client.get("/sito-studio/builder")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Sito Studio Builder Pro" in html
    assert "data-block-editor-list" in html
    assert "Salva bozza" in html
    assert "Redazione AI" in html
