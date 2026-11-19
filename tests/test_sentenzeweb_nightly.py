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


def test_lotto_con_testi_senza_riscontro_segnala_esito_parziale(tmp_path, monkeypatch):
    import json
    import sqlite3
    from types import SimpleNamespace

    with sqlite3.connect(tmp_path / "giurisprudenza_corpus.db") as db:
        db.executescript("""
            CREATE TABLE sentenzeweb_progress(id,seen,expected,status);
            INSERT INTO sentenzeweb_progress VALUES (1,0,0,'complete');
            CREATE TABLE sentenzeweb_recovery_queue(status);
            INSERT INTO sentenzeweb_recovery_queue VALUES ('pending'), ('needs_evidence');
        """)
    counters = {"processed": 2, "recovered": 1, "needs_evidence": 1, "already_available": 0}
    monkeypatch.setattr("pct.sentenzeweb_nightly.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(counters)))
    result = run_nightly({"IUSENTRA_SENTENZEWEB_DIRECTORY": str(tmp_path)})
    assert result["status"] == "parziale"
    assert result["recovery"] == counters and result["recovery_pending"] == 1
    assert not result["downloaded"]


def _corpus_minimo(tmp_path):
    import sqlite3

    with sqlite3.connect(tmp_path / "giurisprudenza_corpus.db") as db:
        db.executescript("""
            CREATE TABLE sentenzeweb_progress(id,seen,expected,status);
            INSERT INTO sentenzeweb_progress VALUES (1,0,0,'complete');
            CREATE TABLE sentenzeweb_recovery_queue(status);
            INSERT INTO sentenzeweb_recovery_queue VALUES ('pending');
        """)


def test_lotto_configurato_oltre_il_massimo_resta_nel_limite_del_recupero(tmp_path, monkeypatch):
    """Verifica del 18/11/2026: con 1500 il recupero rifiutava la richiesta e il giro falliva sempre."""
    import json
    from types import SimpleNamespace

    from pct.sentenzeweb_nightly import recuperi_per_giro
    from pct.sentenzeweb_recovery import MASSIMO_RECUPERI_PER_GIRO

    assert recuperi_per_giro({"IUSENTRA_SENTENZEWEB_RECUPERO_PER_GIRO": "1500"}) == MASSIMO_RECUPERI_PER_GIRO == 1000
    assert recuperi_per_giro({"IUSENTRA_SENTENZEWEB_RECUPERO_PER_GIRO": "0"}) == 1
    assert recuperi_per_giro({"IUSENTRA_SENTENZEWEB_RECUPERO_PER_GIRO": "x"}) == 25
    _corpus_minimo(tmp_path)
    comandi = []
    counters = {"processed": 0, "recovered": 0, "needs_evidence": 0, "already_available": 0}

    def esegui(command, **kwargs):
        comandi.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps(counters))

    monkeypatch.setattr("pct.sentenzeweb_nightly.subprocess.run", esegui)
    run_nightly({"IUSENTRA_SENTENZEWEB_DIRECTORY": str(tmp_path), "IUSENTRA_SENTENZEWEB_RECUPERO_PER_GIRO": "1500"})
    recupero = comandi[-1]
    assert recupero[recupero.index("--max-records") + 1] == "1000"


def test_recupero_oltre_il_tempo_resta_parziale_senza_far_fallire_il_giro(tmp_path, monkeypatch):
    import subprocess
    from types import SimpleNamespace

    _corpus_minimo(tmp_path)

    def esegui(command, **kwargs):
        if any(str(parte).endswith("sentenzeweb_recupera.py") for parte in command):
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("pct.sentenzeweb_nightly.subprocess.run", esegui)
    result = run_nightly({"IUSENTRA_SENTENZEWEB_DIRECTORY": str(tmp_path)})
    assert result["ok"] is True and result["status"] == "parziale"
    assert result["recovery_status"] == "timeout" and result["recovery_pending"] == 1


def test_la_lettura_delle_citazioni_procede_anche_se_sentenzeweb_fallisce(tmp_path, monkeypatch):
    from pct import giurisprudenza_alimentazione as alimentazione

    def guasto(config):
        raise RuntimeError("Public recovery failed; native queue and preserved originals retained")

    monkeypatch.setattr("pct.sentenzeweb_nightly.run_nightly", guasto)
    letti = []
    monkeypatch.setattr(alimentazione, "leggi_citazioni", lambda owner, scadenza=None: letti.append(owner) or {"lette": 0})
    studio = tmp_path / "studio.db"
    studio.write_bytes(b"")
    esito = alimentazione.esegui_giro({"IUSENTRA_ALIMENTAZIONE_GIURISPRUDENZA": "continua"}, archivi_studi=[str(studio)])
    assert esito["status"] == "parziale" and esito["sentenzeweb"]["ok"] is False
    assert "Public recovery failed" in esito["sentenzeweb"]["error"]
    assert letti, "la lettura delle citazioni degli studi deve proseguire"
