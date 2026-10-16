"""Confine studio e repository reali, con soli dati sintetici temporanei."""
import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest
from flask import Flask, g

from pct.email_client import GestioneEmailRicevute
from pct.email_mailbox_repository import EmailMailboxRepository, MailboxNotInitialized
from pct.storage import StudioDB
from pct.tenant import StudioLegale
from web.services.email_mailbox_readonly import mailbox_reader
from web.services.studio_readonly import request_studio_reader
from web.services.tenant_isolation_runtime import TenantIsolationError


@pytest.fixture
def studies(tmp_path):
    registry = tmp_path / 'tenants.json'
    owners = [StudioLegale(slug=name, db_config={'mode': 'SQLITE'}) for name in ('study-a', 'study-b')]
    registry.write_text(json.dumps({owner.slug: owner.to_dict() for owner in owners}), encoding='utf-8')
    databases = []
    for owner in owners:
        root = tmp_path / 'tenants' / owner.slug
        (root / 'email').mkdir(parents=True)
        db = StudioDB(str(root / 'studio.db'))
        repository = EmailMailboxRepository(db, owner.slug, 'pec')
        repository.ensure_schema()
        repository.initialize({'one': {'id': 'one', 'subject': owner.slug}}, source_of_truth='sqlite')
        databases.append(db)
    app = Flask(__name__)
    app.config.update(MULTI_TENANT=True, TENANTS_REGISTRY=str(registry))
    try:
        yield app, owners, databases, tmp_path
    finally:
        for db in databases:
            db.chiudi()


def test_mailbox_reads_only_the_current_study_without_managers(studies, monkeypatch):
    app, owners, _, root = studies

    def forbidden(*args, **kwargs):
        raise AssertionError('Preparazione o caricamento del catalogo non richiesto')

    monkeypatch.setattr(GestioneEmailRicevute, '__init__', forbidden)
    monkeypatch.setattr(EmailMailboxRepository, 'ensure_schema', forbidden)
    monkeypatch.setattr('web.services.email_storage_runtime._initialize_empty_sql_catalog', forbidden)
    for owner in owners:
        with app.test_request_context('/api/assistente/chat'):
            g.tenant = owner
            path = root / 'tenants' / owner.slug / 'email' / 'casella.json'
            with mailbox_reader(path, expected_tenant=owner.slug) as repository:
                assert repository.load(message_keys=['one'], update_original=False)['one']['subject'] == owner.slug
                with pytest.raises(sqlite3.OperationalError):
                    repository.db.conn.execute('DELETE FROM email_mailbox_records')


def test_other_study_path_and_context_cannot_be_used(studies):
    app, owners, _, root = studies
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owners[0]
        with pytest.raises(RuntimeError, match='non appartiene'):
            with mailbox_reader(root / 'tenants' / owners[1].slug / 'email' / 'casella.json', expected_tenant=owners[0].slug):
                pytest.fail('Il repository di un altro studio non deve essere aperto')
        with pytest.raises(PermissionError):
            with mailbox_reader(root / 'tenants' / owners[0].slug / 'email' / 'casella.json', expected_tenant=owners[1].slug):
                pytest.fail('Il contesto discordante non deve essere aperto')
        with pytest.raises(TenantIsolationError):
            with request_studio_reader(str(root / 'tenants' / owners[1].slug / 'email' / 'casella.json')):
                pytest.fail('Il percorso fuori studio non deve essere aperto')


def test_missing_context_is_explicit_and_does_not_create_data(studies):
    app, _, _, root = studies
    path = root / 'missing' / 'email' / 'casella.json'
    with app.test_request_context('/api/assistente/chat'):
        with pytest.raises(PermissionError):
            with request_studio_reader(str(path)):
                pytest.fail('Contesto assente')
    assert not path.parent.exists()


