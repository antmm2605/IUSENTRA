"""«Cerca norme e sentenze»: aprire la pagina non riscrive cataloghi e schemi a ogni richiesta.

Collaudo 21/11/2026: la pagina iniziale impiegava fino a 56 s; ogni apertura riscriveva i
cataloghi della ricerca legale, lo schema e le fonti predefinite (commit SQLite a vuoto).
"""
import time

from pct import legal_intelligence as li
from pct.legal_update_job_queue import LegalUpdateJobQueue
from pct.normative_tables import GestioneTabelleNormative
from pct.schema_preparato import gia_preparato


def test_cataloghi_riscritti_solo_se_cambiano(tmp_path, monkeypatch):
    chiamate = []
    originale = li.GestioneTelematicoRepository.synchronize_runtime

    def conta(self, payload):
        chiamate.append(1)
        return originale(self, payload)

    monkeypatch.setattr(li.GestioneTelematicoRepository, "synchronize_runtime", conta)
    db = tmp_path / "intelligence" / "legal_intelligence.json"
    db.parent.mkdir()
    li.GestioneLegalIntelligence(db_path=str(db))
    li.GestioneLegalIntelligence(db_path=str(db))
    assert len(chiamate) == 1
    for json_path in tmp_path.rglob("*telematico*.json"):
        json_path.unlink()  # un'esportazione sparita si rigenera
    li.GestioneLegalIntelligence(db_path=str(db))
    assert len(chiamate) == 2


def test_schema_della_coda_preparato_una_volta(tmp_path, monkeypatch):
    percorso = tmp_path / "coda.sqlite"
    LegalUpdateJobQueue(percorso)
    assert gia_preparato(percorso, "legal_update_jobs")
    monkeypatch.setattr(LegalUpdateJobQueue, "_crea_schema", lambda self: (_ for _ in ()).throw(AssertionError("schema rifatto")))
    LegalUpdateJobQueue(percorso)
    percorso.unlink()
    assert not gia_preparato(percorso, "legal_update_jobs")


def test_tabelle_normative_lette_senza_ricalcolare_le_definizioni(tmp_path):
    gestione = GestioneTabelleNormative(str(tmp_path / "tabelle.json"))
    tabelle = list(gestione._data.get("tables", {}))[:30]
    inizio = time.monotonic()
    for tabella in tabelle:
        gestione.get_table(tabella)
    assert time.monotonic() - inizio < 1.0
    prima = gestione.get_table(tabelle[0])
    prima["defaults"]["modificato"] = True
    assert "modificato" not in gestione.get_table(tabelle[0])["defaults"]
