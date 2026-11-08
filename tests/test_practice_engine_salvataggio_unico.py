"""Una sola scrittura per le modifiche del presidio di un fascicolo (misura del collaudo 08/11/2026).

Aprire il Presidio del fascicolo riscriveva sette volte tutte le tabelle del presidio di tutto lo studio: 40 dei 46
secondi della richiesta. Il contenuto salvato deve restare identico; cambia solo quante volte e quanto si scrive.
"""

from __future__ import annotations

from pathlib import Path

from pct.practice_engine import PracticeEngineRepository, get_profile
from pct.practice_engine.models import ValidationResult


def _repo(tmp_path: Path) -> PracticeEngineRepository:
    return PracticeEngineRepository(str(tmp_path / "fascicoli" / "practice_engine" / "practice_engine.json"))


def _conta_scritture(repository, monkeypatch) -> dict[str, int]:
    conteggio = {"tutto": 0, "fascicolo": 0}
    originale = repository._persist_all

    def tutto():
        conteggio["tutto"] += 1
        originale()

    import pct.practice_engine.salvataggio as salvataggio

    scrivi = salvataggio.scrivi_fascicolo

    def fascicolo(repo, fid):
        conteggio["fascicolo"] += 1
        scrivi(repo, fid)

    monkeypatch.setattr(repository, "_persist_all", tutto)
    monkeypatch.setattr(salvataggio, "scrivi_fascicolo", fascicolo)
    return conteggio


def _profilo():
    profilo = get_profile("PROC_LIC_IMP_001")
    assert profilo is not None
    return profilo


def test_piu_modifiche_dello_stesso_fascicolo_una_sola_scrittura_e_dati_identici(tmp_path, monkeypatch):
    repository = _repo(tmp_path)
    repository.apply_profile("ALTRO", _profilo(), actor="avv")
    repository.apply_profile("F1", _profilo(), actor="avv")
    conteggio = _conta_scritture(repository, monkeypatch)
    with repository.salvataggio_unico("F1"):
        repository.save_validation_results("F1", [ValidationResult(key="cliente_presente", status="OK", severity="INFO", message="ok")])
        repository.record_state("F1", "FASCICOLO_APERTO", actor="avv")
        repository.audit("F1", "REGIA_RECALCULATED", actor="avv", message="ricalcolo")
    assert conteggio == {"tutto": 0, "fascicolo": 1}
    riletto = _repo(tmp_path)
    assert {k: len(v) for k, v in riletto._data.items()} == {k: len(v) for k, v in repository._data.items()}
    assert riletto.get_profile_snapshot("ALTRO")["code"] == "PROC_LIC_IMP_001"  # l'altro fascicolo resta
    assert [r.key for r in riletto.list_validation_results("F1")] == ["cliente_presente"]


def test_se_cambiano_le_righe_di_altri_fascicoli_si_riscrive_tutto(tmp_path, monkeypatch):
    repository = _repo(tmp_path)
    repository.apply_profile("F1", _profilo(), actor="avv")
    conteggio = _conta_scritture(repository, monkeypatch)
    with repository.salvataggio_unico("F1"):
        repository.record_state("F2", "FASCICOLO_APERTO", actor="avv")
    assert conteggio["tutto"] == 1 and conteggio["fascicolo"] == 0
    assert _repo(tmp_path).studio_db.conn.execute(
        "SELECT COUNT(*) AS n FROM practice_state_history WHERE fascicolo_id = 'F2'").fetchone()["n"] == 1


def test_errore_dentro_il_blocco_non_scrive_e_letture_invariate_non_scrivono(tmp_path, monkeypatch):
    repository = _repo(tmp_path)
    repository.apply_profile("F1", _profilo(), actor="avv")
    conteggio = _conta_scritture(repository, monkeypatch)
    try:
        with repository.salvataggio_unico("F1"):
            repository.record_state("F1", "X", actor="avv")
            raise RuntimeError("interrotta")
    except RuntimeError:
        pass
    assert conteggio == {"tutto": 0, "fascicolo": 0}
    # slot e checklist già presenti e invariati: nessuna scrittura
    repository.ensure_slots("F1", _profilo())
    repository.ensure_checklist("F1", _profilo())
    assert conteggio == {"tutto": 0, "fascicolo": 0}