def test_no_implicit_mailbox_initialization(studies):
    app, owners, databases, root = studies
    db = databases[0]
    db.conn.execute('DELETE FROM email_mailbox_bootstrap WHERE tenant_key=?', (owners[0].slug,))
    db.conn.commit()
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owners[0]
        with pytest.raises(MailboxNotInitialized):
            with mailbox_reader(root / 'tenants' / owners[0].slug / 'email' / 'casella.json', expected_tenant=owners[0].slug):
                pytest.fail('Nessuna inizializzazione automatica')
    assert db.conn.execute('SELECT COUNT(*) FROM email_mailbox_bootstrap WHERE tenant_key=?', (owners[0].slug,)).fetchone()[0] == 0


def test_lex_page_permissions_before_sql_and_no_unrequested_managers(studies, monkeypatch):
    from lex.operational_knowledge.models import OperationalQueryContext
    from lex.operational_knowledge.query_selection import resolve_query_selection
    from lex.operational_knowledge.tools import OperationalKnowledgeTools

    app, owners, databases, root = studies
    owner = owners[0]
    repo = EmailMailboxRepository(databases[0], owner.slug, 'pec')
    values = repo.load()
    values['one'].update(data='2026-10-14T12:00:00+02:00', cartella='INBOX', oggetto='Fonte sintetica')
    repo.save(values, actor_key='controlled-user')
    tools = OperationalKnowledgeTools()
    monkeypatch.setattr(tools, '_email_manager', lambda *a, **k: pytest.fail('Gestore non richiesto'))
    monkeypatch.setattr(EmailMailboxRepository, 'load', lambda *a, **k: pytest.fail('Catalogo completo non richiesto'))
    monkeypatch.setattr(EmailMailboxRepository, 'ensure_schema', lambda *a, **k: pytest.fail('DDL non richiesto'))
    selection = resolve_query_selection('PEC ricevute il 14/10/26', today=date(2026, 10, 16))
    user = SimpleNamespace(id='controlled-user', tenant_slug=owner.slug, ha_permesso=lambda permission: True)
    context = OperationalQueryContext(owner.slug, user.id, user=user, multi_tenant=True)
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owner
        g.data_paths = {'EMAIL_CASELLA_DB': str(root / 'tenants' / owner.slug / 'email' / 'casella.json')}
        result = tools.query_pec_page(context, selection=selection)
        assert result.ok, result.coverage_gaps
        assert [row['id'] for row in result.data] == ['one']
        assert result.query_metadata['ranges'] == [['2026-10-14', '2026-10-14']]
        assert not result.query_metadata['has_more']
        user.ha_permesso = lambda permission: False
        monkeypatch.setattr('web.services.email_mailbox_readonly.mailbox_reader', lambda *a, **k: pytest.fail('SQL prima del permesso'))
        denied = tools.query_pec_page(context, selection=selection)
        assert not denied.ok
        assert denied.blocked_reason == 'missing_permission'


@pytest.mark.parametrize('day', ['14 10 2026', '14/10/26', '14/10/2026', '14.10.2026', '14-10-2026', '14-10-26'])
def test_lex_service_date_to_authorized_sql_and_visible_answer(studies, monkeypatch, day):
    from lex.operational_knowledge.service import OperationalKnowledgeService
    from lex.operational_knowledge.tools import OperationalKnowledgeTools

    app, owners, databases, root = studies
    owner = owners[0]
    repository = EmailMailboxRepository(databases[0], owner.slug, 'pec')
    records = repository.load()
    records['one'].update(data='2026-10-14T12:00:00+02:00', cartella='INBOX', oggetto='Esito sintetico',
                          percorso_privato='D:/segreto', tenant_slug=owner.slug)
    repository.save(records, actor_key='controlled-user')
    tools = OperationalKnowledgeTools()
    monkeypatch.setattr(tools, '_manager', lambda *a, **k: pytest.fail('Dominio estraneo non richiesto'))
    monkeypatch.setattr(tools, '_email_manager', lambda *a, **k: pytest.fail('Catalogo MIME non richiesto'))
    user = SimpleNamespace(id='controlled-user', tenant_slug=owner.slug, ha_permesso=lambda permission: True)
    service = OperationalKnowledgeService(tools=tools)
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owner
        g.data_paths = {'EMAIL_CASELLA_DB': str(root / 'tenants' / owner.slug / 'email' / 'casella.json')}
        answer = service.answer(question=f'Mostrami le PEC ricevute il {day}', user=user, studio=owner)
        assert answer.route.intent == 'pec_query_page'
        assert '14 ottobre 2026' in answer.answer
        assert 'Esito sintetico' in answer.answer
        assert {source.source_id for source in answer.sources} == {'email_pec'}
        assert 'D:/segreto' not in str(answer.to_dict())
        assert answer.metadata['query_page']['ranges'] == [['2026-10-14', '2026-10-14']]


