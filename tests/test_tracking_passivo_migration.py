"""Importazione storica controllata: backup, stati e assenza di sovrascritture."""
import json
import os
from pathlib import Path

import pytest

from pct.tracking_passivo_sql import SCHEMA, TrackingPassivoSQL
from pct.timesheet_sql_writer import TimesheetConflict
from tools.migrate_tracking_passivo_sql import migrate
pytest_plugins = ("tests.test_timesheet_sql_concurrency",)


@pytest.fixture
def migration_database(managers):
    db = managers[0]
    if getattr(db, "raw_conn", None) is not None:
        from psycopg2.extensions import make_dsn, parse_dsn
        db.backend_kind = "postgresql"
        parameters = parse_dsn(db.raw_conn.dsn)
        parameters['password'] = os.environ['AUDIT_POSTGRES_PASSWORD']
        db.dsn = make_dsn(**parameters)
        db.chiudi = lambda: None  # Il fixture proprietario chiude le connessioni.
        db.conn.execute("CREATE TABLE IF NOT EXISTS _meta (chiave TEXT PRIMARY KEY,valore TEXT)")
        for statement in SCHEMA.split(';'):
            if statement.strip():
                db.conn.execute(statement)
        db.conn.execute('CREATE TABLE audit_log (id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)')
        db.raw_conn.commit()
    return db


def historical(key='proposal', state='BOZZA'):
    return dict(id=key, chiave=f'user|case|{key}', stato=state, utente_id='user',
                fascicolo_id='case', inizio='2026-10-17T10:00:00', minuti=12,
                descrizione='Fonte originale', estensione={'provenienza': 'audit storico'})


def test_importa_tutti_gli_stati_e_conserva_originale_e_backup(tmp_path, migration_database):
    db = migration_database
    source = tmp_path / 'tracking_passivo.json'
    rows = {str(i): historical(str(i), state) for i, state in enumerate(['BOZZA', 'CONFERMATA', 'SCARTATA'])}
    from pct.timesheet import GestioneTimesheet
    db.conn.execute("INSERT INTO fascicoli (id) VALUES ('case')")
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    confirmed = GestioneTimesheet(str(tmp_path / 'entries.json'), studio_db=db).crea(
        descrizione='Fonte originale', minuti=12, id_fascicolo='case', id_utente='user', origine='tracking_passivo')
    rows['1']['voce_timesheet_id'] = confirmed.id
    original = json.dumps(rows, ensure_ascii=False).encode()
    source.write_bytes(original)
    try:
        report = migrate(db, source, tmp_path / 'backup')
        assert report['inserted'] == 3
        assert source.read_bytes() == original
        assert (tmp_path / 'backup' / 'tracking_passivo.original.json').read_bytes() == original
        assert Path(report['backup']).is_file()
        repo = TrackingPassivoSQL(db)
        for key, value in rows.items():
            assert repo.get(key) == value
        assert migrate(db, source, tmp_path / 'backup')['inserted'] == 0
    finally:
        db.chiudi()


def test_ripetizione_non_sovrascrive_decisioni_successive(tmp_path, migration_database):
    db = migration_database
    source = tmp_path / 'tracking_passivo.json'
    source.write_text(json.dumps({'proposal': historical()}))
    try:
        migrate(db, source, tmp_path / 'backup')
        repo = TrackingPassivoSQL(db)
        repo.transition('proposal', actor_id='user', reason='Decisione manuale')
        migrate(db, source, tmp_path / 'backup')
        assert repo.get('proposal')['stato'] == 'SCARTATA'
        assert repo.get('proposal')['motivo_scarto'] == 'Decisione manuale'
    finally:
        db.chiudi()


def test_fonti_discordanti_non_sovrascrivono_sql(tmp_path, migration_database):
    db = migration_database
    source = tmp_path / 'tracking_passivo.json'
    source.write_text(json.dumps({'proposal': historical()}))
    try:
        repo = TrackingPassivoSQL(db)
        repo.insert([dict(historical(), minuti=99)])
        with pytest.raises(TimesheetConflict, match='diversa'):
            migrate(db, source, tmp_path / 'backup')
        assert repo.get('proposal')['minuti'] == 99
        assert db.conn.execute("SELECT valore FROM _meta WHERE chiave='tracking_passivo_sql_source'").fetchone() is None
    finally:
        db.chiudi()


def test_cambiamento_durante_importazione_annulla_le_scritture(tmp_path, monkeypatch, migration_database):
    db = migration_database
    source = tmp_path / 'tracking_passivo.json'
    source.write_text(json.dumps({'proposal': historical()}))
    native = db.salva_tabella
    def changed(table, rows, inserter, delete_all=True):
        source.write_text('{}')
        return native(table, rows, inserter, delete_all=delete_all)
    monkeypatch.setattr(db, 'salva_tabella', changed)
    try:
        with pytest.raises(TimesheetConflict, match='durante'):
            migrate(db, source, tmp_path / 'backup')
        assert TrackingPassivoSQL(db).get('proposal') is None
    finally:
        db.chiudi()


def test_controllo_prontezza_non_muta_e_rileva_fonte_modificata(tmp_path, migration_database):
    from tools.migrate_tracking_passivo_sql import migration_ready
    db = migration_database
    source = tmp_path / 'tracking_passivo.json'
    assert migration_ready(db, source) is False
    migrate(db, source, tmp_path / 'backup')
    assert migration_ready(db, source) is True
    events = db.fetchall_readonly("SELECT id FROM audit_log WHERE azione='timesheet.proposte_adozione_sql'")
    assert len(events) == 1
    migrate(db, source, tmp_path / 'backup')
    assert len(db.fetchall_readonly("SELECT id FROM audit_log WHERE azione='timesheet.proposte_adozione_sql'")) == 1
    source.write_text('{}')
    with pytest.raises(TimesheetConflict):
        migration_ready(db, source)


def test_preparazione_installa_segnali_live_prima_degli_scrittori(tmp_path, migration_database):
    from pct.operational_live import read_live_revisions
    db = migration_database
    db.conn.execute("DELETE FROM _meta WHERE chiave='operational_live_v3'")
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    source = tmp_path / 'tracking_passivo.json'
    migrate(db, source, tmp_path / 'backup')
    before = read_live_revisions(db, {'timesheet'})
    repo = TrackingPassivoSQL(db)
    repo.insert([historical()])
    after = read_live_revisions(db, {'timesheet'})
    assert after['timesheet'] > before.get('timesheet', 0)
