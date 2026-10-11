"""Backup/fence controllati: nessuna migrazione dei dati reali nei test."""
import json
import sqlite3
from pathlib import Path

import pytest

from pct.prima_nota_transition import prima_nota_source_lock, read_transition, transition_path
from pct.udienze.adoption import adopt_locked, read_source
from tests.test_preparazioni_sql_repository import database as database, record


def source_for(database, content="[]"):
    root = Path(database.db_path).parent
    source = root / "sessioni.json"
    source.write_text(content, encoding="utf-8")
    return source, root / "backup-preparazioni", root


def adopt(database, source, backup, root, **kwargs):
    with prima_nota_source_lock(source):
        return adopt_locked(database, source, tenant="studio", destination=backup,
                            writers_drained=kwargs.get("writers_drained", True), data_root=root)


def test_empty_source_backup_and_adoption_resume(database):
    source, backup, root = source_for(database)
    first = adopt(database, source, backup, root)
    assert first["records"] == 0 and first["phase"] == "committed"
    assert read_transition(source)["source_sha256"] == first["source_sha256"]
    connection = sqlite3.connect(backup / "studio-preparazioni.db")
    try:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT count(*) FROM preparazioni_state").fetchone()[0] == 0
    finally:
        connection.close()
    assert adopt(database, source, backup, root) == first
    assert database.conn.execute("SELECT count(*) FROM audit_log WHERE azione='udienza.adozione'").fetchone()[0] == 1


def test_legacy_manager_open_before_adoption_cannot_write_after_fence(database):
    from pct.wizard_pro import GestioneWizardPro
    source, backup, root = source_for(database)
    manager = GestioneWizardPro(str(source))
    assert manager.lista() == []
    adopt(database, source, backup, root)
    original = source.read_bytes()
    with pytest.raises(RuntimeError, match="transizione SQL"):
        manager.salva(record())
    assert source.read_bytes() == original
    with pytest.raises(RuntimeError, match="transizione SQL"):
        manager.lista()


def test_no_writers_drain_no_backup_or_marker(database):
    source, backup, root = source_for(database)
    with pytest.raises(ValueError, match="Drain"):
        adopt(database, source, backup, root, writers_drained=False)
    assert not backup.exists() and not transition_path(source).exists()


def test_source_changes_during_backup_never_adopted(database, monkeypatch):
    from deploy.hetzner import backup_structured
    source, backup, root = source_for(database)
    original = backup_structured._backup_sqlite
    def changed(*args):
        result = original(*args)
        source.write_text(" [] ", encoding="utf-8")
        return result
    monkeypatch.setattr(backup_structured, "_backup_sqlite", changed)
    with pytest.raises(RuntimeError, match="Fonte cambiata"):
        adopt(database, source, backup, root)
    assert not transition_path(source).exists()
    assert database.conn.execute("SELECT count(*) FROM preparazioni_state").fetchone()[0] == 0


def test_broken_backup_cannot_be_used_for_resume(database):
    source, backup, root = source_for(database)
    adopt(database, source, backup, root)
    (backup / "studio-preparazioni.db").write_bytes(b"backup corrotto del solo test")
    with pytest.raises(RuntimeError, match="Backup SQL"):
        adopt(database, source, backup, root)
    assert read_transition(source)["phase"] == "committed"


def test_orphan_preparation_explicit_no_silent_drop(database):
    source, backup, root = source_for(database, json.dumps([record()]))
    with pytest.raises(ValueError, match="Fascicolo"):
        adopt(database, source, backup, root)
    assert not backup.exists() and not transition_path(source).exists()
    assert len(read_source(source)[0]) == 1


@pytest.mark.parametrize("content", ["testo non JSON", "{}", '[{"id":"da-preservare"}]'])
def test_invalid_source_is_not_an_empty_archive(tmp_path, content):
    source = tmp_path / "sessioni.json"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_source(source)
    assert source.read_text(encoding="utf-8") == content