def test_service_paginazione_con_filtri_originali_e_senza_ripetizioni(studies):
    from lex.operational_knowledge.service import OperationalKnowledgeService
    from lex.operational_knowledge.settings import OperationalKnowledgeSettings

    app, owners, databases, root = studies
    app.secret_key = 'controlled-pagination-secret-only'
    owner = owners[0]
    repo = EmailMailboxRepository(databases[0], owner.slug, 'pec')
    records = repo.load()
    for key in ['one', 'two', 'three']:
        records[key] = {'id': key, 'data': '2026-10-14T12:00:00+02:00', 'cartella': 'INBOX', 'oggetto': key}
    repo.save(records, actor_key='controlled-user')
    user = SimpleNamespace(id='controlled-user', tenant_slug=owner.slug, ha_permesso=lambda permission: True)
    service = OperationalKnowledgeService(settings=OperationalKnowledgeSettings(max_results=1))
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owner
        g.data_paths = {'EMAIL_CASELLA_DB': str(root / 'tenants' / owner.slug / 'email' / 'casella.json')}
        answer = service.answer(question='PEC ricevute il 14/10/26', user=user, studio=owner)
        found = [answer.sources[0].object_id]
        first_token = answer.metadata['query_page']['continuation']
        while answer.metadata['query_page']['has_more']:
            token = answer.metadata['query_page']['continuation']
            answer = service.answer(question='Mostra altre PEC', user=user, studio=owner, metadata={'query_continuation': token})
            assert answer.metadata['query_page']['ranges'] == [['2026-10-14', '2026-10-14']]
            found.extend(source.object_id for source in answer.sources)
        assert set(found) == {'one', 'two', 'three'}
        assert len(found) == 3
        invalid = service.answer(question='PEC ricevute oggi', user=user, studio=owner,
                                 metadata={'query_continuation': first_token})
        assert invalid.blocked_reason
        assert not invalid.sources


def test_worker_riprende_solo_eventi_pendenti_degli_studi_senza_cataloghi(studies, monkeypatch):
    from web.services.mailbox_query_events_runtime import resume_mailbox_query_events

    app, owners, databases, _ = studies
    app.secret_key = 'controlled-worker-secret-only'
    databases[0].conn.execute('DELETE FROM email_mailbox_query_index WHERE tenant_key=?', (owners[0].slug,))
    databases[0].conn.commit()
    monkeypatch.setattr(EmailMailboxRepository, 'load', lambda *a, **k: pytest.fail('Caricamento intero non richiesto'))
    monkeypatch.setattr(EmailMailboxRepository, 'ensure_schema', lambda *a, **k: pytest.fail('Schema non richiesto nel worker'))
    monkeypatch.setattr(GestioneEmailRicevute, '__init__', lambda *a, **k: pytest.fail('MIME non richiesto'))
    result = resume_mailbox_query_events(app, limit=1)
    assert result == {'delivered': 1, 'failed': 0, 'not_migrated': 2}
    assert resume_mailbox_query_events(app, limit=1)['delivered'] == 0
    assert databases[0].conn.execute('SELECT COUNT(*) FROM email_mailbox_query_index WHERE tenant_key=?',
                                    (owners[0].slug,)).fetchone()[0] == 1


