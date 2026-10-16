"""Ripresa, backup e cursori del catalogo su database controllati."""
import pytest

from pct.fascicoli_list_migration import begin, rebuild_batch, install_migration_schema
from pct.fascicoli_list_query import FascicoliListNotReady
from tests.test_fascicoli_list_query import catalog as catalog


def test_preparazione_a_lotti_e_ripresa_non_rileggono_fascicoli_precedenti(catalog):
    db, repo = catalog
    install_migration_schema(db.conn)
    db.conn.execute('CREATE TABLE fascicoli(id TEXT PRIMARY KEY)')
    db.conn.execute('CREATE TABLE scadenze(id TEXT PRIMARY KEY)')
    for number in range(61):
        db.conn.execute('INSERT INTO fascicoli VALUES (?)', (f'F{number:03}',))
    state = begin(db.conn, tenant='studio', backup_reference='backup-controllato.db', backup_sha256='a' * 64, actor='test')
    with pytest.raises(FascicoliListNotReady):
        repo.list_page()
    seen = {'IDENTITIES': [], 'ROWS': []}

    def project(_conn, keys, *, phase):
        assert 1 <= len(keys) <= 20
        seen[phase].extend(keys)

    while state['phase'] != 'COMPLETED':
        state = rebuild_batch(db.conn, tenant='studio', migration_id=state['id'], actor='test',
            phase=state['phase'], after_key=state['after_key'], project=project, limit=20)
        resume = begin(db.conn, tenant='studio', backup_reference='backup-controllato.db', backup_sha256='a' * 64, actor='test')
        assert resume['phase'] == state['phase'] and resume['after_key'] == state['after_key']
    assert seen['IDENTITIES'] == seen['ROWS'] == [f'F{n:03}' for n in range(61)]
    assert repo.list_page()['pagination']['total'] == 61
    assert db.conn.execute('SELECT COUNT(*) FROM fascicoli').fetchone()[0] == 61


def test_preparazione_rifiuta_autore_backup_e_cursore_non_corrispondenti(catalog):
    db, _repo = catalog
    install_migration_schema(db.conn)
    db.conn.execute('CREATE TABLE fascicoli(id TEXT PRIMARY KEY)')
    state = begin(db.conn, tenant='studio', backup_reference='backup-controllato.db', backup_sha256='a' * 64, actor='test')
    with pytest.raises(ValueError, match='Backup o autore'):
        begin(db.conn, tenant='studio', backup_reference='backup-controllato.db', backup_sha256='b' * 64, actor='test')
    with pytest.raises(ValueError, match='altro studio'):
        begin(db.conn, tenant='altro', backup_reference='backup-controllato.db', backup_sha256='a' * 64, actor='test')
    for actor, cursor in (('altro', ''), ('test', 'inventato')):
        with pytest.raises(ValueError, match='Cursore'):
            rebuild_batch(db.conn, tenant='studio', migration_id=state['id'], actor=actor,
                phase='IDENTITIES', after_key=cursor, project=lambda *_args, **_kwargs: pytest.fail('Lotto non autorizzato'))


def test_studio_nuovo_prepara_catalogo_vuoto_con_backup_senza_leggere_documenti(tmp_path):
    from pct.storage import StudioDB
    from pct.fascicoli_list_migration import prepare_empty_catalog
    from pct.fascicoli_list_query import FascicoliListQuery
    database = StudioDB(str(tmp_path / 'studio.db'))
    try:
        assert prepare_empty_catalog(database, tenant='nuovo-studio',
            registry_path=tmp_path / 'registro.db', backup_dir=tmp_path / 'backup')
        assert FascicoliListQuery(database, 'nuovo-studio').list_page()['pagination']['total'] == 0
        assert (tmp_path / 'backup' / 'core' / 'manifest.json').is_file()
        assert (tmp_path / 'backup' / 'registro' / 'manifest.json').is_file()
    finally:
        database.chiudi()
