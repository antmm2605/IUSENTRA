import os
import sqlite3

import pytest

from pct.pec_notification_presidio import NotificationPresidioRepository, NotificationPresidioService
from tests.test_condivisioni_sql_repository import SQLFactory
from tests.test_pec_notification_presidio import _candidate


@pytest.mark.parametrize('backend', ['sqlite', 'postgresql'])
def test_lettore_notificazioni_non_inizializza_e_non_scrive(tmp_path, monkeypatch, backend):
    if backend == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato: parità non verificata in questa esecuzione.')
    factory = SQLFactory(backend)
    path = tmp_path / 'controlled-notifications.db'
    dsn = ''
    blocked = sqlite3.OperationalError
    if backend == 'postgresql':
        from psycopg2.errors import ReadOnlySqlTransaction
        from psycopg2.extensions import make_dsn

        dsn = make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}')
        blocked = ReadOnlySqlTransaction
    writer = NotificationPresidioRepository(path, tenant_id='study-a', postgres_dsn=dsn)
    reader = None
    try:
        candidate_id = _candidate(NotificationPresidioService(writer), recipients=[{
            'name': 'Soggetto controllato', 'role': 'controparte', 'pec_address': 'recipient@example.test'}])
        monkeypatch.setattr(NotificationPresidioRepository, '_ensure_sqlite_schema', lambda *a: pytest.fail('Schema non richiesto'))
        if backend == 'postgresql':
            monkeypatch.setattr('pct.postgres_runtime_support.PostgresRepositoryBackend._ensure_schema', lambda *a: pytest.fail('Schema non richiesto'))
        reader = NotificationPresidioRepository(path, tenant_id='study-a', postgres_dsn=dsn, read_only=True)
        assert reader.list_presidia().items[0].id == candidate_id
        with pytest.raises(blocked):
            with reader.connection() as conn:
                conn.execute('DELETE FROM pec_legal_notification_presidia WHERE tenant_id=?', ('study-a',))
        assert writer.list_presidia().items[0].id == candidate_id
    finally:
        if reader:
            reader.close()
        writer.close()
        factory.close()


def test_sorgente_notificazioni_assente_non_diventa_un_archivio_vuoto(tmp_path):
    path = tmp_path / 'absent' / 'notifications.db'
    reader = NotificationPresidioRepository(path, tenant_id='study-a', read_only=True)
    with pytest.raises(sqlite3.OperationalError):
        reader.list_presidia()
    assert not path.parent.exists()