@pytest.mark.parametrize('streaming', [False, True])
def test_http_primary_query_does_not_build_global_context_or_load_ai(studies, streaming):
    from lex.orchestrator_http import build_context_response, chat_response

    app, owners, databases, root = studies
    owner = owners[0]
    # Fonte ricevuta dimostrata dalla cartella; la data originale resta assente.
    repository = EmailMailboxRepository(databases[0], owner.slug, 'pec')
    records = repository.load()
    records['one']['cartella'] = 'INBOX'
    repository.save(records, actor_key='controlled-user')
    user = SimpleNamespace(id='controlled-user', tenant_slug=owner.slug, ha_permesso=lambda permission: True)
    authorizations = []

    class ForbiddenDependencies:
        def __getattr__(self, name):
            pytest.fail('Dipendenza non richiesta: ' + name)

    orchestrator = SimpleNamespace(
        auth_guard=SimpleNamespace(ensure_can_access=lambda **kw: authorizations.append(kw)),
        dependencies=ForbiddenDependencies(),
    )
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owner
        g.data_paths = {'EMAIL_CASELLA_DB': str(root / 'tenants' / owner.slug / 'email' / 'casella.json')}
        arguments = dict(orchestrator=orchestrator, user=user, studio=owner, data={},
                         resolve_messages=lambda **kw: ('PEC ricevute il 14/10/26', '', []))
        if streaming:
            response = chat_response(**arguments, messages_with_effective_question=lambda **kw: pytest.fail('Prompt non richiesto'))
            payload = ''.join(response.response)
            assert '"payload"' in payload
            assert '[DONE]' in payload
            assert 'Nessuna corrispondenza tra le PEC con data e direzione verificate' in payload
            assert 'Resta 1 messaggio non attribuibile al periodo richiesto.' in payload
        else:
            payload, status = build_context_response(**arguments)
            assert status == 200
            assert 'Nessuna corrispondenza tra le PEC con data e direzione verificate' in payload['answer']
            assert 'Resta 1 messaggio non attribuibile al periodo richiesto.' in payload['answer']
        assert len(authorizations) == 1


@pytest.mark.parametrize('streaming', [False, True])
def test_http_notificazioni_non_avvia_pipeline_o_ai(studies, streaming):
    from lex.orchestrator_http import build_context_response, chat_response
    from pct.pec_notification_presidio import NotificationPresidioRepository, NotificationPresidioService
    from tests.test_pec_notification_presidio import _candidate

    app, owners, _, root = studies
    owner = owners[0]
    path = root / 'tenants' / owner.slug / 'email' / 'pec_audit.sqlite'
    repository = NotificationPresidioRepository(path, tenant_id=owner.slug)
    _candidate(NotificationPresidioService(repository), recipients=[{'name': 'Destinatario sintetico', 'role': 'controparte'}])
    repository.close()
    before = path.read_bytes()
    class ForbiddenDependencies:
        def __getattr__(self, name):
            pytest.fail('Dipendenza non richiesta: ' + name)
    user = SimpleNamespace(id='controlled-user', tenant_slug=owner.slug, ha_permesso=lambda permission: True)
    orchestrator = SimpleNamespace(auth_guard=SimpleNamespace(ensure_can_access=lambda **kw: None), dependencies=ForbiddenDependencies())
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owner
        g.data_paths = {'PEC_AUDIT_DB': str(path)}
        arguments = dict(orchestrator=orchestrator, user=user, studio=owner, data={},
                         resolve_messages=lambda **kw: ('notifiche da fare oggi', '', []))
        if streaming:
            response = chat_response(**arguments, messages_with_effective_question=lambda **kw: pytest.fail('Prompt non richiesto'))
            answer = ''.join(response.response)
        else:
            payload, status = build_context_response(**arguments)
            assert status == 200
            answer = payload['answer']
        assert 'Notificazioni legali' in answer
        assert 'Nessuna corrispondenza tra le notificazioni con data disponibile' in answer
    assert path.read_bytes() == before


