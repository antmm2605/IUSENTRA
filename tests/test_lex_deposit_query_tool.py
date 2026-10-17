from contextlib import contextmanager
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest
from flask import Flask

from lex.operational_knowledge.models import OperationalQueryContext
from lex.operational_knowledge.query_cursor import decode_query_cursor, encode_query_cursor
from lex.operational_knowledge.query_router import OperationalQueryRouter
from lex.operational_knowledge.query_selection import resolve_query_selection
from lex.operational_knowledge.tools import OperationalKnowledgeTools
from tests.test_pec_deposit_query_repository import receipts as receipts
from tests.test_receipt_archive_query import prepare, put
from tests.test_receipt_sources_consultation import registry as registry


def context():
    return OperationalQueryContext(tenant_id='study-a', user_id='controlled',
        user=SimpleNamespace(id='controlled'), permissions={'ai.usa', 'messaggi.leggi', 'fascicoli.leggi'})


def test_rbac_blocca_prima_di_aprire_ricevute(monkeypatch):
    monkeypatch.setattr('web.services.pec_audit_query_connection.pec_audit_query_connection',
                        lambda **kw: pytest.fail('Archivio aperto senza permessi'))
    selection = resolve_query_selection('depositi accettati oggi', today=date(2026, 10, 14))
    result = OperationalKnowledgeTools().query_deposit_receipts_page(
        OperationalQueryContext(tenant_id='study-a', user_id='controlled'), selection=selection)
    assert not result.ok


@pytest.mark.parametrize('question,state,identifier', [
    ('depositi accettati il 14/10/26', 'ACCETTATO_CANCELLERIA', 'registry'),
    ('depositi accettati dal gestore PEC il 14.10.2026', 'ACCETTATO_PEC', 'pec'),
])
def test_lex_interroga_repository_reale_solo_lettura_e_apre_fonte(receipts, monkeypatch, question, state, identifier):
    database, _repository = receipts
    @contextmanager
    def connection(*, tenant, writable=False):
        assert tenant == 'study-a' and not writable
        yield database.conn
    monkeypatch.setattr('web.services.pec_audit_query_connection.pec_audit_query_connection', connection)
    monkeypatch.setattr('pct.pec_pipeline.PecAuditRepository.__init__',
                        lambda *a, **kw: pytest.fail('Pipeline non richiesta'))
    selection = resolve_query_selection(question, today=date(2026, 10, 17))
    result = OperationalKnowledgeTools().query_deposit_receipts_page(context(), selection=selection)
    assert result.ok and result.query_metadata['executed']
    assert result.query_metadata['states'] == [state]
    assert [row['id'] for row in result.data] == [identifier]
    assert result.data[0]['action_url'] == '/email/?audit_id=' + identifier
    assert result.data[0]['id_fascicolo'] == ''
    assert 'original_mime' not in result.data[0] and 'report_json' not in result.data[0]
    assert OperationalQueryRouter().route(question).intent == 'deposit_query_page'


def test_router_non_perde_cliente_fascicolo_o_procedura_da_fare():
    router = OperationalQueryRouter()
    for question, metadata in [
        ('depositi accettati per il cliente Rossi', {}),
        ('depositi accettati oggi', {'active_context': {'case_id': 'case-a'}}),
        ('depositi da fare domani', {}),
    ]:
        route = router.route(question, metadata=metadata)
        assert route is None or route.intent != 'deposit_query_page'


def test_continuazione_non_cambia_studio_o_fase():
    app = Flask(__name__)
    app.secret_key = 'controlled-deposit-cursor'
    selected = resolve_query_selection('depositi accettati dal gestore ieri', today=date(2026, 10, 15))
    with app.app_context():
        token = encode_query_cursor(context(), selected, ('2026-10-14T08:00:00.000000+00:00', 'one'))
        decoded, cursor = decode_query_cursor(token, context())
        assert decoded == selected and cursor[1] == 'one'
        with pytest.raises(ValueError):
            decode_query_cursor(token, replace(context(), tenant_id='other-study'))
        invalid = encode_query_cursor(context(), replace(selected, date_axis='registry_acceptance_at'), cursor)
        with pytest.raises(ValueError):
            decode_query_cursor(invalid, context())


def test_lex_ricevute_nei_documenti_usa_catalogo_e_link_originale(registry, monkeypatch):
    put(registry, 'original-receipt')
    put(registry, 'same-bytes-copy')
    prepare(registry)
    monkeypatch.setattr('web.services.receipt_archive_payload.registro_corrente', lambda **_: registry)
    monkeypatch.setattr('web.services.receipt_archive_payload.tenant_corrente', lambda: 'study-a')
    selection = resolve_query_selection('ricevute di accettazione il 14/10/26', today=date(2026, 10, 17))
    result = OperationalKnowledgeTools().query_archived_receipts_page(context(), selection=selection)
    assert result.ok and result.query_metadata['executed']
    assert len(result.data) == 1
    assert len(result.data[0]['evidence_sources']) == 2
    assert not result.data[0]['legal_notification_confirmed']
    assert {row['href'] for row in result.data[0]['evidence_sources']} == {
        '/fascicoli/case-a/documenti/original-receipt/visualizza',
        '/fascicoli/case-a/documenti/same-bytes-copy/visualizza',
    }
    assert OperationalQueryRouter().route('ricevute di accettazione il 14/10/26').intent == 'receipt_archive_query_page'


def test_lex_archivio_senza_permessi_non_apre_repository(monkeypatch):
    monkeypatch.setattr('web.services.receipt_archive_payload.archived_receipt_page',
                        lambda **_: pytest.fail('Archivio aperto senza permessi'))
    selected = resolve_query_selection('ricevute di consegna ieri', today=date(2026, 10, 17))
    result = OperationalKnowledgeTools().query_archived_receipts_page(
        OperationalQueryContext(tenant_id='study-a', user_id='controlled'), selection=selected)
    assert not result.ok
