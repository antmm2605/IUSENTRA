import sqlite3

import pytest

from pct.openga_identita import identita_catalogo


def test_identity_comes_from_current_resource_not_browser(tmp_path):
    path = tmp_path / "catalogo.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
          CREATE TABLE risorse(id TEXT, sha256 TEXT);
          CREATE TABLE attive(relazione TEXT, risorsa TEXT, sede TEXT, nome_sede TEXT,
                              tipo TEXT, numero TEXT, anno INTEGER, ricorso TEXT);
        """)
        conn.execute("INSERT INTO risorse VALUES (?,?)", ("resource", "a" * 64))
        conn.execute("INSERT INTO attive VALUES (?,?,?,?,?,?,?,?)",
                     ("rel", "resource", "020", "Torino", "Sentenza", "202300355", 2023, "201900721"))
    payload = {"relazione_id": "rel", "resource_id": "resource", "resource_sha256": "a" * 64,
               "url": "https://attacker.invalid", "numero": "999"}
    assert identita_catalogo(path, payload)["numero"] == "202300355"
    with pytest.raises(ValueError):
        identita_catalogo(path, {**payload, "resource_sha256": "b" * 64})
    with pytest.raises(ValueError):
        identita_catalogo(path, {**payload, "relazione_id": "' OR 1=1 --"})


def test_missing_catalogue_is_not_created(tmp_path):
    path = tmp_path / "absent.db"
    with pytest.raises(sqlite3.OperationalError):
        identita_catalogo(path, {"relazione_id": "r", "resource_id": "s", "resource_sha256": "a" * 64})
    assert not path.exists()
