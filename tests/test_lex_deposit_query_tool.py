from contextlib import contextmanager
import json
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from urllib.parse import unquote

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


@pytest.mark.parametrize('question', [
    'ricevute di accettazione il 14/10/26',
    'Ricevute di accettazione del 14/10/2026, anche nei fascicoli',
    'ricevute di accettazione nei fascicoli il 14.10.2026',
])
def test_lex_ricevute_nei_documenti_usa_catalogo_e_link_originale(registry, monkeypatch, question):
    put(registry, 'original-receipt')
    put(registry, 'same-bytes-copy')
    prepare(registry)
    monkeypatch.setattr('web.services.receipt_archive_payload.registro_corrente', lambda **_: registry)
    monkeypatch.setattr('web.services.receipt_archive_payload.tenant_corrente', lambda: 'study-a')
    selection = resolve_query_selection(question, today=date(2026, 10, 17))
    assert selection is not None and selection.domain == 'archived_receipts'
    result = OperationalKnowledgeTools().query_archived_receipts_page(context(), selection=selection)
    assert result.ok and result.query_metadata['executed']
    assert len(result.data) == 1
    assert len(result.data[0]['evidence_sources']) == 2
    assert not result.data[0]['legal_notification_confirmed']
    assert {row['href'] for row in result.data[0]['evidence_sources']} == {
        '/fascicoli/case-a/documenti/original-receipt/visualizza',
        '/fascicoli/case-a/documenti/same-bytes-copy/visualizza',
    }
    assert OperationalQueryRouter().route(question).intent == 'receipt_archive_query_page'


@pytest.mark.parametrize('suffix', [
    'nel fascicolo Rossi', 'nei fascicoli del cliente Rossi',
    'nel fascicolo RG 123/2026', 'solo nei fascicoli',
    'nei fascicoli 123/2026', 'nei fascicoli: 123/2026',
    'nei fascicoli n. 123/2026',
])
def test_ricevute_non_perdono_filtri_specifici_o_esclusivi(suffix):
    question = 'ricevute di consegna ieri ' + suffix
    route = OperationalQueryRouter().route(question)
    assert route is None or route.intent != 'receipt_archive_query_page'
    assert resolve_query_selection(question, today=date(2026, 10, 17)) is None


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


def _http_readonly_query(question, streaming, *, data=None):
    from flask import g
    from lex.orchestrator_http import build_context_response, chat_response

    class ForbiddenDependencies:
        def __getattr__(self, name):
            pytest.fail('Contesto, modello o pipeline non richiesti: ' + name)

    authorizations = []
    owner = SimpleNamespace(slug='study-a')
    user = SimpleNamespace(id='controlled', tenant_slug=owner.slug, ha_permesso=lambda _: True)
    orchestrator = SimpleNamespace(
        auth_guard=SimpleNamespace(ensure_can_access=lambda **kw: authorizations.append(kw)),
        dependencies=ForbiddenDependencies(),
    )
    app = Flask(__name__)
    app.secret_key = 'controlled-http-readonly-query'
    app.config['MULTI_TENANT'] = True
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owner
        arguments = dict(orchestrator=orchestrator, user=user, studio=owner, data=data or {},
                         resolve_messages=lambda **_: (question, '', []))
        if streaming:
            response = chat_response(**arguments,
                messages_with_effective_question=lambda **_: pytest.fail('Prompt non richiesto'))
            events = ''.join(response.response).splitlines()
            assert 'data: [DONE]' in events
            payload = next(json.loads(line[6:])['payload'] for line in events
                           if line.startswith('data: {'))
        else:
            payload, status = build_context_response(**arguments)
            assert status == 200
    assert len(authorizations) == 1
    return payload


@pytest.mark.parametrize('streaming', [False, True])
def test_http_depositi_usa_repository_nativo_senza_contesto_esteso(receipts, registry, monkeypatch, streaming):
    database, _ = receipts
    put(registry, 'controlled-original')
    prepare(registry)

    @contextmanager
    def connection(*, tenant, writable=False):
        assert tenant == 'study-a' and not writable
        yield database.conn

    monkeypatch.setattr('web.services.pec_audit_query_connection.pec_audit_query_connection', connection)
    monkeypatch.setattr('web.services.receipt_archive_payload.registro_corrente', lambda **_: registry)
    monkeypatch.setattr('web.services.receipt_archive_payload.tenant_corrente', lambda: 'study-a')
    payload = _http_readonly_query('depositi accettati il 14/10/26', streaming)
    assert 'accettazione della cancelleria' in payload['answer']
    assert '1 ricevuta in questa pagina' in payload['answer']
    assert '/email/?audit_id=registry' in unquote(payload['answer'])
    assert '14 ottobre 2026' in payload['answer']


