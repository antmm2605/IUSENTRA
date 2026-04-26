from io import BytesIO
from pathlib import Path

from web.app import create_app
from web.services.studio_site_runtime import studio_site_repository

from tests.test_studio_site import _cfg_web, _login_tenant_admin, _seed_tenant_admin, _write_studio_config


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_upload_immagine_builder_crea_asset(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)
    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")
        response = client.post(
            "/sito-studio/api/assets/upload",
            data={
                "file": (BytesIO(PNG_1X1), "studio.png"),
                "alt_text": "Immagine della sede dello studio",
                "title": "Sede",
                "category": "home",
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["asset"]["alt_text"] == "Immagine della sede dello studio"

        assets = client.get("/sito-studio/api/assets").get_json()["assets"]
        assert len(assets) == 1

        delete = client.delete(f"/sito-studio/api/assets/{assets[0]['id']}")
        assert delete.status_code == 200
        assert delete.get_json()["ok"] is True

    with app.app_context():
        site = studio_site_repository().get_site_by_tenant_slug(studio.slug)
        assert studio_site_repository().list_assets(int(site["id"])) == []
