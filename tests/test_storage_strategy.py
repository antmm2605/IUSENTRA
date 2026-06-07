import json
import pytest
import sqlite3
from pathlib import Path

from flask import g

from pct.auth import GestioneUtenti, RuoloUtente
from pct.core_storage_backend import build_core_storage_backend
from pct.database import GestioneDatabase
from pct.storage import StudioDB
from pct.tenant import DatabaseConfig, DbMode, GestioneTenant
from scripts.audit_tenant_data_structure import audit_tenant_data_structure
from web.bootstrap.flask_app_factory import create_flask_app
from web.app import create_app
from web.blueprints.api_v1_react import admin_database_react_payload
from web.blueprints.legal_intelligence import (
    _carica_portali as legal_intelligence_carica_portali,
    _daily_db_path as legal_intelligence_daily_db_path,
)
from web.blueprints.template_atti import _get_gp as template_atti_get_gp
from web.blueprints.template_atti import _get_gt as template_atti_get_gt
from web.services.core_runtime import build_core_runtime
from web.services.admin_surfaces_shared import (
    get_backup_manager,
    get_clienti_manager,
    load_studio_config,
)
from web.services.applicazioni_runtime import (
    _carica_portali as applicazioni_carica_portali,
    _template_manager as applicazioni_template_manager,
)
from web.services.react_impostazioni_calendar import _cal_token_dir
from web.services.storage_runtime import get_request_storage_runtime, get_request_studio_db
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data, legacy_root_data_paths
from web.services.topbar_operational import _cfg_value as topbar_cfg_value
from web.template_atti import _get_gp


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


def test_legacy_bootstrap_non_importa_email_root_automaticamente(tmp_path: Path):
    cfg = {
        "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "EMAIL_ORDINARIA_DB": str(tmp_path / "email" / "ordinaria.json"),
    }

    paths = legacy_root_data_paths(cfg)

    assert "CLIENTI_DB" in paths
    assert "EMAIL_CASELLA_DB" not in paths
    assert "EMAIL_ORDINARIA_DB" not in paths


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


def test_core_runtime_espone_archivi_fonti_ufficiali_da_env(tmp_path: Path, monkeypatch):
    data_root = tmp_path / "data-root"
    lex_db = data_root / "fonti_ufficiali" / "lex_sources.sqlite"
    normattiva_db = data_root / "normativa" / "normattiva.sqlite"
    normattiva_jsonl = data_root / "normativa" / "index" / "normattiva_chunks.jsonl"
    monkeypatch.setenv("PCT_DATA_ROOT", str(data_root))
    monkeypatch.setenv("PCT_LEX_OFFICIAL_DB", str(lex_db))
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(normattiva_db))
    monkeypatch.setenv("PCT_NORMATTIVA_JSONL", str(normattiva_jsonl))

    app, flask_cfg = create_flask_app(_cfg(tmp_path))
    build_core_runtime(app, flask_cfg)

    assert app.config["PCT_DATA_ROOT"] == str(data_root)
    assert app.config["DATA_DIR"] == str(data_root)
    assert app.config["LEX_OFFICIAL_DB"] == str(lex_db)
    assert app.config["NORMATTIVA_DB"] == str(normattiva_db)
    assert app.config["NORMATTIVA_JSONL"] == str(normattiva_jsonl)


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
    )


def test_database_config_normalizes_storage_modes():
    assert DatabaseConfig.from_dict("LOCAL").normalized_mode == DbMode.JSON
    assert DatabaseConfig.from_dict("JSON").is_json is True
    assert DatabaseConfig.from_dict("SQLITE3").normalized_mode == DbMode.SQLITE
    assert DatabaseConfig.from_dict("POSTGRES").normalized_mode == DbMode.POSTGRESQL
    assert DatabaseConfig().normalized_mode == DbMode.SQLITE


def test_core_storage_backend_factory_enforces_common_contract(tmp_path: Path):
    backend = build_core_storage_backend(
        DatabaseConfig(mode=DbMode.SQLITE),
        studio_db_path=str(tmp_path / "studio.db"),
    )

    assert backend is not None
    assert callable(getattr(backend, "carica_tabella", None))
    assert callable(getattr(backend, "salva_tabella", None))
    assert callable(getattr(backend, "ha_dati", None))


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


def test_nuovo_studio_crea_configurazione_runtime_agenda_scadenze_notifiche(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Config Completa", "studio-config-completa", db_config={"mode": "SQLITE"})

    paths = tm.percorsi_dati(studio.slug, reconcile_aliases=False)

    assert Path(paths["AGENDA_DB"]).exists()
    assert Path(paths["SCADENZIARIO_DB"]).exists()
    assert Path(paths["STUDIO_DB"]).exists()
    assert Path(paths["NOTIFICATIONS_DB"]).exists()
    with sqlite3.connect(paths["STUDIO_DB"]) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        moduli = {
            row[0]
            for row in conn.execute("SELECT nome FROM moduli_dati").fetchall()
        }
    assert {"appuntamenti", "scadenze", "clienti", "fascicoli"}.issubset(tables)
    assert {
        "appuntamenti",
        "scadenze",
        "email_casella",
        "email_ordinaria",
        "practice_engine",
        "legal_updates_repository",
        "legal_skills_runs",
        "redaction_assistant",
    }.issubset(moduli)
    with sqlite3.connect(paths["NOTIFICATIONS_DB"]) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"notifications", "push_subscriptions", "notification_preferences"}.issubset(tables)


