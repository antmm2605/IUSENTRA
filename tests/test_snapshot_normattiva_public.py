import hashlib
import json
import sqlite3

import pytest

from deploy.hetzner.snapshot_normattiva_public import FILES, public_config, snapshot


def archive(tmp_path):
    db = tmp_path / "normattiva.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript("CREATE TABLE normative_documents(id INTEGER PRIMARY KEY, text_content TEXT);"
                           "CREATE TABLE normative_articles(id INTEGER PRIMARY KEY);"
                           "CREATE TABLE normative_chunks(id INTEGER PRIMARY KEY);")
        conn.execute("INSERT INTO normative_documents VALUES(1, 'Norma pubblica sintetica')")
    vectors = tmp_path / "vettori_normattiva"
    vectors.mkdir()
    for name in FILES:
        (vectors / name).write_bytes(b"{}" if name == "meta.json" else b"public-vector-fixture")
    return db, vectors


def test_snapshot_copia_solo_archivio_pubblico_e_conserva_hash_sorgenti(tmp_path):
    db, vectors = archive(tmp_path)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    result = snapshot(db, vectors, tmp_path / "copy", {"LEX_EMBED_MODEL": "fixture"})
    assert result["source_untouched"] is True
    assert result["index_text_coverage_certified"] is False
    assert result["counts"]["normative_documents"] == 1
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    for name in FILES:
        rel = "normativa/vettori_normattiva/" + name
        assert (tmp_path / "copy" / rel).read_bytes() == (vectors / name).read_bytes()
        assert hashlib.sha256((tmp_path / "copy" / rel).read_bytes()).hexdigest() == result["sha256"][rel]
    assert json.loads((tmp_path / "copy/manifest.json").read_text())["scope"] == "public_normattiva_only"


def test_snapshot_rifiuta_database_con_tabelle_di_studio(tmp_path):
    db, vectors = archive(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE fascicoli(id INTEGER PRIMARY KEY)")
    with pytest.raises(ValueError, match="Schema diverso"):
        snapshot(db, vectors, tmp_path / "copy", {})
    assert not (tmp_path / "copy").exists()


def test_snapshot_rifiuta_symlink_ai_file_vettoriali(tmp_path):
    db, vectors = archive(tmp_path)
    (vectors / "ids.i64").unlink()
    (vectors / "ids.i64").symlink_to(vectors / "impronte.u64")
    with pytest.raises(ValueError, match="percorso non ammesso"):
        snapshot(db, vectors, tmp_path / "copy", {})


def test_config_esclude_segreti_e_rimuove_credenziali_da_url():
    result = public_config(["LLAMACPP_API_KEY=SECRET", "DATABASE_PASSWORD=SECRET",
                            "LEX_EMBED_MODEL=fixture", "LEX_EMBED_URL=https://user:SECRET@localhost:11434/api?token=SECRET#SECRET"])
    assert result == {"LEX_EMBED_MODEL": "fixture", "LEX_EMBED_URL": "https://localhost:11434/api"}
    assert "SECRET" not in json.dumps(result)


def test_snapshot_rifiuta_db_cambiato_durante_la_copia(tmp_path, monkeypatch):
    from deploy.hetzner import snapshot_normattiva_public as module

    db, vectors = archive(tmp_path)
    original = module.shutil.copyfile
    changed = False
    def copy(src, dst):
        nonlocal changed
        result = original(src, dst)
        if not changed:
            with sqlite3.connect(db) as conn:
                conn.execute("INSERT INTO normative_documents VALUES(2, 'Aggiornamento concorrente')")
            changed = True
        return result
    monkeypatch.setattr(module.shutil, "copyfile", copy)
    with pytest.raises(ValueError, match="Database cambiato"):
        snapshot(db, vectors, tmp_path / "copy", {})
    assert not (tmp_path / "copy/manifest.json").exists()
