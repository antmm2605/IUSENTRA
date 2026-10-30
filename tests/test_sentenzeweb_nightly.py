from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from pct.scheduler_registry import default_scheduler_templates
from pct.sentenzeweb_nightly import run_nightly, tls_bundle


def test_schedule_is_configured_only_with_public_storage(monkeypatch):
    monkeypatch.delenv("IUSENTRA_SENTENZEWEB_DIRECTORY", raising=False)
    plain = next(row for row in default_scheduler_templates({}) if row.key == "cassazione_sentenzeweb_nightly")
    enabled = next(
        row
        for row in default_scheduler_templates({"IUSENTRA_SENTENZEWEB_DIRECTORY": "/public-corpus"})
        if row.key == plain.key
    )
    assert not plain.enabled and enabled.enabled
    assert enabled.hour == "23" and enabled.minute == "35"


def test_evening_time_tracks_summer_and_winter_clock():
    zone = ZoneInfo("Europe/Rome")
    trigger = CronTrigger(hour=23, minute=35, timezone=zone)
    summer = trigger.get_next_fire_time(None, datetime(2026, 10, 24, 12, tzinfo=zone))
    winter = trigger.get_next_fire_time(None, datetime(2026, 10, 26, 12, tzinfo=zone))
    assert summer.hour == winter.hour == 23 and summer.minute == winter.minute == 35
    assert summer.utcoffset() == timedelta(hours=2)
    assert winter.utcoffset() == timedelta(hours=1)


def test_tls_bundle_preserves_roots_and_fixed_intermediate(tmp_path):
    path = tls_bundle(tmp_path)
    assert path == tls_bundle(tmp_path)
    text = path.read_text()
    assert text.count("BEGIN CERTIFICATE") > 1


def test_unconfigured_job_does_not_start_download(monkeypatch):
    monkeypatch.delenv("IUSENTRA_SENTENZEWEB_DIRECTORY", raising=False)
    assert run_nightly({}) == {"ok": False, "status": "not_configured", "downloaded": False}


def test_public_ca_bundle_is_readable_across_app_worker_uids_without_write_access(tmp_path):
    from pct.sentenzeweb_nightly import tls_bundle
    bundle = tls_bundle(tmp_path)
    assert bundle.stat().st_mode & 0o777 == 0o644
    assert tls_bundle(tmp_path) == bundle
