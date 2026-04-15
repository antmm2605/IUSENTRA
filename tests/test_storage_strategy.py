import json
import sqlite3
from pathlib import Path

from flask import g

from pct.auth import GestioneUtenti, RuoloUtente
from pct.tenant import DatabaseConfig, DbMode, GestioneTenant
from web.app import create_app
from web.services.storage_runtime import get_request_storage_runtime, get_request_studio_db


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


def test_database_config_normalizes_storage_modes():
    assert DatabaseConfig.from_dict("LOCAL").normalized_mode == DbMode.JSON
    assert DatabaseConfig.from_dict("JSON").is_json is True
    assert DatabaseConfig.from_dict("SQLITE3").normalized_mode == DbMode.SQLITE
    assert DatabaseConfig.from_dict("POSTGRES").normalized_mode == DbMode.POSTGRESQL


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

    utenti = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    superadmin = utenti.crea(
        username="superadmin",
        password="superpass123",
        ruolo=RuoloUtente.SUPERADMIN,
        tenant_slug="",
    )

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = superadmin.id
        sess["tenant_slug"] = ""

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


def test_superadmin_can_create_studio_with_postgresql_strategy(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    utenti = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    superadmin = utenti.crea(
        username="superadmin",
        password="superpass123",
        ruolo=RuoloUtente.SUPERADMIN,
        tenant_slug="",
    )

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = superadmin.id
        sess["tenant_slug"] = ""

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
