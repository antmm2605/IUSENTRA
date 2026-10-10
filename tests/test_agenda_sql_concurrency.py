"""Concorrenza sul repository Agenda reale, senza dati dello studio."""
import os
from datetime import date
from types import MethodType, SimpleNamespace

import pytest
from pct.agenda import Agenda, TipoAppuntamento
from pct.agenda_sql_writer import AgendaConflict, COLUMNS
from pct.storage import StudioDB


@pytest.fixture
def repository(tmp_path):
    raw = None
    if os.environ.get("CTU_TEST_POSTGRES") == "1":
        import psycopg2
        from pct.storage_postgres import PostgresCompatConnection, PostgresStudioDB
        raw = psycopg2.connect(host=os.environ.get("CTU_TEST_PG_HOST", "audit-postgres"),
                              dbname=os.environ.get("AUDIT_POSTGRES_DB", "iusentra_audit"),
                              user=os.environ.get("AUDIT_POSTGRES_USER", "iusentra_audit"),
                              password=os.environ["AUDIT_POSTGRES_PASSWORD"])
        db = SimpleNamespace(raw_conn=raw)
        db.conn = PostgresCompatConnection(db)
        columns = [name + (" INTEGER" if name == "durata_minuti" else " TEXT") +
                   (" PRIMARY KEY" if name == "id" else "") for name in COLUMNS]
        db.conn.execute(f"CREATE TEMP TABLE appuntamenti ({','.join(columns)})")
        raw.commit()
        db.salva_tabella = MethodType(PostgresStudioDB.salva_tabella, db)
        db.fetchall_readonly = lambda sql: db.conn.execute(sql).fetchall()
    else:
        db = StudioDB.get(str(tmp_path / "studio.db"))
    path = str(tmp_path / "agenda.json")
    try:
        yield db, path, Agenda(path, studio_db=db)
    finally:
        if raw is not None:
            raw.close()


def add(agenda, title):
    return agenda.aggiungi(title, TipoAppuntamento.ALTRO, "2026-12-15T10:00:00", allow_overlap=True)


def test_day_availability_includes_only_selected_day(repository):
    _, _, agenda = repository
    selected = add(agenda, "Giorno selezionato")
    agenda.aggiungi("Giorno successivo", TipoAppuntamento.ALTRO,
                   "2026-12-16T10:00:00", allow_overlap=True)
    assert [app.id for app in agenda.cerca(da=date(2026, 12, 15), a=date(2026, 12, 15))] == [selected.id]


def test_stale_add_preserves_both_processes(repository):
    db, path, first = repository
    second = Agenda(path, studio_db=db)
    a = add(first, "Primo processo")
    b = add(second, "Secondo processo")
    fresh = Agenda(path, studio_db=db)
    assert fresh.get(a.id).titolo == "Primo processo"
    assert fresh.get(b.id).titolo == "Secondo processo"


def test_stale_edit_refuses_overwrite_and_restores_snapshot(repository):
    db, path, first = repository
    app = add(first, "Originale")
    second = Agenda(path, studio_db=db)
    first.modifica(app.id, titolo="Confermato dal primo")
    with pytest.raises(AgendaConflict):
        second.modifica(app.id, titolo="Snapshot superato")
    assert second.get(app.id).titolo == "Originale"
    assert Agenda(path, studio_db=db).get(app.id).titolo == "Confermato dal primo"


def test_stale_delete_refuses_newer_edit(repository):
    db, path, first = repository
    app = add(first, "Originale")
    second = Agenda(path, studio_db=db)
    first.modifica(app.id, note="Nota confermata")
    with pytest.raises(AgendaConflict):
        second.elimina(app.id)
    assert second.get(app.id) is not None
    assert Agenda(path, studio_db=db).get(app.id).note == "Nota confermata"


def test_delete_keeps_concurrent_addition(repository):
    db, path, first = repository
    app = add(first, "Da eliminare")
    second = Agenda(path, studio_db=db)
    other = add(second, "Da conservare")
    first.elimina(app.id)
    fresh = Agenda(path, studio_db=db)
    assert fresh.get(app.id) is None
    assert fresh.get(other.id) is not None


def test_sql_read_error_does_not_replace_archive_with_json(repository, monkeypatch):
    db, path, agenda = repository
    app = add(agenda, "Persistito")
    def fail(*args, **kwargs):
        raise RuntimeError("Errore SQL controllato")
    monkeypatch.setattr(db, "fetchall_readonly", fail)
    with pytest.raises(RuntimeError, match="Errore SQL controllato"):
        Agenda(path, studio_db=db)
    assert db.conn.execute("SELECT titolo FROM appuntamenti WHERE id=?", (app.id,)).fetchone()[0] == "Persistito"


def test_different_records_can_be_modified_from_stale_snapshot(repository):
    db, path, first = repository
    a, b = add(first, "Uno"), add(first, "Due")
    second = Agenda(path, studio_db=db)
    first.modifica(a.id, titolo="Uno aggiornato")
    second.modifica(b.id, titolo="Due aggiornato")
    fresh = Agenda(path, studio_db=db)
    assert fresh.get(a.id).titolo == "Uno aggiornato"
    assert fresh.get(b.id).titolo == "Due aggiornato"


def test_conflict_rolls_back_entire_batch(repository):
    db, path, first = repository
    a, b = add(first, "Uno"), add(first, "Due")
    second = Agenda(path, studio_db=db)
    first.modifica(b.id, note="Aggiornamento concorrente")
    second.get(a.id).titolo = "Non deve essere salvato"
    second.get(b.id).titolo = "Nemmeno questo"
    with pytest.raises(AgendaConflict):
        second._salva()
    fresh = Agenda(path, studio_db=db)
    assert fresh.get(a.id).titolo == "Uno"
    assert fresh.get(b.id).note == "Aggiornamento concorrente"


def test_browser_version_refuses_newer_record_in_fresh_request(repository):
    db, path, first = repository
    app = add(first, "Versione letta dal browser")
    expected = first.revision_token(app.id)
    Agenda(path, studio_db=db).modifica(app.id, titolo="Salvato da un altro utente")
    fresh_request = Agenda(path, studio_db=db)
    with pytest.raises(AgendaConflict):
        fresh_request.modifica(app.id, expected_version=expected, titolo="Bozza superata")
    assert Agenda(path, studio_db=db).get(app.id).titolo == "Salvato da un altro utente"


def test_browser_current_version_can_save(repository):
    db, path, first = repository
    app = add(first, "Versione originale")
    expected = first.revision_token(app.id)
    first.modifica(app.id, expected_version=expected, titolo="Salvataggio confermato")
    fresh = Agenda(path, studio_db=db)
    assert fresh.get(app.id).titolo == "Salvataggio confermato"
    assert fresh.revision_token(app.id) != expected
