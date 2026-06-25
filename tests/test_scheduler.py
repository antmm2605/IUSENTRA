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


def test_lex_sentenza_economia_job_lancia_backfill_automatico(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    registry = tmp_path / "tenants.json"
    registry.write_text("{}", encoding="utf-8")
    calls: list[dict] = []

    import scripts.backfill_sentenza_lex_economics as backfill_module

    def fake_run_backfill(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "source_of_truth": "sqlite/postgresql runtime repositories",
            "totals": {
                "documents_seen": 4,
                "sentenze_found": 1,
                "unique_fascicoli_confirmed": 1,
                "applied": 1,
                "vector_indexed": 1,
                "context_mismatch_skipped": 3,
            },
        }

    monkeypatch.setattr(backfill_module, "run_backfill", fake_run_backfill)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        PCT_DATA_ROOT=str(tmp_path),
        TENANTS_REGISTRY=str(registry),
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
    )

    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job("lex_sentenza_economia_auto")
        assert job is not None

        result = job.func()

        assert result["ok"] is True
        assert result["job"] == "lex_sentenza_economia_auto"
        assert result["totals"]["applied"] == 1
        assert calls
        call = calls[0]
        assert call["apply"] is True
        assert call["skip_lex"] is False
        assert call["data_root"] == tmp_path
        assert call["registry"] == registry
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_pst_certificati_scheduler_non_forza_refresh_remoto_di_default(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    monkeypatch.delenv("PCT_PST_CERTIFICATI_CIFRATURA_FORCE_REFRESH", raising=False)
    calls: list[dict] = []

    import pct.pst_cifratura as pst_cifratura

    def fake_controllo(*, force_refresh=False, max_workers=6):
        calls.append({"force_refresh": force_refresh, "max_workers": max_workers})
        return {
            "ok": True,
            "totale": 1,
            "scaricati_o_validi": 1,
            "errori": 0,
            "report_path": str(tmp_path / "audit.json"),
        }

    monkeypatch.setattr(
        pst_cifratura,
        "esegui_controllo_settimanale_certificati_cifratura",
        fake_controllo,
    )

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
    )

    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job("pst_certificati_cifratura_weekly")
        assert job is not None

        result = job.func()

        assert result["ok"] is True
        assert calls == [{"force_refresh": False, "max_workers": 6}]
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
