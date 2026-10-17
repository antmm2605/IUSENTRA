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


@pytest.mark.parametrize('kind', ['rac', 'rdac'])
def test_risposta_archivio_mostra_data_copie_e_limiti_della_prova(kind):
    from lex.operational_knowledge.models import OperationalRoute, OperationalToolResult
    from lex.operational_knowledge.response_composer import OperationalResponseComposer

    source = dict(id='receipt', titolo='Ricevuta controllata', data='2026-10-14T09:30:00+02:00',
                  action_url='/fascicoli/case-a/documenti/receipt/visualizza', verified=False,
                  evidence_sources=[dict(id='original'), dict(id='copy')])
    page = dict(states=[kind], ranges=[['2026-10-14', '2026-10-15']], has_more=True)
    result = OperationalToolResult(True, 'archived_receipts', data=[source], query_metadata=page)
    answer = OperationalResponseComposer().compose(question='ricevute archiviate',
        route=OperationalRoute('controlled', 'receipt_archive_query_page', ('archived_receipts',)), results=[result])
    assert '1 prova in questa pagina' in answer.answer
    assert '14 ottobre 2026' in answer.answer and '15 ottobre 2026' in answer.answer
    assert source['action_url'] in answer.answer
    assert '2 copie identiche' in answer.answer
    assert 'Classificazione della fonte da verificare' in answer.answer
    assert 'non conferma da sola' in answer.answer
    assert ('accettazione PEC' if kind == 'rac' else 'avvenuta consegna PEC') in answer.answer
    assert answer.metadata['query_page'] == page


@pytest.mark.parametrize('transport', [True, False])
def test_risposta_deposito_non_confonde_gestore_cancelleria_e_documenti(transport):
    from lex.operational_knowledge.models import OperationalRoute, OperationalToolResult
    from lex.operational_knowledge.response_composer import OperationalResponseComposer

    archive = dict(id='document', titolo='Prova archivio', data='2026-10-14',
                   action_url='/fascicoli/case-a/documenti/document/visualizza')
    source = dict(id='receipt', titolo='Ricevuta controllata', data='2026-10-14',
                  action_url='/email/?audit_id=receipt', stato='ACCETTATO_PEC', id_fascicolo='')
    page = dict(date_axis='pec_acceptance_at' if transport else 'registry_acceptance_at',
                ranges=[['2026-10-14', '2026-10-14']], has_more=True,
                archive_executed=True, archive_evidence=[archive], archive_has_more=True)
    answer = OperationalResponseComposer().compose(question='depositi accettati',
        route=OperationalRoute('controlled', 'deposit_query_page', ('deposit_receipts',)),
        results=[OperationalToolResult(True, 'deposit_receipts', data=[source], query_metadata=page)])
    assert '1 ricevuta in questa pagina' in answer.answer
    assert 'Collegamento al fascicolo non confermato' in answer.answer
    from urllib.parse import unquote
    assert source['action_url'] in unquote(answer.answer) and archive['action_url'] in unquote(answer.answer)
    assert 'non vengono sommate' in answer.answer and 'Sono presenti altre prove archiviate' in answer.answer
    assert ('non dimostra l’accettazione del deposito' in answer.answer) is transport


@pytest.mark.parametrize('unknown', [0, 1])
def test_risposta_deposito_vuoto_distingue_assenza_esiti_da_data_non_provata(unknown):
    from lex.operational_knowledge.models import OperationalRoute, OperationalToolResult
    from lex.operational_knowledge.response_composer import OperationalResponseComposer

    answer = OperationalResponseComposer().compose(question='depositi accettati oggi',
        route=OperationalRoute('controlled', 'deposit_query_page', ('deposit_receipts',)),
        results=[OperationalToolResult(True, 'deposit_receipts', data=[],
            query_metadata=dict(unknown_date_count=unknown, archive_executed=True, archive_evidence=[]))])
    assert ('tra gli esiti databili e confermati' in answer.answer) is bool(unknown)
    assert 'nessuna ulteriore prova' in answer.answer
    assert '0 ricevute' not in answer.answer


def test_cursor_archivio_conserva_tipo_prova_e_rifiuta_filtri_estranei():
    app = Flask(__name__)
    app.secret_key = 'controlled-archive-cursor'
    selected = resolve_query_selection('ricevute di consegna ieri', today=date(2026, 10, 15))
    position = ('2026-10-14T08:00:00.000000+00:00', 'one')
    with app.app_context():
        token = encode_query_cursor(context(), selected, position)
        assert decode_query_cursor(token, context()) == (selected, position)
        for invalid in (replace(selected, states=('rac', 'rdac')), replace(selected, direction='sent'),
                        replace(selected, date_axis='message_at')):
            with pytest.raises(ValueError):
                decode_query_cursor(encode_query_cursor(context(), invalid, position), context())
