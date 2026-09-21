from pathlib import Path

import json
from unittest.mock import patch

import pytest

from scripts.backfill_archivio_batches import resume_managed_backfills, run_batches


def test_backfill_si_ferma_e_riprende_dal_checkpoint_senza_ripetere_i_casi(tmp_path: Path):
    checkpoint = tmp_path / "checkpoint.json"
    casi = [f"studio:F{i:02d}" for i in range(1, 13)]
    prima: list[str] = []

    def fallisce_al_sesto(case: str):
        prima.append(case)
        if case.endswith("F06"):
            raise RuntimeError("errore controllato")
        return {"ok": True, "fascicolo_id": case.split(":", 1)[1]}

    with pytest.raises(RuntimeError, match="errore controllato"):
        run_batches(casi, checkpoint_path=checkpoint, process_case=fallisce_al_sesto, readiness=lambda: None)

    seconda: list[str] = []
    risultato = run_batches(
        casi,
        checkpoint_path=checkpoint,
        process_case=lambda case: seconda.append(case) or {"ok": True},
        readiness=lambda: None,
    )

    assert prima == casi[:6]
    assert seconda == casi[5:]
    assert risultato["status"] == "complete"
    assert risultato["batch_size"] == 10
    assert risultato["completed"] == sorted(casi)


def test_backfill_quarantena_un_caso_permanente_e_prosegue(tmp_path: Path):
    checkpoint = tmp_path / "checkpoint.json"
    casi = ["studio:F01", "studio:F02", "studio:F03"]
    visti: list[str] = []

    def processa(case: str):
        visti.append(case)
        if case.endswith("F02"):
            return {"ok": False, "status": "quarantined", "reason": "formato non supportato"}
        return {"ok": True, "status": "ready"}

    risultato = run_batches(
        casi, checkpoint_path=checkpoint, process_case=processa, readiness=lambda: None
    )
    seconda: list[str] = []
    ripresa = run_batches(
        casi, checkpoint_path=checkpoint,
        process_case=lambda case: seconda.append(case) or {"ok": True},
        readiness=lambda: None,
    )

    assert visti == casi
    assert risultato["status"] == "complete_with_quarantine"
    assert risultato["quarantined"] == ["studio:F02"]
    assert risultato["completed"] == ["studio:F01", "studio:F03"]
    assert seconda == []
    assert ripresa["status"] == "complete_with_quarantine"


def test_scheduler_riprende_un_solo_caso_da_checkpoint_dopo_riavvio(tmp_path: Path):
    checkpoint = tmp_path / "tenants" / "studio-a" / "intelligence" / "backfill-archivio-batches.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text(json.dumps({"status": "stopped", "cases": ["studio-a:F01"]}), encoding="utf-8")
    with patch("scripts.backfill_archivio_batches.run_operational", return_value={"status": "pending", "last_case": "studio-a:F01"}) as run:
        report = resume_managed_backfills(object(), data_root=tmp_path)
    assert report["managed"] == 1
    assert run.call_args.kwargs["selected_tenant"] == "studio-a"
    assert run.call_args.kwargs["max_cases"] == 1
    assert run.call_args.kwargs["checkpoint_path"] == checkpoint
