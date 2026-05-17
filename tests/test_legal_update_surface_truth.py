from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from pct.legal_update_pipeline import build_legal_update_pipeline
from pct.scheduler_registry import scheduler_registry_repository
from tests.test_legal_updates_pipeline import (
    DummyResponse,
    _cfg_web,
    _normativa_html,
    _seed_platform_superadmin,
    _write_studio_config,
)
from web.app import create_app
from web.services.legal_update_surface import build_legal_update_surface


def _app_with_admin(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    username, password = _seed_platform_superadmin(app)
    return app, username, password


def _seed_read_not_published_update(app) -> None:
    with app.app_context():
        pipeline = build_legal_update_pipeline(
            app.config["LEGAL_INTELLIGENCE_DB"],
            giurisprudenza_db_path=app.config["GIURISPRUDENZA_DB"],
        )
        pipeline.run_cycle(
            source_codes=["gazzetta_ufficiale"],
            request_get=lambda *args, **kwargs: DummyResponse(
                _normativa_html(),
                url="https://www.gazzettaufficiale.it/",
            ),
            auto_publish=False,
        )
        review = pipeline.repository.list_review_queue(limit=1)[0]
        pipeline.repository.set_review_status(int(review["id"]), "pending", reviewer="test")


def test_metriche_verita_separano_letture_analisi_e_schede_pubblicate(tmp_path: Path):
    app, _, _ = _app_with_admin(tmp_path)
    _seed_read_not_published_update(app)

    with app.app_context():
        payload = build_legal_update_surface(app)

    metrics = payload["truth_metrics"]
    assert metrics["documents_read"] == 1
    assert metrics["documents_analyzed"] == 1
    assert metrics["published_cards"] == 0
    assert metrics["to_verify"] == 1
    assert metrics["conversion_label"] == "1 letti, 1 analizzati, 0 schede pubblicate"


def test_dashboard_non_chiama_acquisite_le_sue_sole_letture(tmp_path: Path):
    app, username, password = _app_with_admin(tmp_path)
    _seed_read_not_published_update(app)

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = client.get("/admin/aggiornamenti-legali")

    html = response.get_data(as_text=True)
    assert login.status_code == 302
    assert response.status_code == 200
    assert "Documenti acquisiti" not in html
    assert "Ultimi documenti acquisiti" not in html
    assert "Documenti letti" in html
    assert "Documenti analizzati" in html
    assert "Schede pubblicate" in html
    assert "Conversione da letture a schede" in html
    assert "0 schede pubblicate" in html


def test_console_pianificazioni_traduce_esiti_legali_senza_falsi_positivi(tmp_path: Path):
    app, username, password = _app_with_admin(tmp_path)
    with app.app_context():
        repo = scheduler_registry_repository(app.config)
        repo.upsert_default_jobs(app.config)
        repo.record_scheduler_event(
            "legal_updates_gazzetta",
            status="completed",
            result={
                "ok": True,
                "report": {
                    "reports": [{"documents_found": 2, "processed": 2, "skipped_unchanged": 0}],
                    "autopublished": {"count": 0},
                },
            },
        )
        repo.record_scheduler_event(
            "legal_updates_batch",
            status="completed",
            result={
                "ok": True,
                "report": {
                    "reports": [
                        {
                            "documents_found": 1,
                            "processed": 0,
                            "error": "Fonte non raggiungibile",
                        }
                    ],
                    "autopublished": {"count": 0},
                },
            },
        )
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with repo.connect() as conn:
            conn.execute(
                """
                INSERT INTO scheduled_job_runs (
                    run_id, job_id, template_key, origin, status, scheduled_at,
                    started_at, finished_at, duration_ms, message, result_json,
                    error_message, requested_by, created_at
                )
                VALUES (
                    'old-running', 'legal_monitor_daily', 'legal_monitor_daily', 'scheduler',
                    'running', ?, ?, '', 0, 'Esecuzione in corso.', '{}', '', '', ?
                )
                """,
                (old, old, old),
            )

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = client.get("/admin/pianificazioni")

    html = response.get_data(as_text=True)
    assert login.status_code == 302
    assert response.status_code == 200
    assert "Controllo completato, nessuna scheda pubblicata" in html
    assert "Fonte non raggiungibile" in html
    assert "Da verificare" in html
    assert "Interrotto, da verificare" in html
