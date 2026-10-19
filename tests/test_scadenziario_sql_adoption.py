"""Fonte storica conservata, repository nativo e barriera per tutti i produttori."""
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from pct.scadenziario import GestioneScadenziario, TipoTermine
from pct.scadenziario_sql_adoption import adopt
from pct.scadenziario_sql_owner import owner_path
from pct.scadenziario_sql_writer import ScadenziarioConflict
from pct.storage import StudioDB


@pytest.fixture
def archive(tmp_path, monkeypatch):
    source = tmp_path / 'scadenziario/scadenze.json'
    legacy = GestioneScadenziario(str(source))
    item = legacy.nuova('Termine controllato', TipoTermine.ADEMPIMENTO, '2026-12-01',
                        note='Fonte preservata', source_document_name='provvedimento.pdf')
    database = StudioDB.get(str(tmp_path / 'studio.db'))
    postgres = os.environ.get('CTU_TEST_POSTGRES') == '1'
    raw = None
    if postgres:
        import psycopg2
        from psycopg2.extensions import make_dsn
        from psycopg2 import sql
        from pct.storage_postgres import PostgresStudioDB
        dsn = make_dsn(host=os.environ.get('CTU_TEST_PG_HOST', 'audit-postgres'),
                       dbname=os.environ.get('AUDIT_POSTGRES_DB', 'lex50_test'),
                       user=os.environ.get('AUDIT_POSTGRES_USER', 'iusentra_audit'),
                       password=os.environ['AUDIT_POSTGRES_PASSWORD'])
        raw = psycopg2.connect(dsn)
        schema = 'scadenze_adoption_' + uuid4().hex
        with raw.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        raw.commit()
        database = PostgresStudioDB(make_dsn(dsn, options='-c search_path=' + schema))
        owner = SimpleNamespace(database=object(), slug='studio-test')
        monkeypatch.setattr('pct.tenant.GestioneTenant', lambda **kwargs: SimpleNamespace(
            get=lambda slug: owner if slug == 'studio-test' else None,
            percorsi_dati=lambda *args, **kwargs: {'SCADENZIARIO_DB': str(source), 'STUDIO_DB': str(tmp_path / 'studio.db')}))
        monkeypatch.setattr('pct.core_storage_backend.build_core_storage_backend', lambda *args, **kwargs: database)
    def migrate(**kwargs):
        return adopt(database, source, tenant='studio-test', destination=tmp_path / 'backup/scadenze',
                     data_root=tmp_path, writers_drained=True, **kwargs)
    try:
        yield database, source, legacy, item, migrate
    finally:
        if raw is not None:
            database.chiudi()
            with raw.cursor() as cursor:
                cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
            raw.commit()
            raw.close()


def test_adozione_preserva_originale_campi_audit_e_produttori_senza_backend(archive):
    db, source, legacy, item, migrate = archive
    before = source.read_bytes()
    assert migrate()['source_records'] == 1
    current = GestioneScadenziario(str(source))
    assert current.get(item.id).to_dict() == item.to_dict()
    current.aggiorna(item.id, note='Confermato SQL')
    reopened = GestioneScadenziario(str(source), studio_db=db)
    assert reopened.get(item.id).note == 'Confermato SQL'
    assert source.read_bytes() == before
    assert json.loads(db.conn.execute("SELECT dettagli FROM audit_log WHERE azione='scadenziario.adozione_sql'").fetchone()[0])['added'] == 1
    assert migrate() == {'changed': False, 'tenant': 'studio-test'}
    with pytest.raises(RuntimeError, match='scrittura JSON storica bloccata'):
        legacy.aggiorna(item.id, note='Snapshot JSON superato')
    assert reopened.get(item.id).note == 'Confermato SQL'


def test_json_modificato_o_corrotto_non_diventa_fonte_dopo_adozione(archive):
    _, source, _, item, migrate = archive
    migrate()
    source.write_text('non è più una fonte operativa', encoding='utf-8')
    assert GestioneScadenziario(str(source)).get(item.id).note == 'Fonte preservata'


def test_cancellazione_sql_non_resuscita_dal_json(archive):
    db, source, _, item, migrate = archive
    migrate()
    db.conn.execute('DELETE FROM scadenze WHERE id=?', (item.id,))
    getattr(db, 'raw_conn', db.conn).commit()
    assert GestioneScadenziario(str(source)).get(item.id) is None


