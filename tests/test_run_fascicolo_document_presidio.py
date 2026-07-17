from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts import run_fascicolo_document_presidio as presidio


def test_presidio_checkpoint_is_written_after_each_cycle(monkeypatch, tmp_path: Path):
    checkpoint = tmp_path / "presidio.json"

    class FakeTenantManager:
        def __init__(self, _registry: str):
            pass

        def lista(self):
            return [SimpleNamespace(slug="studio-test")]

        def percorsi_dati(self, _tenant: str, **_kwargs):
            return {"FASCICOLI_DB": str(tmp_path / "fascicoli.sqlite")}

    class FakeRepository:
        calls = 0

        def recover_missing_hearings_from_fascicolo_documents(self, **kwargs):
            self.calls += 1
            kwargs["progress_callback"](
                {
                    "phase": "document_indexing",
                    "fascicolo_id": "FASC-1",
                    "documents": [{"document_id": "DOC-1", "filename": "Decreto.pdf", "sha256": "abc"}],
                }
            )
            active_checkpoint = json.loads(checkpoint.read_text(encoding="utf-8"))
            assert active_checkpoint["current"]["cycle"] == self.calls
            assert active_checkpoint["current"]["documents"][0]["filename"] == "Decreto.pdf"
            if self.calls == 1:
                return {
                    "processed_new_documents": 1,
                    "indexed_documents": 1,
                    "pending_new_or_changed_documents": 1,
                    "items": [
                        {
                            "status": "not_scheduled",
                            "fascicolo_id": "FASC-1",
                            "document": "Decreto.pdf",
                            "due_date": "2026-09-10",
                            "kind": "udienza",
                            "deadline": {"ok": False, "message": "Dato da verificare"},
                        }
                    ],
                }
            first_checkpoint = json.loads(checkpoint.read_text(encoding="utf-8"))
            assert first_checkpoint["completed"] is False
            assert first_checkpoint["totals"]["processed_new_documents"] == 1
            assert first_checkpoint["cycles"][0]["outcomes"][0]["deadline"]["message"] == "Dato da verificare"
            return {"processed_new_documents": 0}

    fake_repository = FakeRepository()
    monkeypatch.setattr(presidio, "GestioneTenant", FakeTenantManager)
    monkeypatch.setattr(presidio, "repository_from_paths", lambda *_args, **_kwargs: fake_repository)

    result = presidio.run_cycles(
        registry=tmp_path / "tenants.json",
        tenant="studio-test",
        limit=10,
        max_cycles=3,
        until_idle=True,
        pause_seconds=0,
        checkpoint_path=checkpoint,
    )

    assert result["ok"] is True
    assert result["completed"] is True
    assert result["idle"] is True
    assert result["totals"]["cycles"] == 2
    persisted_checkpoint = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert persisted_checkpoint["completed"] is True
    assert persisted_checkpoint["ok"] is True
    assert persisted_checkpoint["cycles"][-1]["processed_new_documents"] == 0


def test_atomic_json_writer_replaces_checkpoint_without_temporary_residue(tmp_path: Path):
    output = tmp_path / "presidio.json"
    presidio._write_json_atomic(output, {"ok": True, "testo": "udienza fissata"})

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "ok": True,
        "testo": "udienza fissata",
    }
    assert not output.with_name("presidio.json.tmp").exists()


def test_presidio_non_dichiara_idle_se_restano_fascicoli_incompleti(monkeypatch, tmp_path: Path):
    class FakeTenantManager:
        def __init__(self, _registry: str):
            pass

        def lista(self):
            return [SimpleNamespace(slug="studio-test")]

        def percorsi_dati(self, _tenant: str, **_kwargs):
            return {"FASCICOLI_DB": str(tmp_path / "fascicoli.sqlite")}

    class FakeRepository:
        calls = 0

        def recover_missing_hearings_from_fascicolo_documents(self, **_kwargs):
            self.calls += 1
            return {
                "processed_new_documents": 0,
                "pending_fascicoli": 1 if self.calls == 1 else 0,
                "pending_new_or_changed_documents": 0,
            }

    fake_repository = FakeRepository()
    monkeypatch.setattr(presidio, "GestioneTenant", FakeTenantManager)
    monkeypatch.setattr(presidio, "repository_from_paths", lambda *_args, **_kwargs: fake_repository)

    result = presidio.run_cycles(
        registry=tmp_path / "tenants.json",
        tenant="studio-test",
        limit=10,
        max_cycles=3,
        until_idle=True,
        pause_seconds=0,
    )

    assert result["ok"] is True
    assert result["idle"] is True
    assert result["totals"]["cycles"] == 2
