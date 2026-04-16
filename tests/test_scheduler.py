from __future__ import annotations

from flask import Flask

from pct.scheduler import start_scheduler


def test_local_ai_maintenance_salta_su_runtime_cloud_hosted(monkeypatch):
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "proj-test")
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
    )

    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job("local_ai_maintenance")
        assert job is not None

        import pct.local_ai as local_ai_module

        class ForbiddenLocalAIService:
            def __init__(self, *args, **kwargs):
                raise AssertionError("LocalAIService non deve partire su runtime cloud-hosted")

        monkeypatch.setattr(local_ai_module, "LocalAIService", ForbiddenLocalAIService)
        job.func()
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
        monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)


def test_start_scheduler_rispetta_flag_disable(monkeypatch):
    monkeypatch.setenv("PCT_DISABLE_SCHEDULER", "1")
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
    )

    scheduler = start_scheduler(app)

    assert scheduler is None
    assert "PCT_SCHEDULER" not in app.config
    monkeypatch.delenv("PCT_DISABLE_SCHEDULER", raising=False)


def test_start_scheduler_non_parte_senza_worker_o_override(monkeypatch):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    monkeypatch.delenv("PCT_ALLOW_INLINE_SCHEDULER", raising=False)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
    )

    scheduler = start_scheduler(app)

    assert scheduler is None
    assert "PCT_SCHEDULER" not in app.config
