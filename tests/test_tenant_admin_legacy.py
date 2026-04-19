import json
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.tenant import DbMode, GestioneTenant, StudioLegale
from web.app import create_app
from web.services.storage_runtime import get_request_studio_db


def test_studio_legale_legacy_db_config_string_non_rompe_database():
    studio = StudioLegale.from_dict(
        {
            "slug": "antonella-mammola",
            "nome": "Studio Antonella Mammola",
            "db_config": "LOCAL",
            "branding": "legacy-string",
            "moduli_override": "fascicoli,clienti",
        }
    )

    assert studio.database.mode == DbMode.LOCAL
    assert studio.branding == {}
    assert studio.moduli_override == ["fascicoli", "clienti"]


def test_admin_dettaglio_studio_renderizza_anche_con_db_legacy(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    app = create_app(
        {
            "TESTING": True,
            "TENANTS_REGISTRY": str(registry_path),
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
            "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
            "BOOTSTRAP_ADMIN_PASSWORD": "superpass123",
        }
    )

    client = app.test_client()
    client.post(
        "/login",
        data={"username": "admin", "password": "superpass123"},
        follow_redirects=False,
    )
    resp = client.get("/admin/studi/antonella-mammola")

    assert resp.status_code == 200
    assert b"Antonella Mammola" in resp.data


def test_gestione_tenant_get_supporta_registry_con_chiave_diversa_dallo_slug(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tm = GestioneTenant(str(registry_path))
    studio = tm.get("antonella-mammola")

    assert studio is not None
    assert studio.slug == "antonella-mammola"


def test_percorsi_dati_usano_storage_key_legacy_quando_presente(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "storage_key": "tenant-8bf98719c459",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": {
                        "mode": "LOCAL",
                        "directory_dati": str(tmp_path / "tenants" / "tenant-8bf98719c459"),
                    },
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tm = GestioneTenant(str(registry_path))
    paths = tm.percorsi_dati("antonella-mammola")

    assert "tenant-8bf98719c459" in paths["CLIENTI_DB"]
    assert "tenant-8bf98719c459" in paths["AUTH_DB"]


def test_reconcile_storage_aliases_ripopola_l_alias_slug_quando_il_canonico_ha_i_dati(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "storage_key": "tenant-8bf98719c459",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": {"mode": "SQLITE"},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tm = GestioneTenant(str(registry_path))
    canonical_paths = tm.percorsi_dati("antonella-mammola")
    canonical_fascicoli = Path(canonical_paths["FASCICOLI_DB"])
    canonical_config = Path(canonical_paths["CONFIG_STUDIO_DB"])
    canonical_studio_db = Path(canonical_paths["STUDIO_DB"])
    canonical_fascicoli.parent.mkdir(parents=True, exist_ok=True)
    canonical_config.parent.mkdir(parents=True, exist_ok=True)
    canonical_fascicoli.write_text(
        json.dumps([{"id": "f-001", "numero": "2026/001"}], ensure_ascii=False),
        encoding="utf-8",
    )
    canonical_config.write_text(
        json.dumps({"studio": {"nome": "Studio Legale Montagnese"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    canonical_studio_db.parent.mkdir(parents=True, exist_ok=True)
    canonical_studio_db.write_text("sqlite-placeholder", encoding="utf-8")

    alias_root = tmp_path / "tenants" / "antonella-mammola"
    (alias_root / "fascicoli").mkdir(parents=True, exist_ok=True)
    (alias_root / "config").mkdir(parents=True, exist_ok=True)

    report = tm.reconcile_storage_aliases("antonella-mammola")

    alias_fascicoli = alias_root / "fascicoli" / "fascicoli.json"
    alias_config = alias_root / "config" / "studio.json"
    alias_studio_db = alias_root / "studio.db"

    assert report["ok"] is True
    assert report["backfilled_alias_files"]
    assert alias_fascicoli.exists()
    assert alias_config.exists()
    assert alias_studio_db.exists()
    assert json.loads(alias_fascicoli.read_text(encoding="utf-8"))[0]["numero"] == "2026/001"
    assert json.loads(alias_config.read_text(encoding="utf-8"))["studio"]["nome"] == "Studio Legale Montagnese"


def test_admin_dettaglio_studio_mostra_storage_root_canonico_e_non_slug_legacy(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "storage_key": "tenant-8bf98719c459",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    app = create_app(
        {
            "TESTING": True,
            "TENANTS_REGISTRY": str(registry_path),
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
            "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
            "BOOTSTRAP_ADMIN_PASSWORD": "superpass123",
        }
    )

    client = app.test_client()
    client.post(
        "/login",
        data={"username": "admin", "password": "superpass123"},
        follow_redirects=False,
    )
    resp = client.get("/admin/studi/antonella-mammola")

    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "tenant-8bf98719c459" in html
    assert "./data/tenants/antonella-mammola/" not in html


def test_superadmin_ha_superficie_piattaforma_separata_dagli_utenti_studio(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    app = create_app(
        {
            "TESTING": True,
            "TENANTS_REGISTRY": str(registry_path),
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
            "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
            "BOOTSTRAP_ADMIN_PASSWORD": "superpass123",
        }
    )

    tm = GestioneTenant(str(registry_path))
    tenant_paths = tm.percorsi_dati("antonella-mammola")
    tenant_users = GestioneUtenti(
        db_path=tenant_paths["AUTH_DB"],
        audit_path=tenant_paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    tenant_users.crea(
        username="adminstudio",
        password="tenantpass123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug="antonella-mammola",
    )

    client = app.test_client()
    login = client.post(
        "/login",
        data={"username": "admin", "password": "superpass123"},
        follow_redirects=False,
    )
    assert login.status_code == 302

    response = client.get("/admin/utenti-piattaforma")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Account piattaforma" in html
    assert "admin" in html
    assert "adminstudio" not in html


def test_superadmin_globale_ignora_ruolo_stale_nel_sql_locale(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    app = create_app(
        {
            "TESTING": True,
            "TENANTS_REGISTRY": str(registry_path),
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
            "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
            "BOOTSTRAP_ADMIN_PASSWORD": "superpass123",
        }
    )

    with app.app_context():
        studio_db = get_request_studio_db(app.config["CLIENTI_DB"])
        assert studio_db is not None

        utenti_sqlite = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
            crea_admin_se_vuoto=False,
            studio_db=studio_db,
        )
        utenti_sqlite.crea(
            username="admin",
            password="superpass123",
            ruolo=RuoloUtente.AMMINISTRATORE,
            tenant_slug="",
            must_change_password=False,
        )

    client = app.test_client()
    login = client.post(
        "/login",
        data={"username": "admin", "password": "superpass123"},
        follow_redirects=False,
    )
    assert login.status_code == 302

    response = client.get("/admin/utenti-piattaforma")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Account piattaforma" in html
    assert "admin" in html
    assert "adminstudio" not in html


def test_superadmin_globale_viene_reindirizzato_fuori_dalla_gestione_utenti_legacy(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    app = create_app(
        {
            "TESTING": True,
            "TENANTS_REGISTRY": str(registry_path),
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
            "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
            "BOOTSTRAP_ADMIN_PASSWORD": "superpass123",
        }
    )

    client = app.test_client()
    login = client.post(
        "/login",
        data={"username": "admin", "password": "superpass123"},
        follow_redirects=False,
    )
    assert login.status_code == 302

    response = client.get("/utenti/nuovo", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/utenti-piattaforma")


def test_admin_tenant_non_vede_ne_accetta_superadmin_nella_route_legacy_utenti(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "antonella-mammola",
                    "nome": "Studio Antonella Mammola",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    app = create_app(
        {
            "TESTING": True,
            "MULTI_TENANT": True,
            "TENANTS_REGISTRY": str(registry_path),
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
            "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
            "BOOTSTRAP_ADMIN_PASSWORD": "superpass123",
        }
    )

    tm = GestioneTenant(str(registry_path))
    studio = tm.get("antonella-mammola")
    assert studio is not None
    tenant_paths = tm.percorsi_dati(studio.slug)
    tenant_users = GestioneUtenti(
        db_path=tenant_paths["AUTH_DB"],
        audit_path=tenant_paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    tenant_users.crea(
        username="adminstudio",
        password="tenantpass123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug=studio.slug,
        must_change_password=False,
    )

    client = app.test_client()
    login = client.post(
        "/login",
        data={
            "username": "adminstudio",
            "password": "tenantpass123",
            "studio_slug": studio.slug,
        },
        follow_redirects=False,
    )
    assert login.status_code == 302

    form_response = client.get("/utenti/nuovo")
    html = form_response.get_data(as_text=True)

    assert form_response.status_code == 200
    assert 'option value="SUPERADMIN"' not in html

    post_response = client.post(
        "/utenti/nuovo",
        data={
            "username": "tentativo-superadmin",
            "password": "Password123!",
            "ruolo": "SUPERADMIN",
            "email": "tenant@example.com",
        },
        follow_redirects=True,
    )
    post_html = post_response.get_data(as_text=True)

    assert post_response.status_code == 200
    assert "Il ruolo SUPERADMIN si gestisce solo dal pannello piattaforma." in post_html
    assert tenant_users.get_by_username("tentativo-superadmin") is None


def test_reset_password_piattaforma_aggiorna_l_unico_superadmin(tmp_path):
    registry_path = tmp_path / "tenants.json"
    registry_path.write_text("{}", encoding="utf-8")

    app = create_app(
        {
            "TESTING": True,
            "TENANTS_REGISTRY": str(registry_path),
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
            "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
            "BOOTSTRAP_ADMIN_PASSWORD": "superpass123",
        }
    )

    client = app.test_client()
    login = client.post(
        "/login",
        data={"username": "admin", "password": "superpass123"},
        follow_redirects=False,
    )
    assert login.status_code == 302

    platform_users = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=None,
    )
    superadmin = platform_users.get_by_username("admin")
    assert superadmin is not None

    response = client.post(
        f"/admin/utenti-piattaforma/{superadmin.id}/reset-password",
        data={"nuova_password": "NuovaPiattaforma123!"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    refreshed_users = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=None,
    )
    assert refreshed_users.autentica("admin", "NuovaPiattaforma123!") is not None