@pytest.mark.parametrize('streaming', [False, True])
def test_http_agenda_filtra_udienze_senza_gestore_o_ai(studies, streaming):
    from lex.orchestrator_http import build_context_response, chat_response
    from pct.calendar_query_repository import CalendarQueryRepository
    from pct.calendar_query_schema import install_calendar_query_events

    app, owners, databases, root = studies
    owner, database = owners[0], databases[0]
    conn = database.conn
    install_calendar_query_events(conn)
    conn.execute('INSERT INTO calendar_query_owner VALUES (1,?,1)', (owner.slug,))
    conn.execute('INSERT INTO calendar_query_bootstrap VALUES (?,\'agenda\',1)', (owner.slug,))
    for key, kind in [('hearing', 'UDIENZA'), ('appointment', 'CONSULTAZIONE')]:
        conn.execute('INSERT INTO appuntamenti(id,titolo,tipo,stato,data_ora,durata_minuti,luogo) '
                     "VALUES (?,?,?,'PROGRAMMATO','2026-10-13T22:30:00Z',30,'Studio')", (key, 'Controllo ' + key, kind))
        CalendarQueryRepository(database, owner.slug).project_record(conn, domain='agenda', key=key,
            row=conn.execute('SELECT * FROM appuntamenti WHERE id=?', (key,)).fetchone())
    conn.execute("UPDATE transactional_outbox SET status='PROCESSED'")
    conn.commit()
    before = (root / 'tenants' / owner.slug / 'studio.db').read_bytes()
    class ForbiddenDependencies:
        def __getattr__(self, name):
            pytest.fail('Dipendenza non richiesta: ' + name)
    user = SimpleNamespace(id='controlled-user', tenant_slug=owner.slug, ha_permesso=lambda permission: True)
    orchestrator = SimpleNamespace(auth_guard=SimpleNamespace(ensure_can_access=lambda **kw: None), dependencies=ForbiddenDependencies())
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owner
        g.data_paths = {'AGENDA_DB': str(root / 'tenants' / owner.slug / 'agenda' / 'appuntamenti.json')}
        args = dict(orchestrator=orchestrator, user=user, studio=owner, data={},
                    resolve_messages=lambda **kw: ('udienze il 14/10/2026', '', []))
        if streaming:
            answer = ''.join(chat_response(**args, messages_with_effective_question=lambda **kw: pytest.fail('Prompt non richiesto')).response)
        else:
            payload, status = build_context_response(**args)
            assert status == 200
            answer = payload['answer']
        assert 'Controllo hearing' in answer
        assert '/agenda/hearing' in answer
        assert 'Controllo appointment' not in answer
    assert (root / 'tenants' / owner.slug / 'studio.db').read_bytes() == before


def test_worker_non_nasconde_un_errore_e_prosegue_sugli_altri_studi(studies, monkeypatch):
    from contextlib import contextmanager

    from web.services.email_mailbox_readonly import mailbox_projection_worker
    from web.services.mailbox_query_events_runtime import resume_mailbox_query_events

    app, owners, databases, _ = studies
    app.secret_key = 'controlled-worker-isolation-only'
    databases[1].conn.execute('DELETE FROM email_mailbox_query_index WHERE tenant_key=?', (owners[1].slug,))
    databases[1].conn.commit()

    @contextmanager
    def isolated(path, *, expected_tenant):
        if expected_tenant == owners[0].slug:
            raise RuntimeError('Guasto controllato')
        with mailbox_projection_worker(path, expected_tenant=expected_tenant) as repository:
            yield repository

    monkeypatch.setattr('web.services.email_mailbox_readonly.mailbox_projection_worker', isolated)
    result = resume_mailbox_query_events(app, limit=1)
    assert result['failed'] == 2
    assert result['delivered'] == 1