def test_snapshot_concorrente_conserva_cas_dopo_adozione(archive):
    _, source, _, item, migrate = archive
    migrate()
    left, right = GestioneScadenziario(str(source)), GestioneScadenziario(str(source))
    left.aggiorna(item.id, note='Vincitore')
    with pytest.raises(ScadenziarioConflict):
        right.aggiorna(item.id, note='Snapshot superato')
    assert GestioneScadenziario(str(source)).get(item.id).note == 'Vincitore'


def test_conflitto_storico_non_sovrascrive_sql_e_lascia_barriera(archive):
    db, source, _, item, migrate = archive
    native = GestioneScadenziario(str(source), studio_db=db)
    native.aggiorna(item.id, note='Versione SQL')
    payload = json.loads(source.read_text(encoding='utf-8'))
    payload[item.id]['note'] = 'Versione storica discordante'
    source.write_text(json.dumps(payload), encoding='utf-8')
    before = source.read_bytes()
    with pytest.raises(RuntimeError, match='discordante'):
        migrate()
    assert source.read_bytes() == before
    assert db.conn.execute('SELECT note FROM scadenze').fetchone()[0] == 'Versione SQL'
    with pytest.raises(RuntimeError, match='non confermata'):
        GestioneScadenziario(str(source))


@pytest.mark.parametrize('change', ['extra', 'id', 'enum', 'duplicate'])
def test_nessuna_riga_o_campo_scartato_silenziosamente(archive, change):
    db, source, _, item, migrate = archive
    payload = item.to_dict()
    if change == 'extra':
        payload['campo_sconosciuto'] = 'conservare'
    elif change == 'id':
        payload['id'] = 'altro'
    elif change == 'enum':
        payload['stato'] = 'SCONOSCIUTO'
    raw = [payload, payload] if change == 'duplicate' else {item.id: payload}
    source.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises(ValueError):
        migrate()
    assert not owner_path(source).exists()
    assert db.conn.execute('SELECT COUNT(*) FROM scadenze').fetchone()[0] == 0


def test_backend_errato_e_marker_corrotto_non_ripiegano_sul_json(archive, tmp_path):
    _, source, _, _, migrate = archive
    migrate()
    other = StudioDB.get(str(tmp_path / 'other.db'))
    with pytest.raises(RuntimeError, match='diverso dal proprietario'):
        GestioneScadenziario(str(source), studio_db=other)
    owner_path(source).write_text('{', encoding='utf-8')
    with pytest.raises(RuntimeError, match='non leggibile'):
        GestioneScadenziario(str(source))


def test_backup_fallito_non_cambia_sql_e_non_attiva_fence(archive, monkeypatch):
    db, source, _, _, migrate = archive
    def failed(*args):
        raise OSError('Backup indisponibile')
    monkeypatch.setattr('scripts.query_index_backup.verified_backup', failed)
    with pytest.raises(OSError):
        migrate()
    assert not owner_path(source).exists()
    assert db.conn.execute('SELECT COUNT(*) FROM scadenze').fetchone()[0] == 0


def test_consultazione_sql_non_legge_json_non_deduplica_non_scrive(archive, monkeypatch):
    db, source, _, item, migrate = archive
    migrate()
    def forbidden(*args, **kwargs):
        raise AssertionError('Lavorazione estranea alla consultazione SQL')
    monkeypatch.setattr(GestioneScadenziario, '_carica_json_file', forbidden)
    monkeypatch.setattr(GestioneScadenziario, '_deduplica_pec_automatiche', forbidden)
    monkeypatch.setattr(GestioneScadenziario, '_salva', forbidden)
    assert GestioneScadenziario(str(source), studio_db=db).get(item.id).titolo == item.titolo


def test_interruzione_dopo_backup_riprende_senza_doppio_audit(archive, monkeypatch):
    db, source, _, item, migrate = archive
    from pct.scadenziario_sql_adoption import write_changes
    def interrupted(*args, **kwargs):
        raise RuntimeError('Interruzione controllata')
    monkeypatch.setattr('pct.scadenziario_sql_adoption.write_changes', interrupted)
    with pytest.raises(RuntimeError, match='Interruzione controllata'):
        migrate()
    with pytest.raises(RuntimeError, match='non confermata'):
        GestioneScadenziario(str(source))
    monkeypatch.setattr('pct.scadenziario_sql_adoption.write_changes', write_changes)
    assert migrate()['changed'] is True
    assert GestioneScadenziario(str(source)).get(item.id).id == item.id
    assert db.conn.execute("SELECT COUNT(*) FROM audit_log WHERE azione='scadenziario.adozione_sql'").fetchone()[0] == 1
