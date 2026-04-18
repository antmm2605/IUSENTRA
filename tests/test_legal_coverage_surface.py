from __future__ import annotations

import json
from pathlib import Path

from flask import g

from pct.auth import GestioneUtenti, RuoloUtente
from pct.tenant import DatabaseConfig, GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.legal_coverage_surface import build_repository
from pct.legal_coverage_sqlite_repository import SQLiteCoverageRepository


def _seed_superadmin(app) -> tuple[str, str]:
    utenti = GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    utenti.crea(
        username="coverage-superadmin",
        password="Superpass123!",
        ruolo=RuoloUtente.SUPERADMIN,
        tenant_slug="",
        must_change_password=False,
    )
    return "coverage-superadmin", "Superpass123!"


def _write_named_tenant_config(path: str, studio_name: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"studio": {"nome": studio_name}}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_admin_copertura_ai_aggancia_il_tenant_unico_con_postgres_legacy(
    tmp_path: Path,
    monkeypatch,
):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    tenant_manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tenant_manager.crea(
        "Studio Coverage",
        "studio-coverage",
        piano="ENTERPRISE",
        db_config={"mode": "LOCAL"},
    )
    tenant_manager.aggiorna_db_config(
        studio.slug,
        DatabaseConfig(
            mode="LOCAL",
            host="db.example.legacy",
            porta=5432,
            db_name="iusentra",
            utente="postgres",
            password="segreta",
            ssl=True,
            connessione_ok=True,
        ),
    )
    _write_named_tenant_config(
        tenant_manager.percorsi_dati(studio.slug)["CONFIG_STUDIO_DB"],
        "Studio Coverage Operativo",
    )

    username, password = _seed_superadmin(app)
    monkeypatch.setattr(
        "web.services.legal_coverage_surface.PostgresCoverageRepository.ping",
        lambda self: False,
    )

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        assert login.status_code == 302

        page = client.get("/admin/copertura-ai")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "DB configurato: si" in html
    assert "Studio attivo:" in html
    assert "Studio Coverage Operativo" in html
    assert "PostgreSQL tenant-aware" in html
    assert 'name="tenant_slug"' in html


def test_review_copertura_ai_spiega_il_flusso_e_mostra_la_coda(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    tenant_manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tenant_manager.crea(
        "Studio Coverage",
        "studio-coverage",
        piano="ENTERPRISE",
        db_config={"mode": "LOCAL"},
    )

    username, password = _seed_superadmin(app)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        assert login.status_code == 302

        page = client.get(f"/admin/copertura-ai/review?tenant_slug={studio.slug}")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Come si usa questa schermata" in html
    assert "Contesto di retrieval" in html
    assert "Nessuna bozza selezionata." in html


def test_admin_copertura_ai_sqlite_tenant_mostra_database_connesso(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    tenant_manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio = tenant_manager.crea(
        "Studio SQLite",
        "studio-sqlite",
        piano="ENTERPRISE",
        db_config={"mode": "SQLITE"},
    )
    tenant_manager.provision_storage_backend(studio.slug, migrate_existing=False)
    _write_named_tenant_config(
        tenant_manager.percorsi_dati(studio.slug)["CONFIG_STUDIO_DB"],
        "Studio Coverage SQLite",
    )

    username, password = _seed_superadmin(app)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        assert login.status_code == 302

        page = client.get(f"/admin/copertura-ai?tenant_slug={studio.slug}")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Database coverage connesso" in html
    assert "SQLite locale" in html
    assert "Studio Coverage SQLite" in html


def test_build_repository_rispetta_il_tenant_slug_esplicito_anche_in_request_context(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    tenant_manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    studio_sqlite = tenant_manager.crea(
        "Studio SQLite",
        "studio-sqlite",
        piano="ENTERPRISE",
        db_config={"mode": "SQLITE"},
    )
    tenant_manager.provision_storage_backend(studio_sqlite.slug, migrate_existing=False)

    studio_postgres = tenant_manager.crea(
        "Studio PostgreSQL",
        "studio-postgres",
        piano="ENTERPRISE",
        db_config={"mode": "LOCAL"},
    )
    tenant_manager.aggiorna_db_config(
        studio_postgres.slug,
        DatabaseConfig(
            mode="LOCAL",
            host="db.example.legacy",
            porta=5432,
            db_name="iusentra",
            utente="postgres",
            password="segreta",
            ssl=True,
            connessione_ok=True,
        ),
    )

    with app.test_request_context(f"/admin/copertura-ai?tenant_slug={studio_sqlite.slug}"):
        g.tenant = tenant_manager.get(studio_postgres.slug)
        repository = build_repository(tenant_slug=studio_sqlite.slug)

    assert isinstance(repository, SQLiteCoverageRepository)
