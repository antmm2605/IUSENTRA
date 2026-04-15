import json
import sqlite3
from pathlib import Path

from flask import g

from pct.auth import GestioneUtenti, RuoloUtente
from pct.storage import StudioDB
from pct.tenant import DatabaseConfig, DbMode, GestioneTenant
from web.bootstrap.flask_app_factory import create_flask_app
from web.app import create_app
from web.services.core_runtime import build_core_runtime
from web.services.storage_runtime import get_request_storage_runtime, get_request_studio_db
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "studio": {"nome": "Studio Test Storage"},
                "pec": {},
                "smtp": {},
                "scheduler": {},
                "ai": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _cfg(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test-storage",
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "fascicoli" / "archivio"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search" / "index.db"),
        "PRIVACY_DB": str(tmp_path / "privacy" / "registro.json"),
        "NOTIFICHE_LOG": str(tmp_path / "notifiche" / "log.json"),
        "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
    }


def _login_superadmin(client, *, username: str, password: str) -> None:
    response = client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 302


def _root_utenti_manager(app):
    return GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=get_request_studio_db(app.config["CLIENTI_DB"]),
    )


def test_database_config_normalizes_storage_modes():
    assert DatabaseConfig.from_dict("LOCAL").normalized_mode == DbMode.JSON
    assert DatabaseConfig.from_dict("JSON").is_json is True
    assert DatabaseConfig.from_dict("SQLITE3").normalized_mode == DbMode.SQLITE
    assert DatabaseConfig.from_dict("POSTGRES").normalized_mode == DbMode.POSTGRESQL
    assert DatabaseConfig().normalized_mode == DbMode.SQLITE


