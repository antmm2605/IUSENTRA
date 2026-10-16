"""Date effettive e isolamento delle consultazioni, senza inviare notifiche."""
import os
from datetime import date

import pytest

from pct.pec_notification_presidio import NotificationPresidioRepository, NotificationPresidioService
from tests.test_condivisioni_sql_repository import SQLFactory
from tests.test_pec_notification_presidio import _candidate


@pytest.fixture(params=['sqlite', 'postgresql'])
def repository(request, tmp_path):
    if request.param == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato in questa esecuzione.')
    factory = SQLFactory(request.param)
    dsn = ''
    if request.param == 'postgresql':
        from psycopg2.extensions import make_dsn
        dsn = make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}')
    repo = NotificationPresidioRepository(tmp_path / 'notifications.db', tenant_id='study-a', postgres_dsn=dsn)
    try:
        yield repo
    finally:
        repo.close()
        factory.close()


def candidate(repo):
    return _candidate(NotificationPresidioService(repo), recipients=[{
        'name': 'Destinatario controllato', 'role': 'controparte', 'pec_address': 'recipient@example.test'}])


def test_scadenza_non_data_di_creazione_e_confine_italiano(repository):
    key = candidate(repository)
    with repository.connection() as conn:
        conn.execute('UPDATE pec_legal_notification_presidia SET explicit_due_at=? WHERE tenant_id=? AND id=?',
                     ('2026-10-13T22:00:00Z', repository.tenant_id, key))
    page = repository.list_operational_page(mode='pending', ranges=((date(2026, 10, 14), date(2026, 10, 14)),))
    assert [row['id'] for row in page['rows']] == [key]
    assert page['rows'][0]['event_at'] == '2026-10-13T22:00:00.000000Z'
    assert page['unknown_date_count'] == 0
    assert repository.list_operational_page(mode='pending', ranges=((date(2026, 10, 13), date(2026, 10, 13)),))['rows'] == []
    with repository.connection() as conn:
        conn.execute("UPDATE pec_legal_notification_presidia SET status='CLOSED' WHERE tenant_id=? AND id=?",
                     (repository.tenant_id, key))
    assert repository.list_operational_page(mode='pending')['rows'] == []


def test_rac_priva_di_data_non_usa_data_ordine_o_aggiornamento(repository):
    key = candidate(repository)
    assert repository.list_operational_page(mode='accepted')['rows'] == []
    with repository.connection() as conn:
        conn.execute("UPDATE pec_legal_notification_recipients SET rac_status='received',rac_message_id='rac-controlled' "
                     'WHERE tenant_id=? AND presidio_id=?', (repository.tenant_id, key))
    page = repository.list_operational_page(mode='accepted', ranges=((date(2026, 7, 20), date(2026, 7, 20)),))
    assert page['rows'] == []
    assert page['unknown_date_count'] == 1
    undated = repository.list_operational_page(mode='accepted')['rows']
    assert undated[0]['event_at'] == ''
    assert undated[0]['date_axis'] == 'rac_at'


def test_tenant_e_modalita_espliciti(repository):
    candidate(repository)
    original = repository.tenant_id
    repository.tenant_id = 'other-study'
    assert repository.list_operational_page(mode='pending')['rows'] == []
    repository.tenant_id = original
    with pytest.raises(ValueError):
        repository.list_operational_page(mode='anything')


def test_rac_registrata_resta_trovabile_dopo_consegna_senza_duplicati(repository):
    key = candidate(repository)
    with repository.connection() as conn:
        conn.execute("UPDATE pec_legal_notification_recipients SET rac_status='received',rac_message_id='rac-controlled' "
                     'WHERE tenant_id=? AND presidio_id=?', (repository.tenant_id, key))
        for index, stamp in enumerate(('2026-10-13T21:59:59Z', '2026-10-13T22:00:00.000001Z')):
            previous = conn.execute('SELECT next_status FROM pec_legal_notification_transitions '
                                    'WHERE tenant_id=? AND presidio_id=? ORDER BY chain_index DESC LIMIT 1',
                                    (repository.tenant_id, key)).fetchone()[0]
            repository._append_transition_row(
                conn, presidio_id=key, previous_status=previous, next_status='RAC_RECEIVED',
                actor='controlled-test', reason='Prova sintetica', evidence={'message_id': 'rac-controlled'},
                idempotency_key=f'rac-controlled-{index}', occurred_at=stamp)
        conn.execute("UPDATE pec_legal_notification_presidia SET status='DELIVERY_COMPLETE' WHERE tenant_id=? AND id=?",
                     (repository.tenant_id, key))
    period = ((date(2026, 10, 14), date(2026, 10, 14)),)
    page = repository.list_operational_page(mode='accepted', ranges=period)
    assert len(page['rows']) == 1
    assert page['rows'][0]['id'] == key
    assert page['rows'][0]['event_at'] == '2026-10-13T22:00:00.000001Z'
    assert page['unknown_date_count'] == 0
    assert page['has_more'] is False
