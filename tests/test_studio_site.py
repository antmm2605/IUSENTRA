import json
from pathlib import Path
from urllib.parse import urlparse

from pct.agenda import Agenda
from pct.auth import GestioneUtenti, RuoloUtente
from pct.storage import StudioDB
from pct.tenant import GestioneTenant
from web.app import create_app
from web.services.studio_site_runtime import studio_site_repository
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Sito Test",
                    "avvocato": "Avv. Sito Test",
                    "indirizzo": "Via Roma 20",
                    "city": "Taurianova",
                    "province": "RC",
                    "telefono": "0966 654321",
                    "email": "studio.sito@example.it",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH": str(tmp_path / "auth" / "bootstrap_admin.json"),
        "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        "CONDIVISIONI_DB": str(tmp_path / "clienti" / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "fascicoli" / "archivio"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search" / "index.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "soggetti" / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "import_pst"),
        "VALIDATION_RUNS_DB": str(tmp_path / "intelligence" / "validation_runs.json"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(tmp_path / "intelligence" / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "workspace_intelligence.json"),
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(tmp_path / "template_atti" / "editor_layout.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(tmp_path / "fatturazione" / "parcelle.json"),
        "TIMESHEET_DB": str(tmp_path / "timesheet" / "entries.json"),
        "LOCAL_AI_DB": str(tmp_path / "intelligence" / "local_ai.db"),
        "LOCAL_AI_POLICY": str(Path(__file__).resolve().parents[1] / "config" / "ai-policy.json"),
        "LOCAL_AI_MODELS_DIR": str(tmp_path / "intelligence" / "models"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "PORTALE_DB": str(tmp_path / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(tmp_path / "portale" / "uploads"),
        "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
    }


def _assert_react_shell_html(html: str) -> None:
    assert 'class="react-shell-document"' in html
    assert 'id="iusentra-react-bootstrap"' in html
    assert 'id="root"' in html


def _seed_tenant_admin(
    app,
    *,
    studio_nome: str = "Studio Sito Test",
    studio_slug: str = "studio-sito-test",
    username: str = "studio-admin",
    password: str = "PasswordSicura!123",
):
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.get(studio_slug) or tm.crea(studio_nome, studio_slug, db_config={"mode": "SQLITE"})
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio.slug)
    paths = tm.percorsi_dati(studio.slug)
    _write_studio_config(Path(paths["CONFIG_STUDIO_DB"]))
    utenti = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=StudioDB.get(paths["STUDIO_DB"]),
    )
    utenti_json = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=None,
    )
    esistente = utenti.get_by_username(username)
    if esistente is None:
        esistente = utenti.crea(
            username=username,
            password=password,
            ruolo=RuoloUtente.AMMINISTRATORE,
            tenant_slug=studio.slug,
            must_change_password=False,
        )
    if utenti_json.get_by_username(username) is None:
        utenti_json.importa_utente_esistente(esistente, tenant_slug=studio.slug, preserve_id=True)
    return studio, esistente


def _login_tenant_admin(client, studio_slug: str, username: str = "studio-admin", password: str = "PasswordSicura!123"):
    return client.post(
        "/login",
        data={"username": username, "password": password, "studio_slug": studio_slug},
        follow_redirects=False,
    )


