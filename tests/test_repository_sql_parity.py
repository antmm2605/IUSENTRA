from __future__ import annotations

from pathlib import Path

from flask import Flask

from pct.giurisprudenza_repository import GestioneRepositoryGiurisprudenza
from pct.legal_intelligence_repository import GestioneLegalIntelligenceRepository
from pct.template_atti_repository import GestioneTemplateRepository
from pct.tenant import DatabaseConfig, DbMode, GestioneTenant
from pct.workspace_intelligence_repository import WorkspaceIntelligenceRepository
from web.services.legal_coverage_surface import build_repository


def test_template_repository_salva_runtime_e_preferenze(tmp_path: Path):
    repo = GestioneTemplateRepository(str(tmp_path / "template_repository.db"))

    repo.save_runtime_state([{"id": "tpl-1", "titolo": "Diffida", "builtin": False}])
    repo.save_editor_preferences({"font_family": "source_serif", "font_size_pt": 12})

    assert repo.load_runtime_state()[0]["id"] == "tpl-1"
    assert repo.load_editor_preferences()["font_family"] == "source_serif"
    assert repo.storage_stats()["template_runtime_state"] == 1
    assert repo.storage_stats()["template_editor_preferences"] == 1


def test_legal_intelligence_repository_salva_runtime_state(tmp_path: Path):
    repo = GestioneLegalIntelligenceRepository(str(tmp_path / "legal_repository.db"))

    repo.save_runtime_state(
        {
            "monitor_runs": [{"id": "run-1", "status": "ok"}],
            "alerts": [{"id": "alert-1", "severity": "high"}],
            "audit_traces": [{"id": "trace-1", "query": "normattiva"}],
        }
    )

    payload = repo.load_runtime_state()

    assert payload["monitor_runs"][0]["id"] == "run-1"
    assert payload["alerts"][0]["id"] == "alert-1"
    assert repo.storage_stats()["legal_runtime_state"] == 1


def test_giurisprudenza_repository_salva_runtime_state(tmp_path: Path):
    repo = GestioneRepositoryGiurisprudenza(str(tmp_path / "giurisprudenza_repository.db"))

    repo.save_runtime_state(
        {
            "storage_version": 2,
            "judgments": [{"id": "jud-1", "titolo": "Sentenza test"}],
            "ingestion_runs": [{"id": "sync-1", "status": "ok"}],
        }
    )

    payload = repo.load_runtime_state()

    assert payload["storage_version"] == 2
    assert payload["judgments"][0]["id"] == "jud-1"
    assert repo.storage_stats()["giurisprudenza_runtime_state"] == 1


def test_workspace_intelligence_repository_salva_snapshot(tmp_path: Path):
    repo = WorkspaceIntelligenceRepository(str(tmp_path / "workspace_repository.db"))

    repo.save_snapshot(
        {
            "generated_at": "2026-04-18T12:00:00",
            "overview": {"summary": {"fascicoli_attenzionati": 3}},
        }
    )

    payload = repo.load_snapshot()

    assert payload["generated_at"] == "2026-04-18T12:00:00"
    assert payload["overview"]["summary"]["fascicoli_attenzionati"] == 3
    assert repo.storage_stats()["workspace_intelligence_snapshots"] == 1


def test_coverage_surface_usa_database_tenant_postgresql_come_fallback():
    app = Flask(__name__)
    app.config["TENANT_DATABASE_CONFIG"] = DatabaseConfig(
        mode=DbMode.POSTGRESQL,
        host="db.example.test",
        porta=5432,
        db_name="iusentra",
        utente="postgres",
        password="segreta",
        ssl=True,
    )

    repository = build_repository(app)

    assert repository.config.configured is True
    assert repository.config.dsn.startswith("postgresql://")
    assert "db.example.test" in repository.config.dsn


def test_coverage_surface_usa_tenant_unico_con_configurazione_postgres_legacy(tmp_path: Path):
    app = Flask(__name__)
    registry_path = tmp_path / "tenants-coverage.json"
    app.config["TENANTS_REGISTRY"] = str(registry_path)
    tenant_manager = GestioneTenant(str(registry_path))
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

    repository = build_repository(app)

    assert repository.config.configured is True
    assert repository.config.dsn.startswith("postgresql://")
    assert "db.example.legacy" in repository.config.dsn
