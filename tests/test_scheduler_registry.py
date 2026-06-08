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
    assert job["enabled"] is True
    cassazione_step1 = repo.get_job("legal_source_cassazione_ultime_sent_ord_questioni")
    assert cassazione_step1 is not None
    assert cassazione_step1["enabled"] is True
    anac_job = repo.get_job("legal_source_anac_documenti")
    assert anac_job is not None
    assert anac_job["enabled"] is True
    ga_job = repo.get_job("legal_source_giustizia_amministrativa")
    assert ga_job is not None
    assert ga_job["enabled"] is False


def test_scheduler_registry_non_accoda_pianificazioni_disattivate(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    repo.upsert_default_jobs({})
    repo.save_job("legal_updates_batch", {"enabled": False}, updated_by="system")

    request = repo.request_manual_run("legal_updates_batch", requested_by="superadmin")

    assert request["status"] == "completed"
    assert "disattivata" in request["message"]
    assert repo.list_requested_runs(limit=5) == []
    recent = repo.list_recent_runs(limit=1)[0]
    assert recent["run_id"] == request["run_id"]
    assert recent["status"] == "completed"
    assert recent["message"] == "Pianificazione disattivata: esecuzione non avviata."


def test_scheduler_registry_non_accoda_manutenzioni_pesanti_in_parallelo(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    repo.upsert_default_jobs({})

    first = repo.request_manual_run("utf8_integrity_nightly", requested_by="superadmin")
    second = repo.request_manual_run("operational_backup_nightly", requested_by="superadmin")

    requested = repo.list_requested_runs(limit=10)
    recent = repo.list_recent_runs(limit=2)

    assert first["status"] == "requested"
    assert second["status"] == "completed"
    assert "Manutenzione pesante" in second["message"]
    assert [run["job_id"] for run in requested] == ["utf8_integrity_nightly"]
    assert recent[0]["job_id"] == "operational_backup_nightly"
    assert recent[0]["status"] == "completed"
    assert recent[0]["result"]["status"] == "manutenzione_esclusiva_rinviata"


def test_scheduler_registry_chiude_manuale_running_da_worker_precedente(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    repo.upsert_default_jobs({})

    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO scheduled_job_runs (
                run_id, job_id, template_key, origin, status, scheduled_at,
                started_at, finished_at, duration_ms, message, result_json,
                error_message, requested_by, created_at
            )
            VALUES ('old-run', 'legal_source_corte_conti', 'legal_source_scan__corte_conti',
                'manuale', 'running', '2026-06-08T10:18:37Z',
                '2026-06-08T10:19:04Z', '', 0, 'Esecuzione in corso.',
                '{}', '', 'codex', '2026-06-08T10:18:37Z')
            """
        )

    result = repo.cancel_manual_runs_started_before(
        "2026-06-08T10:30:00Z",
        reason="Esecuzione interrotta dal riavvio del worker; rilanciare dalla console.",
    )
    recent = repo.list_recent_runs(limit=1)[0]

    assert result == {"cancelled": 1}
    assert recent["run_id"] == "old-run"
    assert recent["status"] == "cancelled"
    assert "riavvio del worker" in recent["message"]


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


def test_agente_fonte_fuori_step_progressivo_completa_presidio_rinviato(tmp_path: Path):
    class App:
        config = {"LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json")}

    result = run_delegated_agent_template(
        "legal_source_scan__inps_sentenze",
        App(),
        {"source_code": "inps_sentenze"},
    )

    assert result["ok"] is True
    assert "presidio rinviato" in result["summary"]
    assert "fase 9 progressiva" in result["summary"]
    assert result["details"][0]["status"] == "fuori_step_progressivo"
    assert "osservazione" in result["details"][0]["reason"]


def test_agente_fonte_processata_senza_pubblicazione_non_diventa_failure(monkeypatch, tmp_path: Path):
    class App:
        config = {"LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json")}

    def fake_batch(*args, **kwargs):
        return {
            "ok": False,
            "reports": [
                {
                    "ok": False,
                    "payload": {
                        "report": {
                            "reports": [
                                {
                                    "documents_found": 10,
                                    "processed": 10,
                                    "skipped_unchanged": 0,
                                }
                            ]
                        }
                    },
                    "timeout": False,
                }
            ],
            "timeouts": 0,
            "autopublished": {"count": 0, "reports": []},
        }

    monkeypatch.setattr("pct.legal_update_batch_runner.run_legal_update_batch_with_timeouts", fake_batch)

    result = run_delegated_agent_template(
        "legal_source_scan__corte_conti",
        App(),
        {"source_code": "corte_conti"},
    )

    assert result["ok"] is True
    assert "10 documenti trovati" in result["summary"]
    assert result["details"][0]["errors"] == []


def test_delegated_agent_autoverifica_percorso_mancante(tmp_path: Path):
    class App:
        config = {"CLIENTI_DB": str(tmp_path / "clienti.json")}

    result = run_delegated_agent_template("agent_clienti_soggetti", App())

    assert result["ok"] is False
    assert "SOGGETTI_DB" in result["missing_keys"]
    assert "Da verificare" in result["self_check"]


def test_scheduler_registry_include_agenti_lex_notturni_e_perimetro_operativo():
    templates = {tpl.key: tpl for tpl in default_scheduler_templates({})}
    specs = {spec["agent_id"] for spec in delegated_operational_agent_specs({})}

    assert "lex_operational_agents_nightly" in templates
    assert "lex_dataset_nightly" in templates
    assert templates["lex_dataset_nightly"].family == "Lex AI"
    assert templates["lex_dataset_nightly"].hour == "1"
    assert templates["lex_dataset_nightly"].minute == "45"
    assert "senza avviare addestramento automatico" in templates["lex_dataset_nightly"].description
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
    assert recent["status"] == "requested"

    manual_job_id = next(str(call["id"]) for call in calls if str(call["id"]).startswith("manual_"))
    scheduler.jobs[manual_job_id]()
    finished = repo.list_recent_runs(limit=1)[0]
    assert finished["run_id"] == request["run_id"]
    assert finished["status"] == "failed"
    assert "punti da verificare" in finished["message"]