def test_audit_tenant_data_structure_verifica_json_sqlite_postgres(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Audit Dati", "studio-audit-dati", db_config={"mode": "SQLITE"})
    tm.ensure_runtime_baseline(studio.slug, force=True)

    report = audit_tenant_data_structure(registry=registry, tenant=studio.slug)

    assert report["ok"] is True
    assert report["postgres_schema"]["ok"] is True
    assert report["studios"][studio.slug]["json"]["scadenziario/scadenze.json"]["module"] == "scadenze"


def test_audit_tenant_data_structure_fallisce_se_manca_mirror_json_sql(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Audit Rosso", "studio-audit-rosso", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug, reconcile_aliases=False)

    with sqlite3.connect(paths["STUDIO_DB"]) as conn:
        conn.execute("DELETE FROM moduli_dati WHERE nome = ?", ("scadenze",))
        conn.commit()

    report = audit_tenant_data_structure(registry=registry, tenant=studio.slug)

    assert report["ok"] is False
    assert any("moduli_dati senza record per scadenze" in error for error in report["errors"])


def test_audit_tenant_data_structure_fallisce_se_manca_json_tenant(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Audit Json", "studio-audit-json", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug, reconcile_aliases=False)
    Path(paths["SCADENZIARIO_DB"]).unlink()

    report = audit_tenant_data_structure(registry=registry, tenant=studio.slug)

    assert report["ok"] is False
    assert any("JSON mancante scadenziario/scadenze.json" in error for error in report["errors"])


def test_practice_engine_default_follows_fascicoli_data_root(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    assert Path(app.config["PRACTICE_ENGINE_DB"]) == (
        tmp_path / "fascicoli" / "practice_engine" / "practice_engine.json"
    )


def test_tenant_paths_include_practice_engine_storage(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Regia", "studio-regia", db_config={"mode": "SQLITE"})

    paths = tm.percorsi_dati(studio.slug)

    assert Path(paths["PRACTICE_ENGINE_DB"]) == (
        tmp_path / "tenants" / "studio-regia" / "fascicoli" / "practice_engine" / "practice_engine.json"
    )
    assert Path(paths["PRACTICE_ENGINE_DB"]).parent.exists()


def test_core_runtime_uses_tenant_practice_engine_path(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Regia", "studio-regia", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)

    with app.test_request_context("/"):
        g.data_paths = paths
        repo = app.extensions["core_runtime"]["get_practice_engine"]()

    assert repo.db_path == Path(paths["PRACTICE_ENGINE_DB"])
    assert repo.root_dir == Path(paths["PRACTICE_ENGINE_DB"]).parent


def test_core_runtime_uses_tenant_paths_for_sensitive_repositories(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Blindato", "studio-blindato", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)

    with app.test_request_context("/"):
        g.data_paths = paths
        core = app.extensions["core_runtime"]
        backup = core["get_backup"]()
        soggetti = core["get_soggetti"]()
        indice = core["get_indice"]()
        trattamenti = core["get_trattamenti"]()
        condivisioni = core["get_condivisioni"]()

    assert backup.dir == Path(paths["BACKUP_DIR"])
    assert backup._percorsi == {
        "agenda": paths["AGENDA_DB"],
        "clienti": paths["CLIENTI_DB"],
        "fascicoli": paths["FASCICOLI_DB"],
        "messaggi": paths["MESSAGGI_DB"],
        "documenti": paths["FASCICOLI_DOCS"],
    }
    assert soggetti.soggetti_path == paths["SOGGETTI_DB"]
    assert soggetti.parti_path == paths["SOGGETTI_PARTI_DB"]
    assert indice.path == Path(paths["SEARCH_INDEX"])
    assert trattamenti.db_path == Path(paths["PRIVACY_DB"])
    assert condivisioni.db_path == Path(paths["CONDIVISIONI_DB"])


def test_core_runtime_blocks_sensitive_repositories_when_tenant_context_is_missing(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})
    core = app.extensions["core_runtime"]

    with app.test_request_context("/"):
        g.data_paths = {}
        g.tenant_context_missing = True
        for loader_name in ("get_backup", "get_soggetti", "get_indice", "get_trattamenti", "get_condivisioni"):
            with pytest.raises(RuntimeError, match="cross-studio"):
                core[loader_name]()


def test_calendar_settings_token_dir_uses_tenant_agenda_path(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Calendari", "studio-calendari", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)

    with app.test_request_context("/"):
        g.data_paths = paths
        token_dir = _cal_token_dir()

    assert Path(token_dir) == Path(paths["AGENDA_DB"]).parent


def test_template_atti_uses_tenant_preventivi_repository(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Preventivi", "studio-preventivi", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)

    with app.test_request_context("/"):
        g.data_paths = paths
        gestore = _get_gp()

    assert Path(gestore.db_path) == Path(paths["PREVENTIVI_DB"])


def test_admin_database_react_payload_uses_tenant_backup_dir(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Database", "studio-database", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    backup_dir = Path(paths["BACKUP_DIR"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = backup_dir / "studio_legale.db"
    conn = sqlite3.connect(sqlite_path)
    conn.execute("CREATE TABLE clienti (id TEXT)")
    conn.commit()
    conn.close()

    class _AdminUser:
        @staticmethod
        def ha_permesso(permission: str) -> bool:
            return permission == "utenti.leggi"

    with app.test_request_context("/api/v1/ui/admin/database?path=/admin/database"):
        g.data_paths = paths
        g.utente_corrente = _AdminUser()
        response = admin_database_react_payload()

    payload = response.get_json()
    assert payload["sqlite"]["exists"] is True
    assert payload["sqlite"]["tables"]


def test_admin_shared_helpers_use_tenant_paths(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Admin", "studio-admin", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    Path(paths["CONFIG_STUDIO_DB"]).parent.mkdir(parents=True, exist_ok=True)
    Path(paths["CONFIG_STUDIO_DB"]).write_text(
        json.dumps({"studio": {"nome": "Studio Tenant Admin"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    with app.test_request_context("/admin/system-health"):
        g.data_paths = paths
        config = load_studio_config()
        backup = get_backup_manager()
        clienti = get_clienti_manager()

    assert config["studio"]["nome"] == "Studio Tenant Admin"
    assert backup.dir == Path(paths["BACKUP_DIR"])
    assert Path(clienti.db_path) == Path(paths["CLIENTI_DB"])


def test_topbar_cfg_value_blocks_when_tenant_context_is_missing(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    with app.test_request_context("/api/v1/ui/topbar"):
        g.data_paths = {}
        g.tenant_context_missing = True
        with pytest.raises(RuntimeError, match="cross-studio"):
            topbar_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json")


def test_template_blueprint_uses_tenant_template_paths(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Template", "studio-template", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)

    with app.test_request_context("/template-atti"):
        g.data_paths = paths
        gestore_template = template_atti_get_gt()
        gestore_prefs = template_atti_get_gp()

    assert Path(gestore_template.db_path) == Path(paths["TEMPLATE_ATTI_DB"])
    assert Path(gestore_prefs.prefs_path) == Path(paths["TEMPLATE_ATTI_PREFS_DB"])


def test_applicazioni_runtime_uses_tenant_template_and_portale_paths(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Applicazioni", "studio-applicazioni", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    observed: dict[str, str] = {}

    class _DummyPortale:
        def __init__(self, db_path: str, uploads_dir: str):
            observed["db_path"] = db_path
            observed["uploads_dir"] = uploads_dir

        def tutti(self, includi_inattivi: bool = False):
            return []

    monkeypatch.setattr("pct.portale.GestionePortale", _DummyPortale)

    with app.test_request_context("/applicazioni"):
        g.data_paths = paths
        template_manager = applicazioni_template_manager()
        portali = applicazioni_carica_portali()

    assert Path(template_manager.db_path) == Path(paths["TEMPLATE_ATTI_DB"])
    assert observed["db_path"] == paths["PORTALE_DB"]
    assert observed["uploads_dir"] == paths["PORTALE_UPLOADS"]
    assert portali == []


def test_legal_intelligence_uses_tenant_daily_and_portale_paths(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Intelligence", "studio-intelligence", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    observed: dict[str, str] = {}

    class _DummyPortale:
        def __init__(self, db_path: str, uploads_dir: str):
            observed["db_path"] = db_path
            observed["uploads_dir"] = uploads_dir

        def tutti(self, includi_inattivi: bool = False):
            return []

    monkeypatch.setattr("web.blueprints.legal_intelligence.GestionePortale", _DummyPortale)

    with app.test_request_context("/legal-intelligence"):
        g.data_paths = paths
        daily_path = legal_intelligence_daily_db_path()
        portali = legal_intelligence_carica_portali()

    assert daily_path == Path(paths["LEGAL_INTELLIGENCE_DB"]).resolve().parent / "daily.sqlite"
    assert observed["db_path"] == paths["PORTALE_DB"]
    assert observed["uploads_dir"] == paths["PORTALE_UPLOADS"]
    assert portali == []


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


def test_migrazione_sqlite_riallinea_colonne_dati_json_runtime(tmp_path: Path):
    agenda_path = tmp_path / "agenda" / "appuntamenti.json"
    agenda_path.parent.mkdir(parents=True, exist_ok=True)
    agenda_path.write_text(
        json.dumps(
            [
                {
                    "id": "APP001",
                    "titolo": "Consulenza iniziale",
                    "tipo": "CONSULTAZIONE",
                    "stato": "PROGRAMMATO",
                    "data_ora": "2026-04-28T10:30:00",
                    "durata_minuti": 30,
                    "luogo": "Studio",
                    "note": "Migrazione agenda",
                    "creato_il": "2026-04-22T09:00:00",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    risultato = GestioneDatabase({"appuntamenti": str(agenda_path)}).migra_verso_sqlite(
        str(tmp_path / "studio.db")
    )

    assert risultato.riuscita is True

    conn = sqlite3.connect(str(tmp_path / "studio.db"))
    try:
        colonne = [row[1] for row in conn.execute("PRAGMA table_info(appuntamenti)").fetchall()]
        dati_json = conn.execute(
            "SELECT dati_json FROM appuntamenti WHERE id = ?",
            ("APP001",),
        ).fetchone()
    finally:
        conn.close()

    assert "dati_json" in colonne
    assert dati_json is not None
    assert "Consulenza iniziale" in str(dati_json[0] or "")


def test_request_storage_runtime_honors_default_storage_mode_json(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "STORAGE_MODE_DEFAULT": "JSON"})

    clienti_path = tmp_path / "clienti" / "anagrafica.json"
    clienti_path.parent.mkdir(parents=True, exist_ok=True)
    clienti_path.write_text("{}", encoding="utf-8")

    with app.test_request_context("/"):
        profile = get_request_storage_runtime(str(clienti_path))
        studio_db = get_request_studio_db(str(clienti_path))

    assert profile.selected_mode == DbMode.JSON
    assert profile.uses_sqlite is False
    assert profile.effective_mode == DbMode.JSON
    assert profile.source == "app-default"
    assert studio_db is None


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


def test_profilo_tenant_cambia_password_anche_se_sqlite_auth_non_e_disponibile(
    tmp_path: Path, monkeypatch
):
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
        studio_db=None,
    )
    tenant_users.crea(
        username="roberto.montagnese",
        password="R0berto!Pct2026",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug=studio.slug,
        must_change_password=True,
    )

    def _raise_sqlite_unavailable(_path: str):
        raise sqlite3.OperationalError("sqlite unavailable")

    client = app.test_client()
    with monkeypatch.context() as login_patch:
        login_patch.setattr("web.services.auth_runtime.build_core_storage_backend", lambda *args, **kwargs: (_raise_sqlite_unavailable("studio.db")))
        login = client.post(
            "/login",
            data={
                "username": "roberto.montagnese",
                "password": "R0berto!Pct2026",
                "studio_slug": studio.slug,
            },
            follow_redirects=False,
        )

    assert login.status_code == 302
    assert login.headers["Location"].endswith("/")
    with client.session_transaction() as session_data:
        assert session_data["tenant_slug"] == studio.slug
        assert session_data["auth_scope"] == "tenant"
        assert session_data["auth_tenant_slug"] == studio.slug
        assert session_data["must_change_password"] is True

    with monkeypatch.context() as profile_patch:
        profile_patch.setattr("web.services.auth_runtime.build_core_storage_backend", lambda *args, **kwargs: (_raise_sqlite_unavailable("studio.db")))
        profile_patch.setattr("web.services.storage_runtime.StudioDB.get", _raise_sqlite_unavailable)
        changed = client.post(
            "/profilo",
            data={
                "azione": "password",
                "password_old": "R0berto!Pct2026",
                "password_new": "NuovaPwd!2026",
            },
            follow_redirects=True,
        )

    body = changed.get_data(as_text=True)

    assert changed.status_code == 200
    assert "Password attuale non corretta." not in body
    assert "Password aggiornata correttamente." in body

    tenant_users_after = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=None,
    )
    assert tenant_users_after.autentica("roberto.montagnese", "NuovaPwd!2026") is not None


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


def test_login_route_blocca_account_globale_non_superadmin_se_esistono_piu_studi(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "SQLITE"})
    tm.crea("Studio Secondario", "studio-secondario", db_config={"mode": "SQLITE"})

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
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<form" in body
    assert "Accedi" in body
    with client.session_transaction() as session_data:
        assert "user_id" not in session_data
        assert "tenant_slug" not in session_data


def test_richiesta_blocca_sessione_globale_non_superadmin_con_piu_studi(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    primo = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "SQLITE"})
    tm.crea("Studio Secondario", "studio-secondario", db_config={"mode": "SQLITE"})

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
    with client.session_transaction() as session_data:
        session_data["user_id"] = legacy_admin.id
        session_data["tenant_slug"] = primo.slug
        session_data["auth_scope"] = "global"
        session_data["auth_tenant_slug"] = ""

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with client.session_transaction() as session_data:
        assert "user_id" not in session_data
        assert "tenant_slug" not in session_data


def test_reconcile_storage_aliases_semina_dati_dal_percorso_slug_al_storage_key(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "JSON"})
    tm.aggiorna(studio.slug, storage_key="tenant-legacy")

    slug_dir = tmp_path / "tenants" / "antonella-mammola"
    storage_dir = tmp_path / "tenants" / "tenant-legacy"
    (slug_dir / "clienti").mkdir(parents=True, exist_ok=True)
    (slug_dir / "config").mkdir(parents=True, exist_ok=True)
    (slug_dir / "fascicoli" / "documenti" / "CASE01").mkdir(parents=True, exist_ok=True)
    (storage_dir / "auth").mkdir(parents=True, exist_ok=True)

    (slug_dir / "clienti" / "anagrafica.json").write_text(
        json.dumps({"c1": {"nome": "Cliente storico"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (slug_dir / "config" / "studio.json").write_text(
        json.dumps({"studio": {"nome": "Studio Legale Montagnese"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (slug_dir / "fascicoli" / "documenti" / "CASE01" / "atto.pdf").write_text(
        "PDF",
        encoding="utf-8",
    )
    (storage_dir / "auth" / "utenti.json").write_text("{}", encoding="utf-8")

    report = tm.reconcile_storage_aliases(studio.slug)

    assert report["copied_files"]
    assert (storage_dir / "clienti" / "anagrafica.json").exists()
    assert (storage_dir / "config" / "studio.json").exists()
    assert (storage_dir / "fascicoli" / "documenti" / "CASE01" / "atto.pdf").exists()


def test_reconcile_storage_aliases_copia_payload_se_copy2_fallisce_su_metadati(
    tmp_path: Path,
    monkeypatch,
):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "JSON"})
    tm.aggiorna(studio.slug, storage_key="tenant-legacy")

    slug_dir = tmp_path / "tenants" / "antonella-mammola"
    storage_dir = tmp_path / "tenants" / "tenant-legacy"
    (slug_dir / "clienti").mkdir(parents=True, exist_ok=True)
    (slug_dir / "clienti" / "anagrafica.json").write_text(
        json.dumps({"c1": {"nome": "Cliente storico"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    def _copy2_permission_denied(source, destination):
        raise PermissionError("[Errno 1] Operation not permitted")

    monkeypatch.setattr("pct.tenant.shutil.copy2", _copy2_permission_denied)

    report = tm.reconcile_storage_aliases(studio.slug)

    assert report["copied_files"]
    assert json.loads((storage_dir / "clienti" / "anagrafica.json").read_text(encoding="utf-8")) == {
        "c1": {"nome": "Cliente storico"}
    }


def test_aggiorna_tenant_funziona_anche_con_registry_indicizzato_per_id(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    legacy_id = "6b4fde33-a390-454c-b981-1492c1f15633"
    registry.write_text(
        json.dumps(
            {
                legacy_id: {
                    "id": legacy_id,
                    "slug": "antonella-mammola",
                    "storage_key": "antonella-mammola",
                    "nome": "Antonella Mammola",
                    "piano": "ENTERPRISE",
                    "stato": "ATTIVO",
                    "db_config": {"mode": "JSON"},
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    tm = GestioneTenant(str(registry))

    aggiornato = tm.aggiorna(
        "antonella-mammola",
        nome="Studio Legale Montagnese",
        piva="01301790802",
    )

    payload = json.loads(registry.read_text(encoding="utf-8"))
    assert aggiornato is not None
    assert payload[legacy_id]["nome"] == "Studio Legale Montagnese"
    assert payload[legacy_id]["piva"] == "01301790802"


def test_sync_user_directory_indicizza_utenti_tenant_sqlite(tmp_path: Path):
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
        username="roberto.montagnese",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="r.montagnese@tiscali.it",
        tenant_slug=studio.slug,
        must_change_password=False,
    )

    payload = tm.sync_user_directory(secret_key=app.secret_key)

    assert payload["users"]["roberto.montagnese"]["tenant_slug"] == studio.slug
    assert payload["emails"]["r.montagnese@tiscali.it"]["user_id"] == tenant_user.id


def test_sync_user_directory_ripara_tenant_slug_errato_nell_auth_tenant(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Giuseppe", "studio-legale-giuseppe-montagnese", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    tenant_users = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=StudioDB.get(paths["STUDIO_DB"]),
        tenant_slug_context=studio.slug,
    )
    tenant_user = tenant_users.crea(
        username="admin",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="giuseppe.montagnese94@gmail.com",
        tenant_slug="tenant_slug",
        must_change_password=False,
    )

    payload = tm.sync_user_directory(secret_key=app.secret_key)
    persisted = json.loads(Path(paths["AUTH_DB"]).read_text(encoding="utf-8"))

    assert payload["users"]["admin"]["tenant_slug"] == studio.slug
    assert payload["emails"]["giuseppe.montagnese94@gmail.com"]["tenant_slug"] == studio.slug
    assert persisted[tenant_user.id]["tenant_slug"] == studio.slug


def test_superadmin_database_ripara_accesso_studio_da_pannello(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    platform_users = _root_utenti_manager(app)
    superadmin = platform_users.crea(
        username="superadmin",
        password="superpass123",
        ruolo=RuoloUtente.SUPERADMIN,
        tenant_slug="",
        must_change_password=False,
    )

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Giuseppe", "studio-legale-giuseppe-montagnese", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    tenant_users = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=StudioDB.get(paths["STUDIO_DB"]),
    )
    tenant_user = tenant_users.crea(
        username="admin",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="giuseppe.montagnese94@gmail.com",
        tenant_slug="tenant_slug",
        must_change_password=False,
    )

    client = app.test_client()
    _login_superadmin(client, username=superadmin.username, password="superpass123")
    page = client.get(f"/admin/studi/{studio.slug}/database")
    response = client.post(
        f"/admin/studi/{studio.slug}/database/ripara-runtime",
        follow_redirects=False,
    )
    persisted = json.loads(Path(paths["AUTH_DB"]).read_text(encoding="utf-8"))
    directory = json.loads((tmp_path / "tenant_user_directory.json").read_text(encoding="utf-8"))

    assert page.status_code == 200
    assert "Ripara studio" in page.get_data(as_text=True)
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/admin/studi/{studio.slug}/database")
    assert persisted[tenant_user.id]["tenant_slug"] == studio.slug
    assert directory["users"]["admin"]["tenant_slug"] == studio.slug
    assert directory["emails"]["giuseppe.montagnese94@gmail.com"]["tenant_slug"] == studio.slug


def test_sync_user_directory_puo_saltare_reconcile_pesante(tmp_path: Path, monkeypatch):
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
        username="roberto.montagnese",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="r.montagnese@tiscali.it",
        tenant_slug=studio.slug,
        must_change_password=False,
    )
    calls = {"reconcile": 0}

    def _reconcile(_slug):
        calls["reconcile"] += 1
        return {"ok": True}

    monkeypatch.setattr(tm, "reconcile_storage_aliases", _reconcile)

    payload = tm.sync_user_directory(secret_key=app.secret_key, reconcile_storage=False)

    assert calls["reconcile"] == 0
    assert payload["users"]["roberto.montagnese"]["tenant_slug"] == studio.slug
    assert payload["emails"]["r.montagnese@tiscali.it"]["user_id"] == tenant_user.id


def test_admin_utenti_studio_mostra_utenti_tenant_sqlite(tmp_path: Path):
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
    tenant_users.crea(
        username="roberto.montagnese",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug=studio.slug,
        must_change_password=False,
    )

    superadmin = _root_utenti_manager(app).crea(
        username="superadmin",
        password="superpass123",
        ruolo=RuoloUtente.SUPERADMIN,
        tenant_slug="",
        must_change_password=False,
    )

    client = app.test_client()
    _login_superadmin(client, username=superadmin.username, password="superpass123")

    response = client.get(f"/admin/studi/{studio.slug}/utenti")

    assert response.status_code == 200
    assert b"roberto.montagnese" in response.data


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


def test_bootstrap_legacy_runtime_data_riconcilia_sqlite_parzialmente_popolato(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Montagnese", "studio-legale-giuseppe-montagnese", db_config={"mode": "SQLITE"})
    tenant_paths = tm.percorsi_dati(studio.slug)

    root_clienti = tmp_path / "clienti" / "anagrafica.json"
    root_clienti.parent.mkdir(parents=True, exist_ok=True)
    root_clienti.write_text(
        json.dumps({"CLI001": {"id": "CLI001", "nome": "Giuseppe", "cognome": "Montagnese"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    root_fascicoli = tmp_path / "fascicoli" / "fascicoli.json"
    root_fascicoli.parent.mkdir(parents=True, exist_ok=True)
    root_fascicoli.write_text(
        json.dumps({"FASC001": {"id": "FASC001", "numero": "1/2026", "titolo": "Pratica", "id_cliente": "CLI001"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    tenant_messaggi = tmp_path / "messaggi.json"
    tenant_messaggi.write_text(
        json.dumps([{"id": "MSG001", "oggetto": "Messaggio già presente"}], ensure_ascii=False),
        encoding="utf-8",
    )
    GestioneDatabase({"messaggi": str(tenant_messaggi)}).migra_verso_sqlite(tenant_paths["STUDIO_DB"])
    conn = sqlite3.connect(tenant_paths["STUDIO_DB"])
    conn.execute(
        "INSERT OR REPLACE INTO messaggi (id, oggetto, corpo) VALUES (?, ?, ?)",
        ("MSG001", "Messaggio già presente", "Da preservare"),
    )
    conn.commit()
    conn.close()

    report = tm.bootstrap_legacy_runtime_data(
        studio.slug,
        {
            "CLIENTI_DB": str(root_clienti),
            "FASCICOLI_DB": str(root_fascicoli),
        },
    )

    conn = sqlite3.connect(tenant_paths["STUDIO_DB"])
    counts = conn.execute(
        "SELECT (SELECT COUNT(*) FROM clienti), (SELECT COUNT(*) FROM fascicoli), (SELECT COUNT(*) FROM messaggi)"
    ).fetchone()
    conn.close()

    assert report["ok"] is True
    assert report["sqlite_migrated"] is True
    assert counts == (1, 1, 1)


def test_bootstrap_legacy_runtime_data_non_riconcilia_storage_in_startup(
    tmp_path: Path,
    monkeypatch,
):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Avvio", "studio-avvio", db_config={"mode": "SQLITE"})

    root_clienti = tmp_path / "clienti" / "anagrafica.json"
    root_clienti.parent.mkdir(parents=True, exist_ok=True)
    root_clienti.write_text(
        json.dumps({"CLI001": {"id": "CLI001", "nome": "Cliente avvio"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    def fail_reconcile(slug: str):
        raise AssertionError(f"reconcile_storage_aliases non deve girare in startup legacy: {slug}")

    monkeypatch.setattr(tm, "reconcile_storage_aliases", fail_reconcile)

    result = tm.bootstrap_legacy_runtime_data(
        studio.slug,
        {"CLIENTI_DB": str(root_clienti)},
    )

    assert result["ok"] is True
    assert "CLIENTI_DB" in result["copied"]


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


def test_bootstrap_legacy_runtime_data_non_semina_root_quando_esistono_due_tenant(
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
    studio_db_path = Path(tenant_paths["STUDIO_DB"])

    assert report["ok"] is False
    assert report["reason"] == "multi-tenant-ambiguous"
    assert report["target_slug"] == ""
    assert not studio_db_path.exists() or not GestioneTenant._sqlite_table_has_records(studio_db_path, "clienti")


def test_bootstrap_legacy_runtime_data_rifiuta_anche_il_tenant_richiesto_se_multi_studio(
    tmp_path: Path,
):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})

    root_clienti = Path(app.config["CLIENTI_DB"])
    root_clienti.parent.mkdir(parents=True, exist_ok=True)
    root_clienti.write_text(
        json.dumps({"CLI001": {"id": "CLI001", "nome": "Cliente storico"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio_target = tm.crea("Studio Antonella", "antonella-mammola", db_config={"mode": "SQLITE"})
    tm.crea("Studio Secondario", "studio-secondario", db_config={"mode": "SQLITE"})

    report = bootstrap_legacy_tenant_runtime_data(app, tenant_slug=studio_target.slug)
    tenant_paths = tm.percorsi_dati(studio_target.slug)
    studio_db_path = Path(tenant_paths["STUDIO_DB"])

    assert report["ok"] is False
    assert report["reason"] == "multi-tenant-ambiguous"
    assert report["target_slug"] == ""
    assert not studio_db_path.exists() or not GestioneTenant._sqlite_table_has_records(studio_db_path, "clienti")


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


def test_carica_tenant_non_bootstrappa_sulle_risorse_statiche(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Tenant", "studio-tenant", db_config={"mode": "SQLITE"})
    counters = {"legacy": 0, "reconcile": 0}

    def _fake_bootstrap(app_obj, *, tenant_slug=None):
        counters["legacy"] += 1
        return {"ok": True, "copied": {}, "sqlite_migrated": False}

    def _fake_reconcile(self, slug):
        counters["reconcile"] += 1
        return {
            "ok": True,
            "copied_files": {},
            "merged_dirs": {},
            "backfilled_alias_files": {},
            "backfilled_alias_dirs": {},
            "canonical": str(tmp_path / "tenants" / slug),
        }

    monkeypatch.setattr(
        "web.services.auth_runtime.bootstrap_legacy_tenant_runtime_data",
        _fake_bootstrap,
    )
    monkeypatch.setattr(GestioneTenant, "reconcile_storage_aliases", _fake_reconcile)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["tenant_slug"] = studio.slug

    response = client.get("/static/css/app.css")

    assert response.status_code in {200, 304}
    assert counters == {"legacy": 0, "reconcile": 0}


def test_carica_tenant_bootstrappa_una_sola_volta_senza_riconciliazione_pesante(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app({**_cfg(tmp_path), "MULTI_TENANT": True})
    tm = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Tenant", "studio-tenant", db_config={"mode": "SQLITE"})
    counters = {"legacy": 0, "reconcile": 0}

    def _fake_bootstrap(app_obj, *, tenant_slug=None):
        counters["legacy"] += 1
        return {"ok": True, "copied": {}, "sqlite_migrated": False}

    def _fake_reconcile(self, slug):
        counters["reconcile"] += 1
        return {
            "ok": True,
            "copied_files": {},
            "merged_dirs": {},
            "backfilled_alias_files": {},
            "backfilled_alias_dirs": {},
            "canonical": str(tmp_path / "tenants" / slug),
        }

    monkeypatch.setattr(
        "web.services.auth_runtime.bootstrap_legacy_tenant_runtime_data",
        _fake_bootstrap,
    )
    monkeypatch.setattr(GestioneTenant, "reconcile_storage_aliases", _fake_reconcile)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["tenant_slug"] = studio.slug

    first = client.get("/login")
    second = client.get("/login")

    state = app.extensions["tenant_runtime_state"][studio.slug]

    assert first.status_code == 200
    assert second.status_code == 200
    assert counters == {"legacy": 1, "reconcile": 0}
    assert state["legacy_bootstrap_completed"] is True
    assert state["storage_reconciled"] is True
    assert state["module_bootstrap_completed"] is True


def test_request_storage_runtime_uses_active_postgresql_backend(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    clienti_path = tmp_path / "tenants" / "pg-live" / "clienti" / "anagrafica.json"
    clienti_path.parent.mkdir(parents=True, exist_ok=True)
    clienti_path.write_text("{}", encoding="utf-8")

    tm = GestioneTenant(str(tmp_path / "tenants.json"))
    studio = tm.crea("Studio PostgreSQL Live", "pg-live", db_config={"mode": "POSTGRESQL"})
    tm.aggiorna_db_config(
        studio.slug,
        DatabaseConfig(
            mode=DbMode.POSTGRESQL,
            host="db.example.local",
            porta=5432,
            db_name="iusentra",
            utente="iusentra",
            password="secret",
            connessione_ok=True,
            core_runtime_enabled=True,
        ),
    )
    fake_backend = object()
    monkeypatch.setattr(
        "web.services.storage_runtime.build_core_storage_backend",
        lambda config, studio_db_path: fake_backend,
    )

    with app.test_request_context("/"):
        g.tenant = tm.get(studio.slug)
        profile = get_request_storage_runtime(str(clienti_path))
        studio_db = get_request_studio_db(str(clienti_path))

    assert profile.selected_mode == DbMode.POSTGRESQL
    assert profile.effective_mode == DbMode.POSTGRESQL
    assert profile.uses_sqlite is False
    assert profile.source == "tenant-postgresql"
    assert studio_db is fake_backend


def test_request_storage_runtime_blocca_fallback_invisibile_se_postgresql_attivo_non_e_disponibile(
    tmp_path: Path,
    monkeypatch,
):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg(tmp_path))

    clienti_path = tmp_path / "tenants" / "pg-fail" / "clienti" / "anagrafica.json"
    clienti_path.parent.mkdir(parents=True, exist_ok=True)
    clienti_path.write_text("{}", encoding="utf-8")

    tm = GestioneTenant(str(tmp_path / "tenants.json"))
    studio = tm.crea("Studio PostgreSQL Fail", "pg-fail", db_config={"mode": "POSTGRESQL"})
    tm.aggiorna_db_config(
        studio.slug,
        DatabaseConfig(
            mode=DbMode.POSTGRESQL,
            host="db.example.local",
            porta=5432,
            db_name="iusentra",
            utente="iusentra",
            password="secret",
            connessione_ok=True,
            core_runtime_enabled=True,
        ),
    )
    monkeypatch.setattr(
        "web.services.storage_runtime.build_core_storage_backend",
        lambda config, studio_db_path: None,
    )

    with app.test_request_context("/"):
        g.tenant = tm.get(studio.slug)
        profile = get_request_storage_runtime(str(clienti_path))
        with pytest.raises(RuntimeError):
            get_request_studio_db(str(clienti_path))

    assert profile.effective_mode == DbMode.POSTGRESQL


def test_storage_manifest_mostra_postgresql_attivo_per_domini_core(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio PG", "studio-pg", db_config={"mode": "POSTGRESQL"})
    tm.aggiorna_db_config(
        studio.slug,
        DatabaseConfig(
            mode=DbMode.POSTGRESQL,
            host="db.example.local",
            porta=5432,
            db_name="iusentra",
            utente="iusentra",
            password="secret",
            connessione_ok=True,
            core_runtime_enabled=True,
        ),
    )

    manifest = tm.storage_manifest(studio.slug)

    assert manifest["effective_runtime_kind"] == "postgresql"
    assert manifest["activation_state"] == "active"
    assert manifest["core_runtime_enabled"] is True


def test_studio_db_fallbacks_to_delete_when_wal_non_disponibile(tmp_path: Path, monkeypatch):
    from pct import storage as storage_module

    real_connect = sqlite3.connect
    statements: list[str] = []

    class _ProxyConnection:
        def __init__(self, conn):
            self._conn = conn

        @property
        def row_factory(self):
            return self._conn.row_factory

        @row_factory.setter
        def row_factory(self, value):
            self._conn.row_factory = value

        def execute(self, sql, *args, **kwargs):
            statements.append(str(sql))
            if str(sql).strip().upper() == "PRAGMA JOURNAL_MODE=WAL":
                raise sqlite3.OperationalError("wal non disponibile")
            return self._conn.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    monkeypatch.setattr(
        storage_module.sqlite3,
        "connect",
        lambda *args, **kwargs: _ProxyConnection(real_connect(*args, **kwargs)),
    )

    db = StudioDB(str(tmp_path / "studio.db"))
    row = db.conn.execute("SELECT 1").fetchone()

    assert any("PRAGMA journal_mode=WAL" in sql for sql in statements)
    assert any("PRAGMA journal_mode=DELETE" in sql for sql in statements)
    assert row[0] == 1


def test_studio_db_salva_tabella_ritenta_se_sqlite_bloccato(tmp_path: Path, monkeypatch):
    from pct import storage as storage_module

    real_connect = sqlite3.connect
    attempts = {"delete": 0}

    class _ProxyConnection:
        def __init__(self, conn):
            self._conn = conn

        @property
        def row_factory(self):
            return self._conn.row_factory

        @row_factory.setter
        def row_factory(self, value):
            self._conn.row_factory = value

        def execute(self, sql, *args, **kwargs):
            statement = str(sql).strip().upper()
            if statement == "DELETE FROM RETRY_ROWS" and attempts["delete"] == 0:
                attempts["delete"] += 1
                raise sqlite3.OperationalError("database is locked")
            if statement == "DELETE FROM RETRY_ROWS":
                attempts["delete"] += 1
            return self._conn.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    monkeypatch.setattr(
        storage_module.sqlite3,
        "connect",
        lambda *args, **kwargs: _ProxyConnection(real_connect(*args, **kwargs)),
    )

    db = StudioDB(str(tmp_path / "studio.db"))
    db.conn.execute("CREATE TABLE retry_rows (id TEXT PRIMARY KEY, value TEXT)")
    db.conn.execute("INSERT INTO retry_rows VALUES (?,?)", ("old", "old"))
    db.conn.commit()

    db.salva_tabella(
        "retry_rows",
        [{"id": "new", "value": "ok"}],
        lambda conn, row: conn.execute("INSERT INTO retry_rows VALUES (?,?)", (row["id"], row["value"])),
    )

    rows = db.conn.execute("SELECT id, value FROM retry_rows").fetchall()
    assert attempts["delete"] == 2
    assert [tuple(row) for row in rows] == [("new", "ok")]


def test_gestione_utenti_ripiega_su_json_quando_backend_studio_non_e_disponibile(tmp_path: Path):
    auth_path = tmp_path / "auth" / "utenti.json"
    audit_path = tmp_path / "auth" / "audit.json"
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text("{}", encoding="utf-8")
    audit_path.write_text("[]", encoding="utf-8")

    legacy = GestioneUtenti(
        db_path=str(auth_path),
        audit_path=str(audit_path),
        secret_key="test",
        crea_admin_se_vuoto=False,
    )
    legacy.crea(
        username="avvtest",
        password="PasswordSicura!123",
        ruolo=RuoloUtente.AVVOCATO,
        must_change_password=False,
    )

    class _BrokenBackend:
        @property
        def conn(self):
            raise sqlite3.OperationalError("backend studio non disponibile")

        def salva_tabella(self, *args, **kwargs):
            raise sqlite3.OperationalError("backend studio non disponibile")

    manager = GestioneUtenti(
        db_path=str(auth_path),
        audit_path=str(audit_path),
        secret_key="test",
        crea_admin_se_vuoto=False,
        studio_db=_BrokenBackend(),
    )

    utenti = manager.lista()

    assert len(utenti) == 1
    assert utenti[0].username == "avvtest"