def test_migrazione_con_backup_nativo_riprende_il_cursore_senza_modificare_messaggi(studies, tmp_path):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / 'scripts/mailbox/rebuild-query-index.py'
    spec = importlib.util.spec_from_file_location('mailbox_query_migration_controlled', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, owners, databases, _ = studies
    repository = EmailMailboxRepository(databases[0], owners[0].slug, 'pec')
    records = repository.load()
    for key in ('two', 'three', 'four'):
        records[key] = {'id': key, 'cartella': 'INBOX', 'data': '2026-10-14T12:00:00+02:00'}
    repository.save(records, actor_key='controlled-user')
    destination = tmp_path / 'preserved-backup'
    first = module.rebuild(repository, destination=destination, limit=2, max_batches=1)
    assert first['phase'] == 'BACKFILL'
    assert first['processed_this_run'] == 2
    second = module.rebuild(repository, destination=destination, limit=2, max_batches=4)
    assert second['phase'] == 'COMPLETED'
    assert second['backup_sha256'] == first['backup_sha256']
    assert repository.load() == records
    manifest = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['backup']['quick_check'] == 'ok'
    assert (destination / 'studio.db').is_file()


def test_worker_calendario_consegna_solo_evento_del_record_modificato(studies, tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    from pct.calendar_query_repository import CalendarQueryRepository
    from web.services.calendar_query_events_runtime import resume_calendar_query_events

    spec = importlib.util.spec_from_file_location('calendar_query_worker_controlled', Path(__file__).resolve().parents[1] / 'scripts/calendar-query-index.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app, owners, databases, _ = studies
    app.secret_key = 'controlled-calendar-worker-secret'
    owner, database = owners[0], databases[0]
    database.conn.execute('INSERT INTO appuntamenti(id,titolo,tipo,stato,data_ora,durata_minuti,luogo) '
                          "VALUES ('one','Controllato','UDIENZA','PROGRAMMATO','2026-10-14T10:00:00',30,'Studio')")
    database.conn.commit()
    assert module.rebuild(database, tenant=owner.slug, destination=tmp_path / 'calendar-worker-backup', domain='agenda')['phase'] == 'COMPLETED'
    database.conn.execute("UPDATE appuntamenti SET titolo='Aggiornato' WHERE id='one'")
    database.conn.commit()
    monkeypatch.setattr('pct.agenda.Agenda.__init__', lambda *a, **kw: pytest.fail('Gestore Agenda non richiesto'))
    monkeypatch.setattr('pct.scadenziario.GestioneScadenziario.__init__', lambda *a, **kw: pytest.fail('Gestore Scadenziario non richiesto'))
    result = resume_calendar_query_events(app, limit=1)
    assert result == dict(delivered=1, failed=0, not_migrated=3)
    assert resume_calendar_query_events(app, limit=1)['delivered'] == 0
    assert CalendarQueryRepository(database, owner.slug).list_page(domain='agenda')['rows'][0]['titolo'] == 'Aggiornato'


def test_migrazione_calendario_backup_reale_e_ripresa_senza_modificare_fonti(studies, tmp_path):
    import importlib.util
    from pathlib import Path

    from pct.calendar_query_repository import CalendarQueryNotReady, CalendarQueryRepository

    path = Path(__file__).resolve().parents[1] / 'scripts/calendar-query-index.py'
    spec = importlib.util.spec_from_file_location('calendar_query_migration_controlled', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, owners, databases, _ = studies
    database, owner = databases[0], owners[0]
    for key in ('one', 'two', 'three'):
        database.conn.execute('INSERT INTO appuntamenti(id,titolo,tipo,stato,data_ora,durata_minuti,luogo) '
                              "VALUES (?,?,'UDIENZA','PROGRAMMATO','2026-10-14T10:00:00',30,'Studio')", (key, key))
    database.conn.commit()
    before = [dict(row) for row in database.conn.execute('SELECT * FROM appuntamenti ORDER BY id').fetchall()]
    destination = tmp_path / 'preserved-calendar-backup'
    first = module.rebuild(database, tenant=owner.slug, destination=destination, domain='agenda', limit=1, max_batches=1)
    assert first['phase'] == 'BACKFILL'
    with pytest.raises(CalendarQueryNotReady):
        CalendarQueryRepository(database, owner.slug).list_page(domain='agenda')
    resumed = module.rebuild(database, tenant=owner.slug, destination=destination, domain='agenda', limit=1, max_batches=4)
    assert resumed['phase'] == 'COMPLETED'
    assert resumed['backup_sha256'] == first['backup_sha256']
    assert len(CalendarQueryRepository(database, owner.slug).list_page(domain='agenda')['rows']) == 3
    assert [dict(row) for row in database.conn.execute('SELECT * FROM appuntamenti ORDER BY id').fetchall()] == before
    manifest = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['backup']['quick_check'] == 'ok'
