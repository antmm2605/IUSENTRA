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

    riprese: list[object] = []
    monkeypatch.setattr(
        "web.services.archivio_letture_runtime.riprendi_eventi_lettura",
        lambda app: riprese.append(app) or {"tenant": 1, "trovati": 0, "avviati": 0},
    )
    app = start_scheduler_worker(_cfg_web(tmp_path))
    scheduler = app.config.get("PCT_SCHEDULER")
    try:
        assert scheduler is not None
        assert scheduler.get_job("backup_giornaliero") is not None
        assert scheduler.get_job("local_ai_maintenance") is not None
        assert scheduler.get_job("lex_sentenza_economia_auto") is not None
        assert scheduler.get_job("lex_operational_agents_nightly") is not None
        assert scheduler.get_job("lex_dataset_nightly") is not None
        assert scheduler.get_job("legal_official_archives_daily") is not None
        assert scheduler.get_job("legal_updates_batch") is not None
        cortecost = scheduler.get_job("corte_costituzionale_opendata_weekly")
        assert cortecost is not None
        assert "day_of_week='sat'" in str(cortecost.trigger)
        comandi: list[list[str]] = []
        monkeypatch.setattr(
            "pct.scheduler._run_scheduler_command",
            lambda label, command, timeout_seconds: comandi.append(command) or {"ok": True},
        )
        cortecost.func()
        assert comandi and comandi[0][1] == "tools/cortecost_importa.py"
        assert {"--scarica", "--tutti-i-tenant"} <= set(comandi[0])
        assert comandi[0][comandi[0].index("--periodi") + 1] == "2001_oggi"
        assert comandi[0][comandi[0].index("--anni-recenti") + 1] == "2"
        registry_tick = scheduler.get_job("scheduler_registry_reload")
        assert registry_tick is not None
        # Lo scheduler qui e' avviato davvero, e questo job ha un trigger al
        # minuto: se il test attraversa lo scoccare del minuto, il tick parte
        # da solo e la ripresa risulta chiamata due volte. Non e' un difetto —
        # e' il job che fa il suo mestiere — ma faceva rosso un turno su
        # cinque, e sempre in una scheggia diversa. Si azzera il conto e si
        # guarda solo quello che fa il tick chiamato qui.
        riprese.clear()
        registry_tick.func()
        assert riprese, "il tick del registro non ha ripreso le letture"
        assert all(ripresa is app for ripresa in riprese), (
            f"la ripresa e' stata chiamata con un'altra applicazione: {riprese}"
        )
        assert scheduler.get_job("mailbox_sync_runtime") is not None
        assert scheduler.get_job("poll_pec_cancelleria") is not None
        assert "hour='23'" in str(scheduler.get_job("legal_official_archives_daily").trigger)
        assert "minute='0'" in str(scheduler.get_job("legal_official_archives_daily").trigger)
        assert "hour='23'" in str(scheduler.get_job("legal_updates_batch").trigger)
        assert "hour='1'" in str(scheduler.get_job("lex_dataset_nightly").trigger)
        assert "minute='45'" in str(scheduler.get_job("lex_dataset_nightly").trigger)
        # Il worker prende l'orario dal registro, non dal CronTrigger scritto
        # nel codice: e' proprio questo che rende obbligatoria la migrazione.
        trigger_lex = str(scheduler.get_job("lex_sentenza_economia_auto").trigger)
        assert "hour='3'" in trigger_lex
        assert "minute='25'" in trigger_lex
        assert scheduler.get_job("operational_crash_morning") is not None
        assert scheduler.get_job("operational_crash_midday") is not None
        assert scheduler.get_job("operational_crash_evening") is not None
        assert scheduler.get_job("operational_backup_nightly") is not None
        assert scheduler.get_job("backup_giornaliero").next_run_time is None
        assert scheduler.get_job("operational_backup_nightly").next_run_time is None
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_scheduler_backup_jobs_non_creano_archivi_quando_disabilitati(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("IUSENTRA_DISABLE_BACKUP_JOBS", "1")
    monkeypatch.delenv("PCT_DISABLE_SCHEDULER", raising=False)
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    _write_studio_config(tmp_path / "config" / "studio.json")

    app = start_scheduler_worker(_cfg_web(tmp_path))
    scheduler = app.config.get("PCT_SCHEDULER")
    try:
        assert scheduler is not None
        giornaliero = scheduler.get_job("backup_giornaliero")
        notturno = scheduler.get_job("operational_backup_nightly")
        assert giornaliero is not None
        assert notturno is not None
        assert giornaliero.next_run_time is None
        assert notturno.next_run_time is None
        assert giornaliero.func() == {
            "ok": True,
            "skipped": True,
            "reason": "backup_jobs_disabled",
        }
        assert notturno.func() == {
            "ok": True,
            "skipped": True,
            "reason": "backup_jobs_disabled",
        }
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
