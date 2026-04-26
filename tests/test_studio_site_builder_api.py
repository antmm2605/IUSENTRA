from pathlib import Path

from web.app import create_app
from web.services.studio_site_runtime import studio_site_repository

from tests.test_studio_site import _cfg_web, _login_tenant_admin, _seed_tenant_admin, _write_studio_config


def test_redazione_ai_crea_bozza_non_pubblicata(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)
    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")
        response = client.post(
            "/sito-studio/redazione-ai/articolo/genera",
            json={
                "argomento": "Separazione consensuale: documenti necessari",
                "area_diritto": "famiglia",
                "pubblico_destinatario": "famiglie",
                "tono": "divulgativo",
                "lunghezza": "media",
                "parole_chiave_seo": "separazione consensuale, documenti",
            },
        )
        assert response.status_code == 200
        job = response.get_json()["job"]
        assert job["status"] == "draft_generated"

        draft = client.post(f"/sito-studio/redazione-ai/articolo/{job['id']}/crea-bozza", json={})
        assert draft.status_code == 200
        article = draft.get_json()["article"]
        assert article["status"] == "draft"

        image = client.post(f"/sito-studio/redazione-ai/articolo/{article['id']}/genera-immagine", json={})
        assert image.status_code == 200
        assert image.get_json()["asset"]["url"].endswith(".svg")

        with app.app_context():
            site = studio_site_repository().get_site_by_tenant_slug(studio.slug)
            saved = studio_site_repository().get_article(int(site["id"]), int(article["id"]))
            assert saved["status"] == "draft"
            assert saved["cover_url"].endswith(".svg")


def test_api_builder_isolamento_tenant_su_pagina(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app, studio_slug="studio-uno", username="admin-uno")
    other, other_admin = _seed_tenant_admin(app, studio_nome="Studio Due", studio_slug="studio-due", username="admin-due")

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")
    with app.test_client() as client:
        _login_tenant_admin(client, other.slug, username=other_admin.username)
        client.get("/sito-studio/")

    with app.app_context():
        repo = studio_site_repository()
        other_site = repo.get_site_by_tenant_slug(other.slug)
        other_page = repo.list_pages(int(other_site["id"]))[0]

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        response = client.post(f"/sito-studio/api/pages/{other_page['id']}/blocks", json={"blocks": []})
        assert response.status_code == 400
        assert response.get_json()["ok"] is False
