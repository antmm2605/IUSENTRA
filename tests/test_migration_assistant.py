import json
from pathlib import Path

from pct.tenant import GestioneTenant
from web.app import create_app
from web.services.migration_assistant import build_migration_assistant, execute_migration_assistant

from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def test_admin_assistente_migrazione_esegui_reindirizza_sullo_studio(tmp_path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Migrazione", "studio-migrazione", db_config={"mode": "SQLITE"})

    app = create_app({**_cfg_web(tmp_path), "TENANTS_REGISTRY": str(registry)})

    monkeypatch.setattr(
        "web.blueprints.admin.execute_migration_assistant",
        lambda *, selected_slug, target: {"report_path": str(Path(tmp_path) / "report.json")},
    )

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code == 302

        response = client.post(
            "/admin/assistente-migrazione/esegui",
            data={"slug": studio.slug, "target": "sqlite"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/admin/assistente-migrazione?slug={studio.slug}"
    )


def test_build_migration_assistant_rileva_postgres_anche_se_storage_corrente_e_json(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea(
        "Studio PostgreSQL",
        "studio-postgres",
        db_config={
            "mode": "LOCAL",
            "host": "db.example.local",
            "porta": 5432,
            "db_name": "iusentra",
            "utente": "iusentra",
            "password": "secret",
        },
    )

    app = create_app({**_cfg_web(tmp_path), "TENANTS_REGISTRY": str(registry)})
    with app.app_context():
        payload = build_migration_assistant(selected_slug=studio.slug)

    assert payload["selected_studio"]["selected_mode"] == "JSON"
    assert payload["can_run_postgres"] is True


def test_execute_migration_assistant_attiva_postgres_con_cutover_reale(tmp_path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea(
        "Studio PostgreSQL",
        "studio-postgres",
        db_config={
            "mode": "LOCAL",
            "host": "db.example.local",
            "porta": 5432,
            "db_name": "iusentra",
            "utente": "iusentra",
            "password": "secret",
        },
    )
    app = create_app({**_cfg_web(tmp_path), "TENANTS_REGISTRY": str(registry)})

    calls = {}

    def _fake_test(self, slug):
        calls["tested_slug"] = slug
        studio_live = self.get(slug)
        calls["tested_mode"] = studio_live.database.normalized_mode
        return {"ok": True, "messaggio": "ok", "latenza_ms": 3}

    def _fake_provision(self, slug, migrate_existing, activate_external=False, secret_key=""):
        calls["provisioned_slug"] = slug
        calls["activate_external"] = activate_external
        calls["provisioned_mode"] = self.get(slug).database.normalized_mode
        return {
            "ok": True,
            "activated": activate_external,
            "migration_report": {
                "target": "postgresql",
                "success": True,
                "report_path": str(Path(tmp_path) / "report-postgres.json"),
            },
        }

    monkeypatch.setattr("pct.tenant.GestioneTenant.testa_connessione", _fake_test)
    monkeypatch.setattr("pct.tenant.GestioneTenant.provision_storage_backend", _fake_provision)

    with app.app_context():
        report = execute_migration_assistant(selected_slug=studio.slug, target="postgresql")

    assert report["target"] == "postgresql"
    assert calls["tested_slug"] == studio.slug
    assert calls["tested_mode"] == "POSTGRESQL"
    assert calls["provisioned_mode"] == "POSTGRESQL"
    assert calls["activate_external"] is True


def test_admin_assistente_migrazione_renderizza_esito_reale_con_report(tmp_path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Migrazione", "studio-migrazione", db_config={"mode": "SQLITE"})
    report_path = tmp_path / "report-migrazione.json"
    report_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-19T10:30:00",
                "target": "sqlite",
                "success": True,
                "report_path": str(report_path),
                "core": {
                    "riuscita": True,
                    "record_migrati": {"clienti": 4, "fascicoli": 2, "appuntamenti": 1},
                    "errori": [],
                    "avvisi": ["timesheet: nessun record legacy presente."],
                },
                "repositories": {
                    "template_atti": {"ok": True, "sqlite_stats": {"template_atti": 18}},
                    "coverage_ai": {"ok": True, "sqlite_stats": {"drafts": 3, "snapshots": 4}},
                },
                "documents": {"count": 12},
                "diff_summary": {
                    "summary": {
                        "rows_total": 2,
                        "matched": 2,
                        "mismatched": 0,
                        "source_label": "JSON legacy",
                        "destination_label": "SQL locale",
                    },
                    "rows": [
                        {
                            "code": "clienti",
                            "title": "Clienti",
                            "source_label": "JSON legacy",
                            "source_count": 4,
                            "destination_label": "SQL locale",
                            "destination_count": 4,
                            "delta": 0,
                            "status": "success",
                            "status_label": "Allineato",
                        }
                    ],
                },
                "rollback": {
                    "status": "success",
                    "label": "Recovery locale disponibile",
                    "detail": "Le sorgenti legacy restano disponibili.",
                    "steps": ["Conserva il report.", "Riesegui il precheck."],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    app = create_app({**_cfg_web(tmp_path), "TENANTS_REGISTRY": str(registry)})

    monkeypatch.setattr(
        "web.blueprints.admin.execute_migration_assistant",
        lambda *, selected_slug, target: {
            "target": target,
            "generated_at": "2026-04-19T10:30:00",
            "report_path": str(report_path),
        },
    )

    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert login.status_code == 302

        response = client.post(
            "/admin/assistente-migrazione/esegui",
            data={"slug": studio.slug, "target": "sqlite"},
            follow_redirects=True,
        )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Ultima esecuzione reale" in html
    assert "Migrazione completata" in html
    assert "Clienti" in html
    assert "Repository strutturati" in html
    assert "Diff pre / post migrazione" in html
    assert "Rollback e recovery guidato" in html
    assert str(report_path) in html


def test_admin_assistente_migrazione_renderizza_errori_e_rimedi(tmp_path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea(
        "Studio PostgreSQL",
        "studio-postgres",
        db_config={
            "mode": "POSTGRESQL",
            "host": "db.example.local",
            "porta": 5432,
            "db_name": "iusentra",
            "utente": "iusentra",
            "password": "secret",
        },
    )

    app = create_app({**_cfg_web(tmp_path), "TENANTS_REGISTRY": str(registry)})

    def _raise_execute(*, selected_slug, target):
        raise RuntimeError("Connessione PostgreSQL non disponibile")

    monkeypatch.setattr("web.blueprints.admin.execute_migration_assistant", _raise_execute)

    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert login.status_code == 302

        response = client.post(
            "/admin/assistente-migrazione/esegui",
            data={"slug": studio.slug, "target": "postgresql"},
            follow_redirects=True,
        )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Esecuzione non completata" in html
    assert "Come risolvere" in html
    assert "Verifica host, porta, nome database, utente e password nello studio selezionato." in html


def test_build_migration_assistant_tollera_report_postgres_con_metadata_stringhe(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Report", "antonella-mammola", db_config={"mode": "POSTGRESQL"})
    paths = tm.percorsi_dati(studio.slug)
    report_path = Path(paths["BACKUP_DIR"]) / "storage_migration_full_postgresql_antonella-mammola_20260419_120000.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-19T12:00:00",
                "target": "postgresql",
                "success": True,
                "report_path": str(report_path),
                "sqlite_stage": {
                    "success": True,
                    "core": {"avvisi": []},
                },
                "core": {
                    "success": True,
                    "consistency": {
                        "clienti": {"json": 10, "sqlite": 10, "postgres": 10, "ok": True},
                    },
                },
                "repositories": {
                    "template_atti": {
                        "ok": True,
                        "postgres_stats": {
                            "db_path": str(tmp_path / "tenant" / "template_repository.db"),
                            "backend_kind": "postgresql",
                            "template_repository": 18,
                            "template_blocks": 18,
                        },
                    },
                    "coverage_ai": {
                        "ok": True,
                        "postgres_stats": {"snapshots": 4, "open_gaps": 2, "drafts": 1},
                    },
                },
                "repository_errors": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    app = create_app({**_cfg_web(tmp_path), "TENANTS_REGISTRY": str(registry)})
    with app.app_context():
        payload = build_migration_assistant(selected_slug=studio.slug)

    assert payload["last_execution"] is not None
    assert payload["last_execution"]["success"] is True
    repository_rows = payload["last_execution"]["repository_rows"]
    template_row = next(row for row in repository_rows if row["label"] == "Template atti")
    assert template_row["status"] == "success"
    assert "18" in template_row["detail"]


def test_build_migration_assistant_prefersce_il_report_piu_recente_rispetto_alla_sessione(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    registry = tmp_path / "tenants.json"
    tm = GestioneTenant(str(registry))
    studio = tm.crea("Studio Recente", "antonella-mammola", db_config={"mode": "SQLITE"})
    paths = tm.percorsi_dati(studio.slug)
    backup_dir = Path(paths["BACKUP_DIR"])
    backup_dir.mkdir(parents=True, exist_ok=True)

    old_report = backup_dir / "storage_migration_full_sqlite_antonella-mammola_20260419_090000.json"
    latest_report = backup_dir / "storage_migration_full_sqlite_antonella-mammola_20260419_120000.json"

    old_report.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-19T09:00:00",
                "target": "sqlite",
                "success": True,
                "report_path": str(old_report),
                "core": {"record_migrati": {"clienti": 1}, "errori": [], "avvisi": ["warning vecchio"]},
                "repositories": {"coverage_ai": {"ok": True, "sqlite_stats": {"drafts": 0}}},
                "documents": {"count": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    latest_report.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-19T12:00:00",
                "target": "sqlite",
                "success": True,
                "report_path": str(latest_report),
                "core": {"record_migrati": {"clienti": 5}, "errori": [], "avvisi": []},
                "repositories": {"coverage_ai": {"ok": True, "sqlite_stats": {"drafts": 2}}},
                "documents": {"count": 7},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    app = create_app({**_cfg_web(tmp_path), "TENANTS_REGISTRY": str(registry)})
    with app.app_context():
        payload = build_migration_assistant(
            selected_slug=studio.slug,
            execution_state={
                "slug": studio.slug,
                "target": "sqlite",
                "report_path": str(old_report),
                "generated_at": "2026-04-19T09:00:00",
            },
        )

    assert payload["last_execution"] is not None
    assert payload["last_execution"]["report_path"] == str(latest_report)
    assert payload["last_execution"]["summary_cards"][0]["value"] == 5
