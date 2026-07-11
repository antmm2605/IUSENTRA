"""Test job scheduler del piano del giorno (registrazione, flag, coalesce)."""

from __future__ import annotations

from flask import Flask

from pct.scheduler import start_scheduler
from pct.scheduler_registry import default_scheduler_templates


def _app(**config):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        **config,
    )
    return app


def _start(app, monkeypatch):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    return start_scheduler(app)


def test_job_registrati_con_max_instances_e_coalesce(monkeypatch):
    app = _app()
    scheduler = _start(app, monkeypatch)
    try:
        completo = scheduler.get_job("studio_daily_operational_plan")
        incrementale = scheduler.get_job("daily_plan_incremental_refresh")
        assert completo is not None
        assert incrementale is not None
        assert completo.max_instances == 1
        assert incrementale.max_instances == 1
        assert completo.coalesce is True
        assert incrementale.coalesce is True
        # cron 07:30; lo scheduler di processo è pinnato su Europe/Rome
        # (nota: il reload del registro ricostruisce i trigger col fuso di
        # runtime, comportamento comune a tutti i job built-in esistenti)
        fields = {f.name: str(f) for f in completo.trigger.fields}
        assert fields.get("hour") == "7"
        assert fields.get("minute") == "30"
        assert "Europe/Rome" in str(scheduler.timezone)
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_job_salta_se_flag_scheduled_runs_spento(monkeypatch):
    app = _app(FEATURE_FLAGS={
        "lex.dailyPlan.enabled": True,
        "lex.dailyPlan.scheduledRuns": False,
    })
    scheduler = _start(app, monkeypatch)
    try:
        job = scheduler.get_job("studio_daily_operational_plan")
        esito = job.func()
        assert esito["ok"] is True
        assert esito["skipped"] == "feature_flag_disattivo"

        incrementale = scheduler.get_job("daily_plan_incremental_refresh")
        esito = incrementale.func()
        assert esito["skipped"] == "feature_flag_disattivo"
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_job_esegue_con_flag_attivi_e_riporta_per_tenant(monkeypatch, tmp_path):
    app = _app(
        FEATURE_FLAGS={
            "lex.dailyPlan.enabled": True,
            "lex.dailyPlan.scheduledRuns": True,
        },
        GIURISPRUDENZA_DB=str(tmp_path / "intelligence" / "giurisprudenza.json"),
        AGENDA_DB=str(tmp_path / "agenda" / "appuntamenti.json"),
        SCADENZIARIO_DB=str(tmp_path / "scadenziario" / "scadenze.json"),
        FASCICOLI_DB=str(tmp_path / "fascicoli" / "fascicoli.json"),
        FASCICOLI_DOCS=str(tmp_path / "fascicoli" / "documenti"),
        FASCICOLI_ARCH=str(tmp_path / "fascicoli" / "archivio"),
        AUTH_DB=str(tmp_path / "auth" / "utenti.json"),
        AUDIT_DB=str(tmp_path / "auth" / "audit.json"),
        EMAIL_CASELLA_DB=str(tmp_path / "email" / "casella.json"),
        PREVENTIVI_DB=str(tmp_path / "preventivi" / "preventivi.json"),
        FATTURAZIONE_DB=str(tmp_path / "fatturazione" / "parcelle.json"),
    )
    scheduler = _start(app, monkeypatch)
    try:
        job = scheduler.get_job("studio_daily_operational_plan")
        esito = job.func()
        assert esito["job"] == "studio_daily_operational_plan"
        assert esito["mode"] == "full"
        assert isinstance(esito["tenants"], list) and esito["tenants"]
        assert esito["tenants"][0]["tenant"] == "default"
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_refresh_incrementale_noop_senza_dirty(monkeypatch, tmp_path):
    app = _app(
        FEATURE_FLAGS={
            "lex.dailyPlan.enabled": True,
            "lex.dailyPlan.scheduledRuns": True,
        },
        GIURISPRUDENZA_DB=str(tmp_path / "intelligence" / "giurisprudenza.json"),
    )
    scheduler = _start(app, monkeypatch)
    try:
        job = scheduler.get_job("daily_plan_incremental_refresh")
        esito = job.func()
        totals = esito["totals"]
        assert totals["skipped"] == 1  # niente dirty, niente job in coda → no-op
        assert totals["errors"] == 0
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_template_console_pianificazioni_presenti():
    templates = {t.key: t for t in default_scheduler_templates()}
    assert "studio_daily_operational_plan" in templates
    assert "daily_plan_incremental_refresh" in templates
    completo = templates["studio_daily_operational_plan"]
    assert completo.built_in is True
    assert completo.hour == "7"
    assert completo.minute == "30"
    assert "nessuna scrittura applicativa" in completo.description.lower()