def _settings_payload(site: dict, **overrides) -> dict[str, str]:
    bool_fields = {
        "is_published",
        "is_active",
        "show_legal_tools",
        "show_applications",
        "show_legal_news",
    }
    base = {
        "studio_nome": str(site.get("studio_nome") or ""),
        "site_name": str(site.get("site_name") or ""),
        "public_slug": str(site.get("public_slug") or ""),
        "site_title": str(site.get("site_title") or ""),
        "site_description": str(site.get("site_description") or ""),
        "hero_claim": str(site.get("hero_claim") or ""),
        "contact_email": str(site.get("contact_email") or ""),
        "contact_phone": str(site.get("contact_phone") or ""),
        "whatsapp_number": str(site.get("whatsapp_number") or ""),
        "address": str(site.get("address") or ""),
        "city": str(site.get("city") or ""),
        "province": str(site.get("province") or ""),
        "zip_code": str(site.get("zip_code") or ""),
        "footer_text": str(site.get("footer_text") or ""),
        "facebook_url": str(site.get("facebook_url") or ""),
        "instagram_url": str(site.get("instagram_url") or ""),
        "linkedin_url": str(site.get("linkedin_url") or ""),
        "primary_color": str(site.get("primary_color") or "#1d4ed8"),
        "secondary_color": str(site.get("secondary_color") or "#0f172a"),
        "accent_color": str(site.get("accent_color") or "#16a34a"),
    }
    effective = {**base, **{k: v for k, v in overrides.items() if k not in bool_fields}}
    for field in bool_fields:
        value = overrides[field] if field in overrides else bool(site.get(field))
        if value:
            effective[field] = "1"
    return effective


