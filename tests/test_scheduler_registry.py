from __future__ import annotations

from pathlib import Path

import pytest

from pct.scheduler_registry import (
    SchedulerRegistryRepository,
    apply_scheduler_registry,
    default_scheduler_templates,
    delegated_operational_agent_specs,
    dispatch_requested_manual_runs,
    legal_source_scheduler_templates,
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

    with pytest.raises(ValueError, match="Template non autorizzato"):
        repo.create_job_from_template("legal_source_scan__evil_shell")


def test_scheduler_registry_crea_agenti_fonte_legale_da_catalogo(tmp_path: Path):
    cfg = {"LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json")}
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")

    repo.upsert_default_jobs(cfg)

    templates = legal_source_scheduler_templates(cfg)
    assert any(tpl.key == "legal_source_scan__gazzetta_ufficiale" for tpl in templates)
    job = repo.get_job("legal_source_gazzetta_ufficiale")
    assert job is not None
    assert job["family"] == "Agenti fonte legale"
    assert job["trigger_kind"] == "manual"
    assert job["args"]["kind"] == "legal_update_source_scan"
    assert job["args"]["source_code"] == "gazzetta_ufficiale"
    ga_job = repo.get_job("legal_source_giustizia_amministrativa")
    assert ga_job is not None
    assert ga_job["enabled"] is False


def test_agente_fonte_in_osservazione_propone_alternativa_ufficiale(tmp_path: Path):
    class App:
        config = {"LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json")}

    result = run_delegated_agent_template(
        "legal_source_scan__giustizia_amministrativa",
        App(),
        {"source_code": "giustizia_amministrativa"},
    )

    assert result["ok"] is False
    assert "Da verificare" in result["self_check"]
    assert "OpenGA ufficiale" in result["supervisor_check"]
    assert result["details"][0]["status"] == "in_osservazione"


def test_delegated_agent_autoverifica_percorso_mancante(tmp_path: Path):
    class App:
        config = {"CLIENTI_DB": str(tmp_path / "clienti.json")}

    result = run_delegated_agent_template("agent_clienti_soggetti", App())

    assert result["ok"] is False
    assert "SOGGETTI_DB" in result["missing_keys"]
    assert "Da verificare" in result["self_check"]


def test_scheduler_registry_include_agenti_lex_notturni_e_perimetro_operativo():
    templates = {tpl.key for tpl in default_scheduler_templates({})}
    specs = {spec["agent_id"] for spec in delegated_operational_agent_specs({})}

    assert "lex_operational_agents_nightly" in templates
    assert {
        "cliente_soggetti",
        "fascicoli_documenti_timeline",
        "redazione_atti_editor",
        "giurisprudenza_cassazione",
        "ai_locale_rag_runtime",
        "integrazioni_native",
    }.issubset(specs)


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
    assert "punti da verificare" in finished["message"]