@pytest.mark.parametrize('streaming', [False, True])
def test_http_ricevute_archiviate_conserva_copie_e_fonti_senza_ai(registry, monkeypatch, streaming):
    put(registry, 'controlled-original')
    put(registry, 'controlled-copy')
    prepare(registry)
    monkeypatch.setattr('web.services.receipt_archive_payload.registro_corrente', lambda **_: registry)
    monkeypatch.setattr('web.services.receipt_archive_payload.tenant_corrente', lambda: 'study-a')
    payload = _http_readonly_query('ricevute di accettazione il 14/10/26 anche nei fascicoli', streaming)
    assert '1 prova in questa pagina' in payload['answer']
    assert '2 copie identiche' in payload['answer']
    links = [f'/fascicoli/case-a/documenti/{key}/visualizza'
             for key in ('controlled-original', 'controlled-copy')]
    # La card usa una copia rappresentativa; il repository conserva entrambe.
    assert any(link in unquote(payload['answer']) for link in links)


@pytest.mark.parametrize('streaming', [False, True])
def test_http_continuazione_ricevute_invalida_non_avvia_altri_motori(streaming):
    payload = _http_readonly_query('mostra altre ricevute archiviate', streaming,
                                 data={'query_continuation': 'invalid-controlled-token'})
    assert payload.get('answer')
    assert 'non' in payload['answer'].casefold()


@pytest.mark.parametrize('question,data,attachments', [
    ('depositi accettati oggi', {'active_context': {'case_id': 'case-a'}}, []),
    ('depositi accettati oggi', {'page_path': '/fascicoli/case-a#documenti'}, []),
    ('depositi accettati oggi', {'free_web_enabled': True}, []),
    ('depositi accettati oggi', {}, [{'id': 'controlled-attachment'}]),
    ('depositi accettati per il cliente Rossi', {}, []),
    ('ricevute di consegna solo nei fascicoli', {}, []),
    ('ricevute di consegna nel fascicolo RG 123/2026', {}, []),
    ('invia PEC oggi', {}, []),
    ('art. 327 procedura civile', {}, []),
])
def test_http_consultazione_minima_non_perde_contesto_filtri_o_comandi(monkeypatch, question, data, attachments):
    from lex.orchestrator_http import _structured_operational_http_payload

    monkeypatch.setattr('lex.operational_knowledge.integration.build_operational_http_payload',
                        lambda **_: pytest.fail('Percorso globale SQL non pertinente'))
    assert _structured_operational_http_payload(user=None, studio=None, data=data,
        question=question, attachments=attachments) is None


@pytest.mark.parametrize('streaming', [False, True])
def test_http_pagine_ricevute_conservano_periodo_e_non_ripetono_fonti(registry, monkeypatch, streaming):
    monkeypatch.setenv('LEX_OPERATIONAL_MAX_RESULTS', '2')
    for index in range(3):
        put(registry, f'controlled-{index}', sha=f'{index + 1:064x}')
    prepare(registry)
    monkeypatch.setattr('web.services.receipt_archive_payload.registro_corrente', lambda **_: registry)
    monkeypatch.setattr('web.services.receipt_archive_payload.tenant_corrente', lambda: 'study-a')
    first = _http_readonly_query('ricevute di accettazione il 14/10/26', streaming)
    page = first['metadata']['query_page']
    assert page['has_more'] and page['ranges'] == [['2026-10-14', '2026-10-14']]
    action = next(action for action in first['lex_actions'] if action['key'] == 'query_next_page')
    assert action['query_continuation'] == page['continuation']
    second = _http_readonly_query(action['prompt'], streaming,
                                 data={'query_continuation': action['query_continuation']})
    assert second['metadata']['query_page']['ranges'] == page['ranges']
    assert not second['metadata']['query_page']['has_more']
    first_ids = {source['id'] for source in first['sources']}
    second_ids = {source['id'] for source in second['sources']}
    assert len(first_ids) == 2 and len(second_ids) == 1
    assert not first_ids.intersection(second_ids)
