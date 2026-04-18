from __future__ import annotations

from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.tenant import DatabaseConfig, GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


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
    assert "DB configurato: sì" in html
    assert "Studio attivo:" in html
    assert "Studio Coverage" in html
    assert 'name="tenant_slug"' in html
