"""Persistenza privata e invarianti atomiche delle decisioni dello studio."""
import pytest

from pct.storage import StudioDB
from pct.schede_fonti.decisioni import DecisioniStudio


def test_lettura_non_crea_tabella_e_scrittura_non_attraversa_studi(tmp_path):
    a = StudioDB(tmp_path / "a.sqlite")
    b = StudioDB(tmp_path / "b.sqlite")
    ra, rb = DecisioniStudio(a), DecisioniStudio(b)
    assert ra.leggi("proposta") == {}
    assert not a.conn.execute("SELECT name FROM sqlite_master WHERE name='schede_fonti_decisioni'").fetchone()
    ra.registra("proposta", [("p", "sha", {"esito": "approvata", "nota": "privata"})], "avvocato A")
    assert len(ra.leggi("proposta")) == 1
    assert a.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0] > 0
    assert rb.leggi("proposta") == {}


def test_conflitto_annulla_intero_lotto_e_non_sovrascrive(tmp_path):
    repo = DecisioniStudio(StudioDB(tmp_path / "studio.sqlite"))
    repo.registra("proposta", [("p", "sha", {"esito": "approvata"})], "primo")
    revisione = repo.db.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0]
    with pytest.raises(ValueError, match="già stata decisa"):
        repo.registra("proposta", [("nuova", "sha", {"esito": "approvata"}), ("p", "sha", {"esito": "respinta"})], "secondo")
    assert repo.db.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0] == revisione
    records = list(repo.leggi("proposta").values())
    assert len(records) == 1 and records[0]["attore"] == "primo" and records[0]["esito"] == "approvata"
    repo.registra("proposta", [("p", "sha", {"esito": "approvata"})], "secondo")
    assert list(repo.leggi("proposta").values())[0]["attore"] == "primo"
    assert repo.db.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0] == revisione


def test_attore_obbligatorio_e_testo_approvato_conservato(tmp_path):
    repo = DecisioniStudio(StudioDB(tmp_path / "studio.sqlite"))
    with pytest.raises(ValueError):
        repo.registra("norma", [("n", "sha", {"testo": "fonte"})], "")
    repo.registra("norma", [("n", "sha", {"testo": "fonte", "url": "https://www.normattiva.it"})], "avvocato")
    record = list(repo.leggi("norma").values())[0]
    assert record["testo"] == "fonte" and record["impronta"] == "sha" and record["creato_il"]