def test_sito_studio_inizializza_seed_e_consente_preview_bozza(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        login = _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        assert login.status_code == 302
        response = client.get("/sito-studio/")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert '<html lang="it" class="react-shell-document">' in html
        assert '<div id="root"></div>' in html

        with app.app_context():
            repo = studio_site_repository()
            site = repo.get_site_by_tenant_slug(studio.slug)
            assert site is not None
            assert repo.site_stats(int(site["id"]))["pages"] >= 1
            assert len(repo.list_services(int(site["id"]))) >= 1
            assert len(repo.list_offices(int(site["id"]))) >= 1
            assert len(repo.list_booking_rules(int(site["id"]))) >= 1
            public_slug = str(site["public_slug"])

        preview = client.get(f"/web/{public_slug}/")
        assert preview.status_code == 200

    with app.test_client() as anonymous_client:
        hidden = anonymous_client.get(f"/web/{public_slug}/")
    assert hidden.status_code == 404


def test_sito_studio_flag_opzionali_controllano_le_route_pubbliche(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")

        with app.app_context():
            site = studio_site_repository().get_site_by_tenant_slug(studio.slug)
            assert site is not None
            public_slug = str(site["public_slug"])

        response = client.post(
            "/sito-studio/impostazioni",
            data=_settings_payload(site, is_published=True, is_active=True),
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.test_client() as anonymous_client:
            assert anonymous_client.get(f"/web/{public_slug}/").status_code == 200
            assert anonymous_client.get(f"/web/{public_slug}/strumenti-legali").status_code == 404
            assert anonymous_client.get(f"/web/{public_slug}/applicazioni").status_code == 404
            assert anonymous_client.get(f"/web/{public_slug}/news-giuridiche").status_code == 404

        response = client.post(
            "/sito-studio/impostazioni",
            data=_settings_payload(
                site,
                is_published=True,
                is_active=True,
                show_legal_tools=True,
                show_applications=True,
                show_legal_news=True,
            ),
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.test_client() as anonymous_client:
            assert anonymous_client.get(f"/web/{public_slug}/strumenti-legali").status_code == 200
            assert anonymous_client.get(f"/web/{public_slug}/applicazioni").status_code == 200
            assert anonymous_client.get(f"/web/{public_slug}/news-giuridiche").status_code == 200

        response = client.post(
            "/sito-studio/impostazioni",
            data=_settings_payload(site, is_published=True, is_active=True),
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.test_client() as anonymous_client:
            assert anonymous_client.get(f"/web/{public_slug}/strumenti-legali").status_code == 404
            assert anonymous_client.get(f"/web/{public_slug}/applicazioni").status_code == 404
            assert anonymous_client.get(f"/web/{public_slug}/news-giuridiche").status_code == 404


def test_sito_studio_contatti_pubblici_persistono(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")
        with app.app_context():
            site = studio_site_repository().get_site_by_tenant_slug(studio.slug)
            assert site is not None
            public_slug = str(site["public_slug"])
        client.post(
            "/sito-studio/impostazioni",
            data=_settings_payload(site, is_published=True, is_active=True),
            follow_redirects=True,
        )

    with app.test_client() as anonymous_client:
        response = anonymous_client.post(
            f"/web/{public_slug}/contatti",
            data={
                "full_name": "Mario Rossi",
                "email": "mario.rossi@example.it",
                "phone": "3331234567",
                "subject": "Richiesta consulenza",
                "message": "Vorrei fissare un incontro sul mio caso.",
                "privacy_accepted": "1",
            },
            follow_redirects=True,
        )
    assert response.status_code == 200
    assert "Richiesta inviata correttamente allo studio." in response.get_data(as_text=True)

    with app.app_context():
        repo = studio_site_repository()
        site = repo.get_site_by_tenant_slug(studio.slug)
        submissions = repo.list_contact_submissions(int(site["id"]))
        assert len(submissions) == 1
        assert submissions[0]["full_name"] == "Mario Rossi"


def test_sito_studio_prenotazione_approvata_si_sincronizza_in_agenda(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")

        with app.app_context():
            repo = studio_site_repository()
            site = repo.get_site_by_tenant_slug(studio.slug)
            assert site is not None
            public_slug = str(site["public_slug"])
        client.post(
            "/sito-studio/impostazioni",
            data=_settings_payload(site, is_published=True, is_active=True),
            follow_redirects=True,
        )

    with app.app_context():
        repo = studio_site_repository()
        site = repo.get_site_by_tenant_slug(studio.slug)
        office = repo.list_offices(int(site["id"]))[0]
        available_slots = repo.available_slots(int(site["id"]), "2026-04-28", office_id=int(office["id"]))
        assert available_slots
        requested_time = str(available_slots[0]["time"])

    with app.test_client() as anonymous_client:
        response = anonymous_client.post(
            f"/web/{public_slug}/prenota",
            data={
                "office_id": str(office["id"]),
                "customer_name": "Lucia Bianchi",
                "customer_email": "lucia.bianchi@example.it",
                "customer_phone": "3337654321",
                "requested_date": "2026-04-28",
                "requested_time": requested_time,
                "subject": "Prima consulenza",
                "notes": "Richiesta su accesso agli atti.",
                "privacy_accepted": "1",
            },
            follow_redirects=True,
        )
    assert response.status_code == 200
    assert "Richiesta appuntamento registrata." in response.get_data(as_text=True)

    with app.app_context():
        repo = studio_site_repository()
        site = repo.get_site_by_tenant_slug(studio.slug)
        booking_requests = repo.list_booking_requests(int(site["id"]))
        assert len(booking_requests) == 1
        booking_request = booking_requests[0]

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        response = client.post(
            f"/sito-studio/prenotazioni/{booking_request['id']}/approva",
            follow_redirects=True,
        )
    assert response.status_code == 200
    assert "Prenotazioni dal sito" in response.get_data(as_text=True)

    with app.app_context():
        repo = studio_site_repository()
        updated = repo.get_booking_request(int(site["id"]), int(booking_request["id"]))
        assert updated is not None
        assert updated["status"] == "approved"
        assert updated["agenda_event_id"]

    tenant_paths = GestioneTenant(app.config["TENANTS_REGISTRY"]).percorsi_dati(studio.slug)
    agenda = Agenda(
        db_path=tenant_paths["AGENDA_DB"],
        studio_db=StudioDB.get(tenant_paths["STUDIO_DB"]),
    )
    external_uid = f"site-studio-booking-{site['id']}-{booking_request['id']}"
    appointment = agenda.trova_per_uid_esterno(external_uid, provider="site_studio")
    assert appointment is not None
    assert "Lucia Bianchi" in appointment.titolo


def test_console_superadmin_siti_studio_espone_il_catalogo(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as tenant_client:
        _login_tenant_admin(tenant_client, studio.slug, username=tenant_admin.username)
        tenant_client.get("/sito-studio/")

    with app.test_client() as platform_client:
        login = platform_client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert login.status_code == 302
        response = platform_client.get("/admin/siti-studio/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Siti Studio" in html
    assert "Studio Sito Test" in html



def test_sito_studio_builder_pro_template_tokens_e_sito_unico_per_tenant(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        response = client.get("/sito-studio/builder")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        _assert_react_shell_html(html)

        apply_response = client.post(
            "/sito-studio/builder/applica-template",
            data={"template_code": "boutique_elegante"},
            follow_redirects=True,
        )
        assert apply_response.status_code == 200

        with app.app_context():
            repo = studio_site_repository()
            site = repo.get_site_by_tenant_slug(studio.slug)
            assert site is not None
            first_site_id = int(site["id"])
            assert site["theme_template"] == "boutique_elegante"
            assert site["design_tokens_json"]["primary"] == "#2b2118"
            assert len(repo.list_theme_presets()) >= 8

            paths = GestioneTenant(app.config["TENANTS_REGISTRY"]).percorsi_dati(studio.slug)
            utenti = GestioneUtenti(
                db_path=paths["AUTH_DB"],
                audit_path=paths["AUDIT_DB"],
                secret_key=app.secret_key,
                crea_admin_se_vuoto=False,
                studio_db=StudioDB.get(paths["STUDIO_DB"]),
            )
            utenti_json = GestioneUtenti(
                db_path=paths["AUTH_DB"],
                audit_path=paths["AUDIT_DB"],
                secret_key=app.secret_key,
                crea_admin_se_vuoto=False,
                studio_db=None,
            )
            second = utenti.crea(
                username="studio-admin-2",
                password="PasswordSicura!123",
                ruolo=RuoloUtente.AMMINISTRATORE,
                tenant_slug=studio.slug,
                must_change_password=False,
            )
            utenti_json.importa_utente_esistente(second, tenant_slug=studio.slug, preserve_id=True)

    with app.test_client() as second_client:
        login = _login_tenant_admin(second_client, studio.slug, username="studio-admin-2")
        assert login.status_code == 302
        response = second_client.get("/sito-studio/")
        assert response.status_code == 200

    with app.app_context():
        repo = studio_site_repository()
        site = repo.get_site_by_tenant_slug(studio.slug)
        assert site is not None
        assert int(site["id"]) == first_site_id
        assert len(repo.list_sites(query="Studio Sito Test")) == 1


def test_sito_studio_builder_generazione_validazione_e_render_pubblico(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, tenant_admin = _seed_tenant_admin(app)

    with app.test_client() as client:
        _login_tenant_admin(client, studio.slug, username=tenant_admin.username)
        client.get("/sito-studio/")
        response = client.post(
            "/sito-studio/builder/genera-automaticamente",
            data={"template": "civilista", "site_type": "civile", "style": "sobrio"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        _assert_react_shell_html(response.get_data(as_text=True))

        validation = client.post("/sito-studio/builder/valida", headers={"Accept": "application/json"})
        assert validation.status_code == 200
        payload = validation.get_json()
        assert payload["ok"] is True
        assert set(payload["validation"]).issuperset({"seo", "accessibility", "privacy", "deontology"})

        with app.app_context():
            repo = studio_site_repository()
            site = repo.get_site_by_tenant_slug(studio.slug)
            assert site is not None
            public_slug = str(site["public_slug"])
            repo.save_site(int(site["id"]), {"is_published": True, "is_active": True})

    with app.test_client() as anonymous_client:
        home = anonymous_client.get(f"/web/{public_slug}/")
        assert home.status_code == 200
        html = home.get_data(as_text=True)
        jsonld_start = '<script type="application/ld+json">'
        jsonld_end = "</script>"
        jsonld_start_index = html.index(jsonld_start) + len(jsonld_start)
        jsonld_end_index = html.index(jsonld_end, jsonld_start_index)
        schema_payload = json.loads(html[jsonld_start_index:jsonld_end_index])
        schema_context = urlparse(schema_payload["@context"])
        assert (schema_context.scheme, schema_context.netloc) == ("https", "schema.org")
        assert "og:title" in html
        assert "studio-site-nav-toggle" in html
        assert f"/web/{public_slug}/sitemap.xml" in anonymous_client.get(f"/web/{public_slug}/robots.txt").get_data(as_text=True)
        assert anonymous_client.get(f"/web/{public_slug}/sitemap.xml").status_code == 200
