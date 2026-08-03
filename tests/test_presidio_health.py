"""Presidi: il silenzio non deve piu' passare per lavoro svolto.

Copre le tre correzioni introdotte dopo il fermo dei presidi PEC, relata e
fascicoli: esito fallito quando non c'e' nulla su cui lavorare, cursore di
acquisizione non avvelenabile, battito verificabile dei job.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from flask import Flask

from pct.scheduler import start_scheduler
from pct.scheduler_health import (
    PRESIDIO_JOBS,
    format_heartbeat_lines,
    mark_worker_started,
    presidio_heartbeat,
    worker_startup_grace_active,
)


class _RegistroFinto:
    def __init__(self, runs: dict[str, dict[str, object]] | None = None, *, esplode: bool = False) -> None:
        self._runs = runs or {}
        self._esplode = esplode

    def latest_runs_by_job(self) -> dict[str, dict[str, object]]:
        if self._esplode:
            raise RuntimeError("registro corrotto")
        return self._runs


def _runs_tutti_ok(now: datetime) -> dict[str, dict[str, object]]:
    return {
        job_id: {"status": "completed", "finished_at": (now - timedelta(minutes=2)).isoformat()}
        for job_id, _label, _tolleranza in PRESIDIO_JOBS
    }


# ── Battito dei presidi ────────────────────────────────────────────────────


def test_battito_verde_quando_tutti_i_presidi_hanno_girato():
    now = datetime.now(timezone.utc)

    report = presidio_heartbeat(_RegistroFinto(_runs_tutti_ok(now)), now=now)

    assert report["ok"] is True
    assert report["degraded"] == 0
    assert report["checked"] == len(PRESIDIO_JOBS)
    # Ogni riga mostrata deve dichiarare da dove viene.
    assert all(voce["source"] for voce in report["presidi"])
    assert report["source"]


def test_battito_segnala_il_presidio_fermo_da_troppo_tempo():
    now = datetime.now(timezone.utc)
    runs = _runs_tutti_ok(now)
    runs["pec_audit_pipeline_workers"] = {
        "status": "completed",
        "finished_at": (now - timedelta(hours=3)).isoformat(),
    }

    report = presidio_heartbeat(_RegistroFinto(runs), now=now)

    assert report["ok"] is False
    assert report["degraded"] == 1
    # Fermo per anzianita', non per errore: non e' un guasto certo.
    assert report["hard_failures"] == 0
    voce = next(v for v in report["presidi"] if v["job"] == "pec_audit_pipeline_workers")
    assert "minuti fa" in voce["problem"]


def test_battito_distingue_il_job_fallito_dal_job_mai_eseguito():
    now = datetime.now(timezone.utc)
    runs = _runs_tutti_ok(now)
    runs["legal_notification_relata_presidio"] = {
        "status": "failed",
        "finished_at": (now - timedelta(minutes=1)).isoformat(),
        "error_message": "archivio fascicoli non raggiungibile",
    }

    fallito = presidio_heartbeat(_RegistroFinto(runs), now=now)
    mai_eseguiti = presidio_heartbeat(_RegistroFinto({}), now=now)

    assert fallito["hard_failures"] == 1
    assert mai_eseguiti["hard_failures"] == 0
    assert mai_eseguiti["degraded"] == len(PRESIDIO_JOBS)
    assert "mai eseguito" in mai_eseguiti["presidi"][0]["problem"]


def test_battito_dichiara_il_registro_illeggibile():
    report = presidio_heartbeat(_RegistroFinto(esplode=True))

    assert report["ok"] is False
    assert "registro pianificazioni" in report["error"]
    assert format_heartbeat_lines(report)[0].startswith("presidi:")


def test_finestra_di_avvio_del_worker(tmp_path, monkeypatch):
    import pct.scheduler_health as health

    marcatore = tmp_path / "start"
    monkeypatch.setattr(health, "WORKER_START_MARKER", marcatore)

    assert health.worker_startup_grace_active() is False
    mark_worker_started()
    assert health.worker_startup_grace_active() is True
    assert health.worker_startup_grace_active(datetime.now(timezone.utc) + timedelta(hours=2)) is False


def test_il_percorso_del_registro_non_diverge_dal_repository(tmp_path, monkeypatch):
    """L'healthcheck risolve il registro da solo per non importare il progetto."""

    from pct.scheduler_health import registry_db_path
    from pct.scheduler_registry import _runtime_registry_db_path

    configurazioni = (
        {"SCHEDULER_REGISTRY_DB": str(tmp_path / "esplicito.sqlite")},
        {"LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json")},
        {},
    )
    monkeypatch.delenv("IUSENTRA_SCHEDULER_REGISTRY_DB", raising=False)
    monkeypatch.delenv("LEGAL_INTELLIGENCE_DB", raising=False)
    for cfg in configurazioni:
        assert registry_db_path(cfg) == _runtime_registry_db_path(cfg)


