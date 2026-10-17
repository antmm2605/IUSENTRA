from pathlib import Path

import pytest

from pct.pec_deposit_query_migration import begin, rebuild_batch
from tests.test_pec_deposit_query_repository import receipts as receipts


def test_lotti_riprendibili_con_backup_e_senza_cambiare_messaggi(receipts):
    database, repo = receipts
    conn = database.conn
    before = [tuple(row) for row in conn.execute('SELECT id,mime_sha256,original_mime FROM pec_messages ORDER BY id').fetchall()]
    args = dict(tenant=repo.tenant, backup_reference='controlled/native-backup', backup_sha256='a' * 64, actor='controlled-migration')
    state = begin(conn, **args)
    with pytest.raises(RuntimeError, match='non ancora confermato'):
        repo.list_page(state='ACCETTATO_CANCELLERIA')
    state = rebuild_batch(conn, repo, migration_id=state['id'], after_key='', actor=args['actor'], limit=1)
    resumed = begin(conn, **args)
    assert resumed['after_key'] == state['after_key']
    with pytest.raises(ValueError, match='Cursore'):
        rebuild_batch(conn, repo, migration_id=state['id'], after_key='', actor=args['actor'])
    while state['phase'] != 'COMPLETED':
        state = rebuild_batch(conn, repo, migration_id=state['id'], after_key=state['after_key'], actor=args['actor'], limit=1)
    assert [row['message_id'] for row in repo.list_page(state='ACCETTATO_CANCELLERIA')['rows']] == ['registry']
    after = [tuple(row) for row in conn.execute('SELECT id,mime_sha256,original_mime FROM pec_messages ORDER BY id').fetchall()]
    assert after == before
    with pytest.raises(ValueError, match='discordante'):
        begin(conn, **dict(args, backup_sha256='b' * 64))


def test_preparazione_senza_backup_non_autorizzata(receipts):
    database, repo = receipts
    with pytest.raises(ValueError, match='backup'):
        begin(database.conn, tenant=repo.tenant, backup_reference='', backup_sha256='', actor='controlled')


def test_schemi_gemelli_corrispondono_alle_definizioni_eseguite():
    from pct.pec_deposit_query_migration import DDL as migration_ddl
    from pct.pec_deposit_query_repository import DDL

    expected = [statement.strip() for statement in (*DDL, *migration_ddl)]
    for suffix in ('', '_postgres'):
        path = Path(__file__).resolve().parents[1] / ('pct/sql/20261016_pec_deposit_query_index' + suffix + '.sql')
        sql = '\n'.join(line for line in path.read_text(encoding='utf-8').splitlines() if not line.startswith('--'))
        assert [statement.strip() for statement in sql.split(';') if statement.strip()] == expected
