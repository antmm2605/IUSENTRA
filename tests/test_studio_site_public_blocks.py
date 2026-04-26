from pathlib import Path

from pct.studio_site_blocks import default_block
from web.app import create_app
from web.services.studio_site_runtime import studio_site_repository

from tests.test_studio_site import _cfg_web, _login_tenant_admin, _seed_tenant_admin, _write_studio_config


def test_render_pubblico_hero_slider(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)
    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")
        with app.app_context():
            repo = studio_site_repository()
            site = repo.get_site_by_tenant_slug(studio.slug)
            page = next(row for row in repo.list_pages(int(site["id"])) if row.get("is_home"))
            repo.save_page_blocks(int(site["id"]), int(page["id"]), [default_block("hero_slider")])
            repo.save_site(int(site["id"]), {"is_published": True, "is_active": True})
            public_slug = site["public_slug"]

    with app.test_client() as anonymous_client:
        response = anonymous_client.get(f"/web/{public_slug}/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "studio-site-hero-slider" in html
    assert "carousel-item active" in html