def test_lettore_leggero_e_repository_vedono_le_stesse_esecuzioni(tmp_path):
    """Il battito legge in sqlite puro: deve dare lo stesso esito del repository."""

    from pct.scheduler_health import _RegistroSoloLettura
    from pct.scheduler_registry import SchedulerRegistryRepository

    db_path = tmp_path / "scheduler_registry.sqlite"
    repo = SchedulerRegistryRepository(db_path)
    repo.init_db()
    repo.record_scheduler_event(
        "pec_audit_pipeline_workers",
        status="completed",
        message="Esecuzione completata dal worker.",
        result={"ok": True},
    )

    atteso = repo.latest_runs_by_job()
    letto = _RegistroSoloLettura(db_path).latest_runs_by_job()

    assert set(letto) == set(atteso)
    for job_id, riga in letto.items():
        assert riga["status"] == atteso[job_id]["status"]


# ── Cursore dell'acquisizione PEC ──────────────────────────────────────────


def test_chiave_di_ordinamento_normalizza_i_formati_di_data():
    from web.services.pec_pipeline_runtime import _normalizza_data_locale

    atteso = "2026-08-03T09:15:00"
    assert _normalizza_data_locale("2026-08-03T09:15:00") == atteso
    assert _normalizza_data_locale("2026-08-03 09:15") == atteso
    assert _normalizza_data_locale("03/08/2026 09:15") == atteso
    assert _normalizza_data_locale("Mon, 3 Aug 2026 09:15:00 +0200") == atteso


def test_una_data_futura_o_illeggibile_non_puo_bloccare_il_cursore():
    """Era il vettore del fermo: una PEC con data anomala finiva in testa."""

    from web.services.pec_pipeline_runtime import _SORT_KEY_MIN, local_email_sort_key

    reale = SimpleNamespace(timestamp="2026-08-01T10:00:00", id="a")
    futura = SimpleNamespace(timestamp="2030-01-01T00:00:00", id="b")
    illeggibile = SimpleNamespace(timestamp="non una data", id="c")

    assert local_email_sort_key(futura) == _SORT_KEY_MIN
    assert local_email_sort_key(illeggibile) == _SORT_KEY_MIN
    assert local_email_sort_key(futura) < local_email_sort_key(reale)


def test_impronta_archivio_cambia_con_il_contenuto(tmp_path):
    from web.services.pec_pipeline_runtime import _archive_fingerprint

    archivio = tmp_path / "casella.json"
    archivio.write_text("{}", encoding="utf-8")
    prima = _archive_fingerprint(archivio)
    archivio.write_text('{"a": 1}', encoding="utf-8")

    assert prima
    assert _archive_fingerprint(archivio) != prima
    assert _archive_fingerprint(tmp_path / "assente.json") == ""


# ── Presidi senza target ───────────────────────────────────────────────────


@pytest.fixture()
def _scheduler_multitenant_senza_studi(monkeypatch):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        MULTI_TENANT=True,
    )
    scheduler = start_scheduler(app)
    yield scheduler
    scheduler.shutdown(wait=False)
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_i_presidi_hanno_una_tolleranza_di_ritardo_utile(_scheduler_multitenant_senza_studi):
    """Con 1 secondo di default un worker occupato saltava il giro del presidio."""

    for job_id, _label, _tolleranza in PRESIDIO_JOBS:
        job = _scheduler_multitenant_senza_studi.get_job(job_id)
        assert job is not None, job_id
        assert job.misfire_grace_time is not None and job.misfire_grace_time >= 60, job_id
        assert job.max_instances == 1, job_id
        assert job.coalesce is True, job_id


@pytest.mark.parametrize(
    "job_id",
    [
        "mailbox_sync_runtime",
        "pec_audit_pipeline_workers",
        "agenda_scadenziario_notifications",
        "legal_notification_relata_presidio",
    ],
)
def test_presidio_senza_target_riporta_un_guasto(_scheduler_multitenant_senza_studi, job_id):
    """Senza studi su cui lavorare l'esito deve essere rosso, non verde a zero."""

    job = _scheduler_multitenant_senza_studi.get_job(job_id)
    assert job is not None

    esito = job.func()

    assert esito["ok"] is False
    assert esito["job"] == job_id
    assert esito["error"]
    assert esito.get("targets") == 0
    # La riga deve dire da dove arriva il giudizio.
    assert esito["source_of_truth"]