def test_gestione_tenant_provision_storage_backend_creates_sqlite_and_manifest(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Demo", "studio-demo", db_config={"mode": "SQLITE"})
    tm.aggiorna_db_config(studio.slug, DatabaseConfig(mode=DbMode.SQLITE))

    result = tm.provision_storage_backend(studio.slug, migrate_existing=False)
    paths = tm.percorsi_dati(studio.slug)
    manifest = json.loads(Path(paths["STORAGE_CONFIG"]).read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert Path(paths["STUDIO_DB"]).exists()
    assert manifest["selected_mode"] == DbMode.SQLITE
    assert manifest["runtime_kind"] == "sqlite"
    assert manifest["effective_runtime_kind"] == "sqlite"
    assert manifest["activation_state"] == "active"


def test_superadmin_can_create_studio_with_sqlite_strategy(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    utenti = _root_utenti_manager(app)
    superadmin = utenti.crea(
        username="superadmin",
        password="superpass123",
        ruolo=RuoloUtente.SUPERADMIN,
        tenant_slug="",
        must_change_password=False,
    )

    client = app.test_client()
    _login_superadmin(client, username=superadmin.username, password="superpass123")

    response = client.post(
        "/admin/studi/nuovo",
        data={
            "nome": "Studio SQLite",
            "slug": "studio-sqlite",
            "piano": "TRIAL",
            "admin_username": "amministratore",
            "admin_password": "PasswordSicura!123",
            "db_mode": "SQLITE",
        },
        follow_redirects=False,
    )

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.get("studio-sqlite")
    paths = tm.percorsi_dati("studio-sqlite")
    conn = sqlite3.connect(paths["STUDIO_DB"])
    utenti_count = conn.execute("SELECT COUNT(*) FROM utenti").fetchone()[0]
    conn.close()

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/studi/studio-sqlite")
    assert studio is not None
    assert studio.database.normalized_mode == DbMode.SQLITE
    assert Path(paths["STUDIO_DB"]).exists()
    assert utenti_count >= 1


def test_request_storage_runtime_uses_tenant_sqlite_profile(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    clienti_path = tmp_path / "tenants" / "demo" / "clienti" / "anagrafica.json"
    clienti_path.parent.mkdir(parents=True, exist_ok=True)
    clienti_path.write_text("{}", encoding="utf-8")

    with app.test_request_context("/"):
        g.tenant = GestioneTenant(str(tmp_path / "tenants.json")).crea(
            "Studio Tenant",
            "demo",
            db_config={"mode": "SQLITE"},
        )
        profile = get_request_storage_runtime(str(clienti_path))
        studio_db = get_request_studio_db(str(clienti_path))

    assert profile.selected_mode == DbMode.SQLITE
    assert profile.uses_sqlite is True
    assert profile.effective_mode == DbMode.SQLITE
    assert studio_db is not None
    assert studio_db.db_path == (tmp_path / "tenants" / "demo" / "studio.db").resolve()


def test_request_storage_runtime_external_sql_keeps_json_backend_until_migration(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    clienti_path = tmp_path / "tenants" / "pg-demo" / "clienti" / "anagrafica.json"
    clienti_path.parent.mkdir(parents=True, exist_ok=True)
    clienti_path.write_text("{}", encoding="utf-8")

    with app.test_request_context("/"):
        g.tenant = GestioneTenant(str(tmp_path / "tenants.json")).crea(
            "Studio Cloud",
            "pg-demo",
            db_config={"mode": "POSTGRESQL"},
        )
        profile = get_request_storage_runtime(str(clienti_path))
        studio_db = get_request_studio_db(str(clienti_path))

    assert profile.selected_mode == DbMode.POSTGRESQL
    assert profile.effective_mode == DbMode.JSON
    assert profile.external_sql_configured is True
    assert studio_db is None


def test_request_storage_runtime_default_operational_prefers_sqlite(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    clienti_path = tmp_path / "clienti" / "anagrafica.json"
    clienti_path.parent.mkdir(parents=True, exist_ok=True)
    clienti_path.write_text("{}", encoding="utf-8")

    with app.test_request_context("/"):
        profile = get_request_storage_runtime(str(clienti_path))
        studio_db = get_request_studio_db(str(clienti_path))

    assert profile.selected_mode == DbMode.SQLITE
    assert profile.uses_sqlite is True
    assert profile.effective_mode == DbMode.SQLITE
    assert studio_db is not None


def test_login_route_migra_auth_legacy_json_verso_sqlite(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    legacy = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    legacy.crea(
        username="migrato",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AVVOCATO,
        must_change_password=False,
    )

    client = app.test_client()
    response = client.post(
        "/login",
        data={"username": "migrato", "password": "PasswordSicura!123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_request_storage_runtime_fallbacks_to_json_when_sqlite_unavailable(
    tmp_path: Path, monkeypatch
):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    clienti_path = tmp_path / "clienti" / "anagrafica.json"
    clienti_path.parent.mkdir(parents=True, exist_ok=True)
    clienti_path.write_text("{}", encoding="utf-8")

    def _raise_sqlite_error(_path: str):
        raise sqlite3.OperationalError("sqlite unavailable")

    monkeypatch.setattr("web.services.storage_runtime.StudioDB.get", _raise_sqlite_error)

    with app.test_request_context("/"):
        profile_before = get_request_storage_runtime(str(clienti_path))
        studio_db = get_request_studio_db(str(clienti_path))
        profile_after = get_request_storage_runtime(str(clienti_path))

    assert profile_before.selected_mode == DbMode.SQLITE
    assert profile_before.uses_sqlite is True
    assert studio_db is None
    assert profile_after.selected_mode == DbMode.SQLITE
    assert profile_after.effective_mode == DbMode.JSON
    assert profile_after.uses_sqlite is False
    assert profile_after.source.endswith("sqlite-unavailable")


def test_login_route_falls_back_to_json_when_sqlite_runtime_is_unavailable(
    tmp_path: Path, monkeypatch
):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    legacy = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    legacy.crea(
        username="locale-json",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AVVOCATO,
        must_change_password=False,
    )

    def _raise_sqlite_error(_path: str):
        raise sqlite3.OperationalError("sqlite unavailable")

    monkeypatch.setattr("web.services.storage_runtime.StudioDB.get", _raise_sqlite_error)

    client = app.test_client()
    response = client.post(
        "/login",
        data={"username": "locale-json", "password": "PasswordSicura!123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_login_route_resolves_unique_tenant_user_without_studio_slug(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    tenant_users = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=StudioDB.get(paths["STUDIO_DB"]),
    )
    tenant_user = tenant_users.crea(
        username="antonella",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug=studio.slug,
        must_change_password=False,
    )

    client = app.test_client()
    response = client.post(
        "/login",
        data={"username": tenant_user.username, "password": "PasswordSicura!123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as session_data:
        assert session_data["tenant_slug"] == studio.slug
        assert session_data["user_id"] == tenant_user.id


def test_login_route_con_studio_slug_legge_utenti_dal_sqlite_del_tenant(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    tenant_users = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=StudioDB.get(paths["STUDIO_DB"]),
    )
    tenant_user = tenant_users.crea(
        username="antonella-explicit",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug=studio.slug,
        must_change_password=False,
    )

    client = app.test_client()
    response = client.post(
        "/login",
        data={
            "username": tenant_user.username,
            "password": "PasswordSicura!123",
            "studio_slug": studio.slug,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as session_data:
        assert session_data["tenant_slug"] == studio.slug
        assert session_data["auth_scope"] == "tenant"
        assert session_data["auth_tenant_slug"] == studio.slug
        assert session_data["user_id"] == tenant_user.id


def test_login_route_assigns_single_active_tenant_to_legacy_global_admin(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "SQLITE"})

    root_users = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    legacy_admin = root_users.crea(
        username="admin",
        password="adminadmin",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug="",
        must_change_password=False,
    )

    client = app.test_client()
    response = client.post(
        "/login",
        data={"username": legacy_admin.username, "password": "adminadmin"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as session_data:
        assert session_data["tenant_slug"] == studio.slug
        assert session_data["user_id"] == legacy_admin.id
        assert session_data["auth_scope"] == "global"
        assert session_data["auth_tenant_slug"] == ""


def test_single_tenant_bootstrap_migra_dati_legacy_nello_studio_sqlite(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "SQLITE"})

    root_clienti = tmp_path / "clienti" / "anagrafica.json"
    root_clienti.parent.mkdir(parents=True, exist_ok=True)
    root_clienti.write_text(
        json.dumps(
            {
                "CLI001": {
                    "id": "CLI001",
                    "tipo": "PERSONA_FISICA",
                    "stato": "ATTIVO",
                    "nome": "Antonella",
                    "cognome": "Mammola",
                    "codice_fiscale": "MMMNNL75E65F839X",
                    "recapiti": {},
                    "documento": {"tipo": "CARTA_IDENTITA"},
                    "procedimenti": [],
                    "tag": [],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    root_fascicoli = tmp_path / "fascicoli" / "fascicoli.json"
    root_fascicoli.parent.mkdir(parents=True, exist_ok=True)
    root_fascicoli.write_text(
        json.dumps(
            {
                "FASC001": {
                    "id": "FASC001",
                    "numero": "1/2026",
                    "titolo": "Ricorso di prova",
                    "tipo": "CIVILE",
                    "stato": "APERTO",
                    "id_cliente": "CLI001",
                    "nome_cliente": "Mammola Antonella",
                    "attivita": [],
                    "documenti": [],
                    "scadenze_interne": [],
                    "depositi_pct": [],
                    "avanzamento": [],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    root_docs = tmp_path / "fascicoli" / "documenti" / "FASC001"
    root_docs.mkdir(parents=True, exist_ok=True)
    (root_docs / "atto.pdf").write_bytes(b"%PDF-1.4 legacy")

    root_config = tmp_path / "config" / "studio.json"
    _write_studio_config(root_config)

    result = tm.bootstrap_legacy_runtime_data(
        studio.slug,
        {
            "CLIENTI_DB": str(root_clienti),
            "FASCICOLI_DB": str(root_fascicoli),
            "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
            "CONFIG_STUDIO_DB": str(root_config),
        },
    )
    tenant_paths = tm.percorsi_dati(studio.slug)
    conn = sqlite3.connect(tenant_paths["STUDIO_DB"])
    clienti_count = conn.execute("SELECT COUNT(*) FROM clienti").fetchone()[0]
    fascicoli_count = conn.execute("SELECT COUNT(*) FROM fascicoli").fetchone()[0]
    conn.close()

    assert result["ok"] is True
    assert result["sqlite_migrated"] is True
    assert result["sqlite_records"]["clienti"] >= 1
    assert clienti_count >= 1
    assert fascicoli_count >= 1
    assert Path(tenant_paths["FASCICOLI_DOCS"], "FASC001", "atto.pdf").exists()
    assert Path(tenant_paths["CONFIG_STUDIO_DB"]).exists()


def test_login_route_bootstraps_legacy_root_data_for_single_tenant_install(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    root_clienti = Path(app.config["CLIENTI_DB"])
    root_clienti.parent.mkdir(parents=True, exist_ok=True)
    root_clienti.write_text(
        json.dumps(
            {
                "CLI001": {
                    "id": "CLI001",
                    "tipo": "PERSONA_FISICA",
                    "stato": "ATTIVO",
                    "nome": "Antonella",
                    "cognome": "Mammola",
                    "codice_fiscale": "MMMNNL75E65F839X",
                    "recapiti": {},
                    "documento": {"tipo": "CARTA_IDENTITA"},
                    "procedimenti": [],
                    "tag": [],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "SQLITE"})

    root_users = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    legacy_admin = root_users.crea(
        username="admin",
        password="adminadmin",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug="",
        must_change_password=False,
    )

    client = app.test_client()
    response = client.post(
        "/login",
        data={"username": legacy_admin.username, "password": "adminadmin"},
        follow_redirects=False,
    )

    dashboard = client.get("/", follow_redirects=False)
    tenant_paths = tm.percorsi_dati(studio.slug)
    conn = sqlite3.connect(tenant_paths["STUDIO_DB"])
    clienti_count = conn.execute("SELECT COUNT(*) FROM clienti").fetchone()[0]
    conn.close()

    assert response.status_code == 302
    assert clienti_count >= 1
    assert dashboard.status_code == 200


def test_bootstrap_legacy_runtime_data_usa_mapping_directory_anche_con_due_tenant(
    tmp_path: Path,
):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    root_clienti = Path(app.config["CLIENTI_DB"])
    root_clienti.parent.mkdir(parents=True, exist_ok=True)
    root_clienti.write_text(
        json.dumps(
            {
                "CLI001": {
                    "id": "CLI001",
                    "tipo": "PERSONA_FISICA",
                    "stato": "ATTIVO",
                    "nome": "Antonella",
                    "cognome": "Mammola",
                    "codice_fiscale": "MMMNNL75E65F839X",
                    "recapiti": {},
                    "documento": {"tipo": "CARTA_IDENTITA"},
                    "procedimenti": [],
                    "tag": [],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio_target = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "SQLITE"})
    tm.crea("Studio Secondario", "studio-secondario", db_config={"mode": "SQLITE"})

    directory_path = tmp_path / "tenant_user_directory.json"
    directory_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-15T00:00:00",
                "users": {
                    "antonella": {
                        "tenant_slug": studio_target.slug,
                        "tenant_id": studio_target.id,
                        "tenant_storage_key": studio_target.storage_key,
                    }
                },
                "emails": {},
                "conflicts": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = bootstrap_legacy_tenant_runtime_data(app)
    tenant_paths = tm.percorsi_dati(studio_target.slug)
    conn = sqlite3.connect(tenant_paths["STUDIO_DB"])
    clienti_count = conn.execute("SELECT COUNT(*) FROM clienti").fetchone()[0]
    conn.close()
    tenant_config = json.loads(Path(tenant_paths["CONFIG_STUDIO_DB"]).read_text(encoding="utf-8"))

    assert report["ok"] is True
    assert report["target_slug"] == studio_target.slug
    assert clienti_count >= 1
    assert "smtp" in tenant_config


def test_core_runtime_risolve_config_studio_e_smtp_dal_tenant_attivo(tmp_path: Path):
    root_config_path = tmp_path / "config" / "studio.json"
    root_config_path.parent.mkdir(parents=True, exist_ok=True)
    root_config_path.write_text(
        json.dumps(
            {
                "studio": {"nome": "Root Studio"},
                "smtp": {
                    "host": "smtp.root.example",
                    "port": 587,
                    "username": "root",
                    "password": "root-pass",
                    "from_address": "root@example.com",
                    "from_name": "Root Studio",
                    "use_tls": True,
                },
                "whatsapp": {},
                "scheduler": {},
                "ai": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cfg = {**_cfg(tmp_path), "MULTI_TENANT": True, "PCT_SECRET_KEY": "test-secret"}
    app, flask_cfg = create_flask_app(cfg)
    core = build_core_runtime(app, flask_cfg)

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Tenant", "studio-tenant", db_config={"mode": "SQLITE"})
    tenant_paths = tm.percorsi_dati(studio.slug)
    Path(tenant_paths["CONFIG_STUDIO_DB"]).write_text(
        json.dumps(
            {
                "studio": {"nome": "Studio Tenant"},
                "smtp": {
                    "host": "smtp.tenant.example",
                    "port": 465,
                    "username": "tenant-user",
                    "password": "tenant-pass",
                    "from_address": "tenant@example.com",
                    "from_name": "Studio Tenant",
                    "use_tls": False,
                },
                "whatsapp": {
                    "twilio_sid": "tenant-sid",
                    "twilio_token": "tenant-token",
                    "twilio_numero": "+390000000000",
                },
                "scheduler": {},
                "ai": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with app.test_request_context("/"):
        g.data_paths = tenant_paths
        gs = core["get_config_studio"]()
        gm = core["get_messaggi"]()

    assert gs.config.smtp.host == "smtp.tenant.example"
    assert gm.config.email.smtp_host == "smtp.tenant.example"
    assert gm.config.email.username == "tenant-user"
    assert gm.config.email.mittente_email == "tenant@example.com"
    assert gm.config.twilio.account_sid == "tenant-sid"


def test_superadmin_can_create_studio_with_postgresql_strategy(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    utenti = _root_utenti_manager(app)
    superadmin = utenti.crea(
        username="superadmin",
        password="superpass123",
        ruolo=RuoloUtente.SUPERADMIN,
        tenant_slug="",
        must_change_password=False,
    )

    client = app.test_client()
    _login_superadmin(client, username=superadmin.username, password="superpass123")

    response = client.post(
        "/admin/studi/nuovo",
        data={
            "nome": "Studio PostgreSQL",
            "slug": "studio-postgresql",
            "piano": "ENTERPRISE",
            "admin_username": "amministratore",
            "admin_password": "PasswordSicura!123",
            "db_mode": "POSTGRESQL",
        },
        follow_redirects=False,
    )

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.get("studio-postgresql")
    manifest = tm.storage_manifest("studio-postgresql")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/studi/studio-postgresql/database")
    assert studio is not None
    assert studio.database.normalized_mode == DbMode.POSTGRESQL
    assert manifest["selected_mode"] == DbMode.POSTGRESQL
    assert manifest["effective_runtime_kind"] == "json"
    assert manifest["activation_state"] == "external-pending"
