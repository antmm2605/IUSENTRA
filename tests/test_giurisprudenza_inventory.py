import hashlib
import sqlite3
from types import SimpleNamespace

from web.services.giurisprudenza_inventory import attach_corpus_counts, corpus_inventory


def test_counts_are_read_only_and_scoped_to_current_database(tmp_path):
    path = tmp_path / "corpus.db"
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE fonti_giurisprudenza(id INTEGER, codice TEXT);"
                         "CREATE TABLE sentenze(fonte_id INTEGER, testo_integrale_presente INTEGER);"
                         "INSERT INTO fonti_giurisprudenza VALUES(1,'corte_costituzionale');"
                         "INSERT INTO sentenze VALUES(1,1),(1,0);")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    manager = SimpleNamespace(corpus_db_path=path)
    rows = attach_corpus_counts([{"id": "corte_costituzionale", "count": 0},
                                {"id": "cassazione", "count": 3}], manager)
    assert rows[0]["corpusCount"] == 2
    assert rows[0]["corpusFullTextCount"] == 1
    assert rows[0]["count"] == 0
    assert rows[1]["corpusCount"] == 0
    assert rows[1]["count"] == 3
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    other = tmp_path / "other.db"
    assert corpus_inventory(SimpleNamespace(corpus_db_path=other)) is None
    assert not other.exists()


def test_unavailable_or_invalid_database_is_unknown_not_zero(tmp_path):
    assert corpus_inventory(object()) is None
    invalid = tmp_path / "invalid.db"
    invalid.write_text("not a database")
    rows = attach_corpus_counts([{"id": "cassazione"}],
                               SimpleNamespace(corpus_db_path=invalid))
    assert rows[0]["corpusCount"] is None
    assert rows[0]["corpusFullTextCount"] is None
