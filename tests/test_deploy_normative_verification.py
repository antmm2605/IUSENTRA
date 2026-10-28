"""La verifica server non puo dichiarare coperta una biblioteca parziale."""
import importlib.util
from pathlib import Path

import pytest
from pct.schede_fonti.verifica import EsitoNorma

spec = importlib.util.spec_from_file_location("verify_release_norms", Path(__file__).parents[1] / "deploy/hetzner/verifica_fonti_lex.py")
verification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)


def norm(state, article):
    return EsitoNorma(scheda="CIV_ORD_001", atto="codice_civile", articolo=article,
                     origine="norme", perche="fonte del modello", stato=state)


@pytest.mark.parametrize("missing", ["atto_assente", "articolo_assente", "articolo_ambiguo", "testo_non_integrale"])
def test_one_available_source_does_not_hide_unresolved_source(monkeypatch, tmp_path, missing):
    monkeypatch.setattr("pct.schede_fonti.verifica.verifica_schede",
                        lambda db: [norm("presente", "2043"), norm(missing, "1218")])
    with pytest.raises(ValueError, match="1 riferimenti"):
        verification.verifica_biblioteca_schede(tmp_path / "configured-library.sqlite")


def test_documented_repeal_is_not_a_missing_text_or_automatic_approval(monkeypatch, tmp_path):
    monkeypatch.setattr("pct.schede_fonti.verifica.verifica_schede",
                        lambda db: [norm("presente", "2043"), norm("abrogato", "old")])
    report = verification.verifica_biblioteca_schede(tmp_path / "configured-library.sqlite")
    assert report["stati"] == {"presente": 1, "abrogato": 1}
    assert report["scritture"] is False
    assert report["approvazioni_automatiche"] is False


@pytest.mark.parametrize("failure", ["disattivo", "mancano_vettori", "modello_irraggiungibile", "solo_lessicale"])
def test_deploy_blocca_semantica_assente_o_non_realmente_usata(tmp_path, failure):
    import sqlite3
    db = tmp_path / "codici_leggi.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE normative_chunks(id INTEGER PRIMARY KEY)")
        conn.executemany("INSERT INTO normative_chunks VALUES(?)", [(1,), (2,), (3,)])

    class FakeEngine:
        def __init__(self, path):
            assert path == db
        def stato(self):
            return {"semantica_attiva": failure != "disattivo", "righe_vettori": 2 if failure == "mancano_vettori" else 3,
                    "modello": "embeddinggemma:300m"}
        def riscalda(self, timeout):
            return failure != "modello_irraggiungibile"
        def cerca(self, query, *, limite, modalita):
            assert modalita == "semantica"
            return [{"ricerca": {"rango_semantico": 0 if failure == "solo_lessicale" else 1}}]

    with pytest.raises(ValueError):
        verification.verifica_biblioteca_semantica(db, FakeEngine)


def test_deploy_accetta_solo_candidati_effettivamente_semantici(tmp_path):
    import sqlite3
    db = tmp_path / "codici_leggi.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE normative_chunks(id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO normative_chunks VALUES(1)")

    class FakeEngine:
        def __init__(self, path): pass
        def stato(self): return {"semantica_attiva": True, "righe_vettori": 1, "modello": "embeddinggemma:300m"}
        def riscalda(self, timeout): return True
        def cerca(self, query, *, limite, modalita): return [{"ricerca": {"rango_semantico": 1}}]

    report = verification.verifica_biblioteca_semantica(db, FakeEngine)
    assert report == {"chunk": 1, "vettori": 1, "modello": "embeddinggemma:300m", "candidati_semantici": 1}
