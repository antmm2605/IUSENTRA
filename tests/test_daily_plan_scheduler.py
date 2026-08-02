"""Test job scheduler del piano del giorno (registrazione, flag, coalesce)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Flask

from pct.daily_plan.clock import ROME_TZ
from pct.scheduler import daily_plan_startup_recovery_allowed, start_scheduler
from pct.scheduler_registry import default_scheduler_templates
from web.services import daily_plan_runtime


def _app(tmp_path: Path | None = None, **config):
    app = Flask(__name__)
    defaults = {
        # Il default ON di produzione non deve avviare lavoro in background
        # nei test che verificano soltanto la registrazione APScheduler.
        "FEATURE_FLAGS": {
            "lex.dailyPlan.enabled": True,
            "lex.dailyPlan.scheduledRuns": False,
        },
        "SECRET_KEY": "test",
        "BACKUP_ORA": "02:00",
        "WA_REMINDER_ORA": "18:00",
        "PCT_SCHEDULER_WORKER": True,
        "PCT_SCHEDULER_NOW_FOR_TESTS": datetime(2026, 7, 11, 4, 0, tzinfo=ROME_TZ),
    }
    if tmp_path is not None:
        defaults["SCHEDULER_REGISTRY_DB"] = str(tmp_path / "scheduler_registry.sqlite3")
    defaults.update(config)
    app.config.update(defaults)
    return app


def _start(app, monkeypatch):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    return start_scheduler(app)


def test_job_registrati_con_max_instances_e_coalesce(monkeypatch, tmp_path):
    app = _app(tmp_path)
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
        assert fields.get("hour") == "5"
        assert fields.get("minute") == "30"
        assert "Europe/Rome" in str(scheduler.timezone)
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_job_mattutino_salta_ma_incrementale_consuma_solo_coda_manual(monkeypatch, tmp_path):
    calls = []

    def fake_run(_app, *, mode, include_dirty=True, **_kwargs):
        calls.append({"mode": mode, "include_dirty": include_dirty})
        return {
            "ok": True,
            "job": "daily_plan_incremental_refresh",
            "mode": mode,
            "tenants": [],
            "totals": {"tenants": 0, "skipped": 1, "errors": 0, "items_written": 0},
        }

    monkeypatch.setattr(
        "web.services.daily_plan_runtime.run_daily_plan_for_all_tenants", fake_run
    )
    app = _app(tmp_path, FEATURE_FLAGS={
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
        assert esito["ok"] is True
        assert calls == [{"mode": "incremental", "include_dirty": False}]
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_job_esegue_con_flag_attivi_e_riporta_per_tenant(monkeypatch, tmp_path):
    app = _app(
        tmp_path,
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
        tmp_path,
        FEATURE_FLAGS={
            "lex.dailyPlan.enabled": True,
            "lex.dailyPlan.scheduledRuns": False,
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
    assert completo.hour == "5"
    assert completo.minute == "30"
    assert "nessuna scrittura applicativa" in completo.description.lower()


def test_startup_recovery_rispetta_finestra_misfire_e_console():
    at_0545 = datetime(2026, 7, 11, 5, 45, tzinfo=ROME_TZ)
    at_0600 = datetime(2026, 7, 11, 6, 0, tzinfo=ROME_TZ)
    default_job = {
        "enabled": True,
        "updated_by": "system",
        "trigger_kind": "cron",
        "hour": "5",
        "minute": "30",
    }

    assert daily_plan_startup_recovery_allowed(at_0545, default_job) is False
    assert daily_plan_startup_recovery_allowed(at_0600, default_job) is True
    assert daily_plan_startup_recovery_allowed(
        at_0600,
        {**default_job, "enabled": False, "updated_by": "avvocato"},
    ) is False
    assert daily_plan_startup_recovery_allowed(
        at_0600,
        {**default_job, "updated_by": "avvocato", "hour": "8", "minute": "15"},
    ) is False


def test_boot_nella_finestra_misfire_non_aggiunge_un_secondo_recovery(monkeypatch, tmp_path):
    app = _app(
        tmp_path,
        FEATURE_FLAGS={
            "lex.dailyPlan.enabled": True,
            "lex.dailyPlan.scheduledRuns": True,
        },
        PCT_SCHEDULER_NOW_FOR_TESTS=datetime(2026, 7, 11, 5, 45, tzinfo=ROME_TZ),
    )
    scheduler = _start(app, monkeypatch)
    try:
        assert scheduler.get_job("daily_plan_startup_recovery") is None
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_consumer_passa_al_servizio_la_data_del_job(monkeypatch):
    calls = []

    class FakeRepository:
        claimed = False

        def claim_next_job(self, job_type):
            if job_type == "full_rebuild" or self.claimed:
                return None
            self.claimed = True
            return {
                "id": "job-futuro",
                "payload": {"target_date": "2026-07-13"},
            }

        def pending_dirty_count(self):
            return 0

        def finish_job(self, job_id, *, status, report):
            calls.append({"finished": job_id, "status": status, "report": report})

    class FakeService:
        def __init__(self):
            self.repository = FakeRepository()

        def refresh_incremental(self, *, target_date, actor):
            calls.append({"target_date": target_date, "actor": actor})
            return {
                "ok": True,
                "mode": "incremental",
                "target_date": target_date,
                "items_written": 0,
                "users_planned": 1,
                "signals_upserted": 0,
            }

    service = FakeService()
    monkeypatch.setattr(daily_plan_runtime, "service_from_paths", lambda *_a, **_k: service)
    monkeypatch.setattr(
        "web.services.fascicoli_presidi_runtime._active_tenants",
        lambda _app: [],
    )
    app = _app()

    result = daily_plan_runtime.run_daily_plan_for_all_tenants(
        app,
        mode="incremental",
        include_dirty=False,
    )

    assert result["ok"] is True
    assert calls[0]["target_date"] == "2026-07-13"
    assert calls[1]["finished"] == "job-futuro"


def test_incrementale_recupera_snapshot_mancanti_senza_scansioni_ui(monkeypatch):
    calls = []

    class FakeRepository:
        def claim_next_job(self, _job_type):
            return None

        def pending_dirty_count(self):
            return 0

    class FakeService:
        def __init__(self):
            self.repository = FakeRepository()

        def missing_snapshot_user_ids(self):
            return {"", "u1"}

        def rebuild_full(self, *, target_date, actor):
            calls.append({"mode": "full", "target_date": target_date, "actor": actor})
            return {
                "ok": True,
                "mode": "full",
                "target_date": target_date,
                "items_written": 4,
                "users_planned": 2,
                "signals_upserted": 4,
            }

    service = FakeService()
    monkeypatch.setattr(daily_plan_runtime, "service_from_paths", lambda *_a, **_k: service)
    monkeypatch.setattr(
        "web.services.fascicoli_presidi_runtime._active_tenants",
        lambda _app: [],
    )

    result = daily_plan_runtime.run_daily_plan_for_all_tenants(
        _app(),
        mode="incremental",
        include_dirty=False,
        ensure_today_snapshots=True,
    )

    assert calls and calls[0]["mode"] == "full"
    assert result["ok"] is True
    assert result["totals"]["items_written"] == 4


def test_incrementale_recupera_oggi_prima_di_una_coda_futura(monkeypatch):
    calls = []

    class FakeRepository:
        claim_calls = []

        def claim_next_job(self, job_type):
            self.claim_calls.append(job_type)
            return {
                "id": "job-futuro",
                "payload": {"target_date": "2026-07-13"},
            }

        def pending_dirty_count(self):
            return 0

    class FakeService:
        def __init__(self):
            self.repository = FakeRepository()

        def missing_snapshot_user_ids(self):
            return {"", "u1"}

        def rebuild_full(self, *, target_date, actor):
            calls.append({"target_date": target_date, "actor": actor})
            return {
                "ok": True,
                "mode": "full",
                "items_written": 2,
                "users_planned": 2,
                "signals_upserted": 2,
            }

    service = FakeService()
    monkeypatch.setattr(daily_plan_runtime, "service_from_paths", lambda *_a, **_k: service)
    monkeypatch.setattr("web.services.fascicoli_presidi_runtime._active_tenants", lambda _app: [])

    result = daily_plan_runtime.run_daily_plan_for_all_tenants(
        _app(),
        mode="incremental",
        include_dirty=False,
        ensure_today_snapshots=True,
    )

    assert result["ok"] is True
    assert calls == [{"target_date": "", "actor": "IUSENTRA scheduler"}]
    assert service.repository.claim_calls == []


def test_passata_mattutina_non_consuma_un_job_manuale_futuro(monkeypatch):
    calls = []

    class FakeRepository:
        claim_calls = []

        def claim_next_job(self, job_type):
            self.claim_calls.append(job_type)
            return {
                "id": "job-futuro",
                "payload": {"target_date": "2026-07-13"},
            }

    class FakeService:
        def __init__(self):
            self.repository = FakeRepository()

        def rebuild_full(self, *, target_date, actor):
            calls.append({"target_date": target_date, "actor": actor})
            return {
                "ok": True,
                "mode": "full",
                "items_written": 3,
                "users_planned": 1,
                "signals_upserted": 3,
            }

    service = FakeService()
    monkeypatch.setattr(daily_plan_runtime, "service_from_paths", lambda *_a, **_k: service)
    monkeypatch.setattr("web.services.fascicoli_presidi_runtime._active_tenants", lambda _app: [])

    result = daily_plan_runtime.run_daily_plan_for_all_tenants(
        _app(), mode="full", scheduled_daily=True
    )

    assert result["ok"] is True
    assert calls == [{"target_date": "", "actor": "IUSENTRA scheduler"}]
    assert service.repository.claim_calls == []
