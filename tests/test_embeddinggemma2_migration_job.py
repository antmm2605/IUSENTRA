"""Guardrail del lotto nativo: modello operativo invariato, checkpoint e limiti."""
import json
import os
from types import SimpleNamespace
import subprocess
import pytest

from pct import embeddinggemma2_migration_job as job
from pct.scheduler_registry import default_scheduler_templates, SchedulerRegistryRepository


def test_preparation_snapshot_only_reads_checkpoint(tmp_path, monkeypatch):
    db = tmp_path / "normattiva.sqlite"
    db.write_bytes(b"Archivio da non aprire nella GET")
    folder = job.candidate_folder(db)
    folder.mkdir()
    config = {"NORMATTIVA_DB": db}
    monkeypatch.setattr(job.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Inferenza nella GET")))
    assert job.preparation_snapshot(config) == {"present": False}
    path = folder / "meta.json"
    path.write_text(json.dumps({"righe": 5, "prima_costruzione": {"totale_iniziale": 20, "completa": False}}))
    result = job.preparation_snapshot(config)
    assert result["stage"] == "building" and result["rows"] == 5 and result["total"] == 20
    path.write_text(json.dumps({"righe": 20, "prima_costruzione": {"totale_iniziale": 20, "completa": True}}))
    assert job.preparation_snapshot(config)["stage"] == "validation_required"
    path.write_text("{danneggiato")
    assert job.preparation_snapshot(config)["stage"] == "error"
    assert db.read_bytes() == b"Archivio da non aprire nella GET"


def test_disabled_job_does_not_read_source(monkeypatch):
    monkeypatch.delenv("IUSENTRA_EMBEDDING_INITIAL_BUILD", raising=False)
    monkeypatch.setattr(job.Path, "is_file", lambda _: (_ for _ in ()).throw(AssertionError("Lettura")))
    assert job.run_initial_batch()["status"] == "disabled"
    template = next(row for row in default_scheduler_templates() if row.key == job.JOB_ID)
    assert not template.enabled and template.built_in and template.interval_minutes == 2


def test_native_child_has_separate_profile_and_budget(tmp_path, monkeypatch):
    db = tmp_path / "normattiva.sqlite"
    db.touch()
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("IUSENTRA_EMBEDDING_RUNTIME", "sentence_transformers")
    folder = job.candidate_folder(db)
    folder.mkdir()
    (folder / "meta.json").write_text(json.dumps({"righe": 9}))

    def run(command, *, env, capture_output, text, timeout):
        assert timeout == 240 and capture_output and text
        assert env["IUSENTRA_EMBEDDING_PROVIDER"] == "embeddinggemma2_local"
        assert env["IUSENTRA_EMBEDDING_RUNTIME"] == "litert"
        assert "FileLock" in command[2] and "--prima-costruzione" in command
        assert command[command.index("--tempo-massimo-s") + 1] == "60"
        assert command[command.index("--out") + 1] == str(folder)
        assert folder.name != "vettori_normattiva"
        # La coda concorrente ha già aggiunto altre righe: questo figlio ne
        # ha prodotte soltanto due, come dichiara il suo esito strutturato.
        (folder / "meta.json").write_text(json.dumps({"righe": 15, "prima_costruzione": {"ultimo_id": 15}}))
        return SimpleNamespace(returncode=0, stdout=json.dumps({"nuovi": 2}))

    monkeypatch.setattr(job.subprocess, "run", run)
    result = job.run_initial_batch({"IUSENTRA_EMBEDDING_INITIAL_BUILD": True, "NORMATTIVA_DB": db})
    assert result["ok"] and result["added"] == 2 and result["checkpoint"]["ultimo_id"] == 15
    assert os.environ["IUSENTRA_EMBEDDING_PROVIDER"] == "ollama"
    assert os.environ["IUSENTRA_EMBEDDING_RUNTIME"] == "sentence_transformers"


def test_complete_checkpoint_does_not_restart_scan(tmp_path, monkeypatch):
    db = tmp_path / "normattiva.sqlite"
    db.touch()
    folder = job.candidate_folder(db)
    folder.mkdir()
    (folder / "meta.json").write_text(json.dumps({"righe": 12, "prima_costruzione": {"completa": True},
                                                "riconvalida_finale_richiesta": False}))
    monkeypatch.setattr(job.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Nuova scansione")))
    result = job.run_initial_batch({"IUSENTRA_EMBEDDING_INITIAL_BUILD": True, "NORMATTIVA_DB": db})
    assert result["status"] == "awaiting_validation" and result["rows"] == 12


def test_complete_construction_starts_bounded_native_validation(tmp_path, monkeypatch):
    db = tmp_path / "normattiva.sqlite"
    db.touch()
    folder = job.candidate_folder(db)
    folder.mkdir()
    path = folder / "meta.json"
    path.write_text(json.dumps({"righe": 12, "prima_costruzione": {"completa": True},
                               "riconvalida_finale_richiesta": True}))

    def run(command, **kwargs):
        assert "--riconvalida-finale" in command and "--prima-costruzione" not in command
        assert kwargs["timeout"] == 240
        path.write_text(json.dumps({"righe": 12, "prima_costruzione": {"completa": True},
                                   "riconvalida_finale_richiesta": False}))
        return SimpleNamespace(returncode=0, stdout=json.dumps({"nuovi": 0}))

    monkeypatch.setattr(job.subprocess, "run", run)
    result = job.run_initial_batch({"IUSENTRA_EMBEDDING_INITIAL_BUILD": True, "NORMATTIVA_DB": db})
    assert result["status"] == "validating"
    monkeypatch.setattr(job.subprocess, "run", lambda *a, **k: pytest.fail("Ripetizione dopo riconvalida"))
    assert job.run_initial_batch({"IUSENTRA_EMBEDDING_INITIAL_BUILD": True, "NORMATTIVA_DB": db})["status"] == "awaiting_validation"


def test_timeout_is_persistent_failed_result(tmp_path, monkeypatch):
    db = tmp_path / "normattiva.sqlite"
    db.touch()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(job.subprocess, "run", timeout)
    result = job.run_initial_batch({"IUSENTRA_EMBEDDING_INITIAL_BUILD": True, "NORMATTIVA_DB": db})
    assert not result["ok"] and result["status"] == "timeout"


def test_registry_governs_retry_recovery_and_stop(tmp_path, monkeypatch):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    repo.upsert_default_jobs()
    repo.save_job(job.JOB_ID, {"enabled": True, "interval_minutes": 7}, updated_by="test:explicit-preparation")
    outcomes = iter([
        {"ok": False, "status": "error", "note": "Servizio locale indisponibile"},
        {"ok": False, "status": "error", "note": "Servizio locale indisponibile"},
        {"ok": True, "status": "building"},
        {"ok": True, "status": "awaiting_validation"},
    ])
    monkeypatch.setattr(job, "run_initial_batch", lambda _: next(outcomes))
    first = job.run_registered_batch({}, repo)
    assert first["retry_minutes"] == 14 and first["base_interval_minutes"] == 7
    repo.record_scheduler_event(job.JOB_ID, status="failed", result=first)
    assert repo.get_job(job.JOB_ID)["interval_minutes"] == 14
    second = job.run_registered_batch({}, repo)
    assert second["retry_minutes"] == 28 and second["base_interval_minutes"] == 7
    repo.record_scheduler_event(job.JOB_ID, status="failed", result=second)
    assert job.run_registered_batch({}, repo)["ok"]
    assert repo.get_job(job.JOB_ID)["interval_minutes"] == 7
    assert job.run_registered_batch({}, repo)["status"] == "awaiting_validation"
    assert not repo.get_job(job.JOB_ID)["enabled"]
    assert job.run_registered_batch({}, repo)["status"] == "disabled"
