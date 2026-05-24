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


def test_sito_studio_modifica_articolo_react_full_salva_json_e_blocca_tenant_id(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")
        with app.app_context():
            site = studio_site_repository().get_site_by_tenant_slug(studio.slug)
            article = studio_site_repository().save_article(
                int(site["id"]),
                {
                    "title": "Articolo React",
                    "slug": "articolo-react",
                    "excerpt": "Sommario iniziale.",
                    "category": "Famiglia",
                    "tags_csv": "famiglia, studio",
                    "author_name": "Studio",
                    "body_json": [{"type": "rich_text", "title": "Contenuto", "text": "Testo iniziale."}],
                    "status": "draft",
                    "seo_title": "Articolo React",
                    "seo_description": "Descrizione iniziale.",
                },
            )

        shell = client.get(f"/sito-studio/articoli/{article['id']}/modifica")
        assert shell.status_code == 200
        shell_html = shell.get_data(as_text=True)
        assert '<html lang="it" class="react-shell-document">' in shell_html
        assert "studio_site/content_form.html" not in shell_html

        payload = client.get(f"/api/v1/ui/sito-studio/articoli/{article['id']}/modifica")
        assert payload.status_code == 200
        data = payload.get_json()
        assert data["ok"] is True
        assert data["article"]["title"] == "Articolo React"
        assert data["contracts"]["writes"] == "json_api"

        forbidden = client.post(
            f"/api/v1/ui/sito-studio/articoli/{article['id']}/modifica",
            json={"tenant_id": "studio-due", "title": "Forzato"},
        )
        assert forbidden.status_code == 400

        saved = client.post(
            f"/api/v1/ui/sito-studio/articoli/{article['id']}/modifica",
            json={
                "title": "Articolo React aggiornato",
                "slug": "articolo-react-aggiornato",
                "excerpt": "Sommario aggiornato.",
                "category": "Famiglia",
                "tagsCsv": "famiglia, aggiornato",
                "authorName": "Studio Legale",
                "bodyJsonText": '[{"type":"rich_text","title":"Contenuto","text":"Testo aggiornato."}]',
                "status": "published",
                "publishedAt": "2026-05-24",
                "seoTitle": "Articolo React aggiornato",
                "seoDescription": "Descrizione aggiornata.",
            },
        )
        assert saved.status_code == 200
        result = saved.get_json()
        assert result["ok"] is True
        assert result["item"]["status"] == "published"

        with app.app_context():
            site = studio_site_repository().get_site_by_tenant_slug(studio.slug)
            updated = studio_site_repository().get_article(int(site["id"]), int(article["id"]))
            assert updated["title"] == "Articolo React aggiornato"
            assert updated["slug"] == "articolo-react-aggiornato"
            assert updated["status"] == "published"
            assert updated["body_json"][0]["text"] == "Testo aggiornato."


def test_api_react_builder_salva_setup_seo_e_duplica_pagina(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")

        site_response = client.post(
            "/api/v1/ui/sito-studio/builder/site",
            json={
                "siteName": "Studio Legale Verdi",
                "claim": "Assistenza legale chiara",
                "contactEmail": "studio@example.test",
                "contactPhone": "+39 010 000000",
                "address": "Via Roma 1",
                "city": "Genova",
                "province": "GE",
                "cookieBannerEnabled": True,
            },
        )
        assert site_response.status_code == 200
        site_payload = site_response.get_json()["payload"]
        assert site_payload["site"]["siteName"] == "Studio Legale Verdi"
        assert site_payload["site"]["contactEmail"] == "studio@example.test"
        assert site_payload["site"]["cookieBannerEnabled"] is True

        design_response = client.post(
            "/api/v1/ui/sito-studio/builder/design",
            json={
                "theme_template": "classic_legal",
                "primary": "#1f3f6d",
                "accent": "#b38b55",
                "font_preset": "garamond_legal",
                "font_size_base": "17px",
                "heading_size": "42px",
                "section_title_size": "30px",
                "animation": "fade-up",
                "card_shadow": "soft",
                "fixed_header": "true",
                "button_hover": "true",
                "section_spacing": "36px",
                "card_padding": "24px",
                "button_radius": "10px",
                "section_divider": "accent-line",
                "image_treatment": "editorial",
            },
        )
        assert design_response.status_code == 200
        design_theme = design_response.get_json()["payload"]["theme"]
        assert design_theme["typography"]["font_preset"] == "garamond_legal"
        assert design_theme["typography"]["font_size_base"] == "17px"
        assert design_theme["typography"]["heading_size"] == "42px"
        assert design_theme["layout"]["section_spacing"] == "36px"
        assert design_theme["layout"]["card_padding"] == "24px"
        assert design_theme["layout"]["button_radius"] == "10px"
        assert design_theme["effects"]["card_shadow"] == "soft"
        assert design_theme["effects"]["fixed_header"] == "true"
        assert design_theme["effects"]["button_hover"] == "true"
        assert design_theme["effects"]["section_divider"] == "accent-line"
        assert design_theme["effects"]["image_treatment"] == "editorial"

        create_response = client.post(
            "/api/v1/ui/sito-studio/builder/pages",
            json={"title": "Servizi", "slug": "servizi", "excerpt": "Aree di assistenza dello studio."},
        )
        assert create_response.status_code == 200
        page_id = create_response.get_json()["page"]["id"]
        page_response = client.post(
            f"/api/v1/ui/sito-studio/builder/pages/{page_id}/settings",
            json={
                "title": "Servizi legali",
                "slug": "servizi-legali",
                "excerpt": "Aree di assistenza dello studio",
                "showInMenu": True,
                "home": False,
                "seoTitle": "Studio Legale Verdi - Genova",
                "seoDescription": "Consulenza legale professionale a Genova.",
            },
        )
        assert page_response.status_code == 200
        page_payload = page_response.get_json()["payload"]
        assert page_payload["activePage"]["slug"] == "servizi-legali"
        assert page_payload["activePage"]["seoTitle"] == "Studio Legale Verdi - Genova"

        duplicate_response = client.post(f"/api/v1/ui/sito-studio/builder/pages/{page_id}/duplicate", json={})
        assert duplicate_response.status_code == 200
        duplicate_payload = duplicate_response.get_json()["payload"]
        duplicate_titles = [page["title"] for page in duplicate_payload["pages"]]
        assert "Copia di Servizi legali" in duplicate_titles
