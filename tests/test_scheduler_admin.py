from __future__ import annotations

from pathlib import Path

from web.app import create_app

from tests.test_legal_updates_pipeline import _cfg_web, _seed_platform_superadmin, _write_studio_config


def test_superadmin_puo_aprire_console_pianificazioni(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = client.get("/admin/pianificazioni")
        alias = client.get("/admin/cronjob", follow_redirects=False)

    assert login.status_code == 302
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Pianificazioni" in html
    assert "Agenti delegati disponibili" in html
    assert "Agenti fonte legale" in html
    assert "Fonte legale: Gazzetta Ufficiale" in html
    assert "Agente clienti e soggetti" in html
    assert "Agente email PEC" in html
    assert alias.status_code == 302
    assert alias.headers["Location"].endswith("/admin/pianificazioni")


def test_superadmin_crea_e_modifica_cronjob_agente(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        create = client.post(
            "/admin/pianificazioni/crea",
            data={
                "_csrf_token": "test",
                "template_key": "agent_clienti_soggetti",
                "name": "Controllo clienti serale",
                "trigger_kind": "cron",
                "hour": "22",
                "minute": "45",
                "interval_minutes": "60",
                "enabled": "1",
            },
            follow_redirects=True,
        )
        page = create.get_data(as_text=True)

    assert create.status_code == 200
    assert "Controllo clienti serale" in page
    assert "Ogni giorno alle 22:45" in page
    assert "agente delegato" in page


def test_superadmin_puo_richiedere_esecuzione_cronjob(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = client.post(
            "/admin/pianificazioni/legal_updates_batch/esegui",
            data={"_csrf_token": "test"},
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Esecuzione richiesta" in html
    assert "Richiesta" in html


def test_superadmin_annulla_fonti_legali_in_corso_senza_toccare_altri_job(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.app_context():
        from pct.scheduler_registry import scheduler_registry_repository

        repo = scheduler_registry_repository(app.config)
        repo.upsert_default_jobs(app.config)
        with repo.connect() as conn:
            for run_id, job_id in (
                ("run-legal-source", "legal_source_cassazione_massimario"),
                ("run-legal-batch", "legal_updates_batch"),
                ("run-ai", "local_ai_maintenance"),
            ):
                conn.execute(
                    """
                    INSERT INTO scheduled_job_runs (
                        run_id, job_id, template_key, origin, status, scheduled_at,
                        started_at, finished_at, duration_ms, message, result_json,
                        error_message, requested_by, created_at
                    )
                    VALUES (?, ?, ?, 'scheduler', 'running',
                        '2026-05-17T13:00:00Z', '2026-05-17T13:00:00Z',
                        '', 0, 'Esecuzione in corso.', '{}', '', '', '2026-05-17T13:00:00Z')
                    """,
                    (run_id, job_id, job_id),
                )

    with app.test_client() as client:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = client.post(
            "/admin/pianificazioni/fonti-legali/annulla",
            data={"_csrf_token": "test"},
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)

    with app.app_context():
        repo = scheduler_registry_repository(app.config)
        with repo.connect() as conn:
            statuses = {
                row["run_id"]: row["status"]
                for row in conn.execute(
                    "SELECT run_id, status FROM scheduled_job_runs WHERE run_id IN ('run-legal-source', 'run-legal-batch', 'run-ai')"
                ).fetchall()
            }

    assert response.status_code == 200
    assert "Controlli fonti legali annullati: 2 esecuzioni aperte chiuse." in html
    assert "Archivio legale verificato" in html
    assert "Annullata" in html
    assert statuses == {
        "run-legal-source": "cancelled",
        "run-legal-batch": "cancelled",
        "run-ai": "running",
    }
