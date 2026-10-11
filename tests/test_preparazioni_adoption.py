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


def test_explicit_preservation_keeps_orphan_payload_and_blocks_all_effects(database):
    from datetime import date
    from uuid import uuid4
    from pct.udienze.repository import PreparazioniRepository, PreparazioneRejected
    from web.services.preparazione_udienza_commands import execute_command
    item = record()
    item["step1_note"] = "Nota storica da conservare"
    source, backup, root = source_for(database, json.dumps([item]))
    original = source.read_bytes()
    with prima_nota_source_lock(source):
        result = adopt_locked(database, source, tenant="studio", destination=backup,
                              writers_drained=True, data_root=root, preserve_missing_fascicoli=True)
    assert result["records"] == 1 and result["unresolved"] == 1
    repo = PreparazioniRepository(database, "studio", actor="avvocato")
    current = repo.get(item["id"])
    assert current["record"] == item and current["reference_issue"]
    assert (backup / "preparazioni-original.json").read_bytes() == original == source.read_bytes()
    for operation, intent in [("passo", {"passo": 1, "campi": {"step1_note": "Sovrascrivere"}}),
                              ("esito", {"esito": "rinvio"}), ("archivia", {}), ("elimina", {})]:
        command = str(uuid4())
        with pytest.raises(PreparazioneRejected) as first:
            execute_command(repo, item["id"], operation, intent, command_key=command,
                            expected_revision=0, today=date(2026, 10, 11))
        with pytest.raises(PreparazioneRejected) as repeated:
            execute_command(repo, item["id"], operation, intent, command_key=command,
                            expected_revision=0, today=date(2026, 10, 11))
        assert first.value.result == repeated.value.result
    assert repo.get(item["id"])["record"] == item and repo.get(item["id"])["revision"] == 0
    assert database.conn.execute("SELECT count(*) FROM appuntamenti").fetchone()[0] == 0
    assert database.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 0
    details = json.loads(database.conn.execute("SELECT dettagli FROM audit_log WHERE azione='udienza.adozione'").fetchone()[0])
    assert item["id"] in details["after"]["unresolved_references"]
    with pytest.raises(RuntimeError, match="non adottate"):
        PreparazioniRepository(database, "altro-studio", actor="avvocato").get(item["id"])

    from types import SimpleNamespace
    from web.services.preparazione_udienza_elenco import elenco
    from web.services.preparazione_udienza_sql_runtime import GestionePreparazioniSql
    empty = SimpleNamespace(tutti=lambda: [])
    listing = elenco(agenda=empty, fascicoli=empty,
                     preparazioni=GestionePreparazioniSql(repo), oggi=date(2026, 10, 11))
    assert listing["concluse"] == [] and listing["udienze"] == []
    assert listing["preservate"][0]["dati"] == item
    assert listing["riepilogo"]["preparate"] == 0


def test_preservation_does_not_accept_discordant_existing_identity(database):
    from pct.udienze.adoption import verify_references
    item = record()
    database.conn.execute("INSERT INTO fascicoli (id,dati_json) VALUES (?,?)", ("F1", '{"id":"ALTRO"}'))
    database.conn.commit()
    with pytest.raises(ValueError, match="discordante"):
        verify_references(database, [item], preserve_missing_fascicoli=True)


def test_missing_document_preserved_without_hiding_discordant_term(database):
    from pct.udienze.adoption import verify_references
    item = record()
    item["id_appuntamento"] = ""
    item["checklist_documenti"] = [{"id_documento": "DOC-STORICO", "label": "Originale storico"}]
    database.conn.execute("INSERT INTO fascicoli (id,dati_json,documenti_json) VALUES (?,?,?)", ("F1", '{"id":"F1"}', '[]'))
    database.conn.commit()
    with pytest.raises(ValueError, match="Documento"):
        verify_references(database, [item], preserve_missing_fascicoli=True)
    issues = verify_references(database, [item], preserve_missing_documents=True)
    assert "Documenti storici" in issues[item["id"]]
    source, backup, root = source_for(database, json.dumps([item]))
    with prima_nota_source_lock(source):
        adopt_locked(database, source, tenant="studio", destination=backup,
                     writers_drained=True, data_root=root, preserve_missing_documents=True)
    from pct.udienze.repository import PreparazioniRepository
    stored = PreparazioniRepository(database, "studio", actor="avvocato").get(item["id"])
    assert stored["record"]["checklist_documenti"][0]["id_documento"] == "DOC-STORICO"
    assert stored["reference_issue"] == issues[item["id"]]
    item["termini_assegnati"] = [{"id_scadenza": "TERMINE-ASSENTE"}]
    with pytest.raises(ValueError, match="Termine"):
        verify_references(database, [item], preserve_missing_documents=True)


@pytest.mark.parametrize("content", ["testo non JSON", "{}", '[{"id":"da-preservare"}]'])
def test_invalid_source_is_not_an_empty_archive(tmp_path, content):
    source = tmp_path / "sessioni.json"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_source(source)
    assert source.read_text(encoding="utf-8") == content
