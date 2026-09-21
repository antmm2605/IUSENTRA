from pathlib import Path

import pytest

from scripts.backfill_archivio_batches import run_batches


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
