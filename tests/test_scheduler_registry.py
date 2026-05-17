from __future__ import annotations

from pathlib import Path

import pytest

from pct.scheduler_registry import (
    SchedulerRegistryRepository,
    apply_scheduler_registry,
    dispatch_requested_manual_runs,
    run_delegated_agent_template,
)


def test_scheduler_registry_crea_agenti_da_template_autorizzato(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    repo.upsert_default_jobs({"BACKUP_ORA": "03:10"})

    created = repo.create_job_from_template(
        "agent_clienti_soggetti",
        name="Controllo clienti",
        hour="22",
        minute="45",
        created_by="superadmin",
    )

    assert created["job_id"].startswith("agent_clienti_soggetti_")
    assert created["name"] == "Controllo clienti"
    assert created["schedule_label"] == "Ogni giorno alle 22:45"
    assert created["enabled"] is True


def test_scheduler_registry_blocca_template_non_autorizzati(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")

    with pytest.raises(ValueError, match="Template non autorizzato"):
        repo.create_job_from_template("comando_libero_shell")


def test_delegated_agent_autoverifica_percorso_mancante(tmp_path: Path):
    class App:
        config = {"CLIENTI_DB": str(tmp_path / "clienti.json")}

    result = run_delegated_agent_template("agent_clienti_soggetti", App())

    assert result["ok"] is False
    assert "SOGGETTI_DB" in result["missing_keys"]
    assert "Da completare" in result["self_check"]


def test_scheduler_registry_applica_agenti_e_richieste_manuali(monkeypatch, tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    created = repo.create_job_from_template(
        "agent_clienti_soggetti",
        name="Controllo clienti",
        trigger_kind="manual",
        created_by="superadmin",
    )
    request = repo.request_manual_run(created["job_id"], requested_by="superadmin")

    calls: list[dict] = []

    class Scheduler:
        def __init__(self) -> None:
            self.jobs: dict[str, object] = {}

        def get_job(self, job_id: str):
            return self.jobs.get(job_id)

        def add_job(self, func, **kwargs):
            calls.append(kwargs)
            self.jobs[str(kwargs["id"])] = func

        def remove_job(self, job_id: str):
            self.jobs.pop(job_id, None)

        def pause_job(self, job_id: str):
            self.jobs[f"paused:{job_id}"] = True

        def resume_job(self, job_id: str):
            self.jobs[f"resumed:{job_id}"] = True

        def reschedule_job(self, job_id: str, trigger):
            self.jobs[f"rescheduled:{job_id}"] = trigger

    class App:
        config = {
            "CLIENTI_DB": str(tmp_path / "clienti.json"),
            "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
            "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        }

        def app_context(self):
            class Ctx:
                def __enter__(self_inner):
                    return None

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return Ctx()

    scheduler = Scheduler()
    apply_scheduler_registry(scheduler, App(), repo)
    dispatch_requested_manual_runs(scheduler, App(), repo)

    assert any(str(call["id"]).startswith("manual_") for call in calls)
    recent = repo.list_recent_runs(limit=1)[0]
    assert recent["run_id"] == request["run_id"]
    assert recent["status"] == "running"

    manual_job_id = next(str(call["id"]) for call in calls if str(call["id"]).startswith("manual_"))
    scheduler.jobs[manual_job_id]()
    finished = repo.list_recent_runs(limit=1)[0]
    assert finished["run_id"] == request["run_id"]
    assert finished["status"] == "failed"
    assert "archivi presenti" in finished["message"]
