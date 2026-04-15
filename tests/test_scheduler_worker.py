from __future__ import annotations

from pathlib import Path

from pct.scheduler_worker import create_scheduler_app, start_scheduler_worker
from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def test_create_scheduler_app_costruisce_worker_leggero(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")

    app = create_scheduler_app(_cfg_web(tmp_path))

    assert app.config["PCT_SCHEDULER_WORKER"] is True
    assert app.config["BACKUP_ORA"] == "03:30"
    assert app.config["WA_REMINDER_ORA"] == "17:15"
    assert app.blueprints == {}
    assert "PCT_SCHEDULER" not in app.config


def test_start_scheduler_worker_registra_job_core(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("PCT_DISABLE_SCHEDULER", raising=False)
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    _write_studio_config(tmp_path / "config" / "studio.json")

    app = start_scheduler_worker(_cfg_web(tmp_path))
    scheduler = app.config.get("PCT_SCHEDULER")
    try:
        assert scheduler is not None
        assert scheduler.get_job("backup_giornaliero") is not None
        assert scheduler.get_job("local_ai_maintenance") is not None
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
