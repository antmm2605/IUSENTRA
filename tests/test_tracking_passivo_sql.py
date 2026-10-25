"""Conferma ripetuta e rollback della proposta con la voce Timesheet nativa."""
import pytest

from pct.tracking_passivo_sql import SCHEMA, TrackingPassivoSQL
from pct.timesheet_sql_writer import TimesheetConflict
pytest_plugins = ("tests.test_timesheet_sql_concurrency",)


@pytest.fixture
def proposal(managers):
    db, open_manager, _, _ = managers
    for statement in SCHEMA.split(';'):
        if statement.strip():
            db.conn.execute(statement)
    db.conn.execute("INSERT INTO fascicoli (id) VALUES (?)", ('case',))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    repo = TrackingPassivoSQL(db)
    row = dict(id='proposal', chiave='user|case|2026-10-17T10:00', stato='BOZZA',
               utente_id='user', fascicolo_id='case', inizio='2026-10-17T10:00:00',
               fine='2026-10-17T10:12:00', minuti=12, descrizione='Attività controllata')
    repo.insert([row])
    return repo, open_manager, row


def test_due_conferme_ritrovano_una_sola_voce(proposal):
    repo, open_manager, row = proposal
    left, right = open_manager(), open_manager()
    first = repo.transition(row['id'], actor_id='user', timesheet=left,
                            create=lambda data: left.crea(**data))
    second = repo.transition(row['id'], actor_id='user', timesheet=right,
                             create=lambda data: right.crea(**data))
    assert first['voce_timesheet_id'] == second['voce_timesheet_id']
    assert not first['gia_presente'] and second['gia_presente']
    assert len(open_manager().tutte()) == 3


def test_due_connessioni_concorrenti_confermano_una_sola_volta(proposal, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from pct.timesheet import GestioneTimesheet
    repo, open_manager, row = proposal
    barrier = Barrier(2)
    def confirm():
        peer = repo.database.open_peer()
        manager = GestioneTimesheet(str(tmp_path / 'unused.json'), studio_db=peer)
        try:
            barrier.wait(timeout=5)
            return TrackingPassivoSQL(peer).transition(row['id'], actor_id='user', timesheet=manager,
                create=lambda data: manager.crea(**data))
        finally:
            if hasattr(peer, 'chiudi'):
                peer.chiudi()
            else:
                peer.raw_conn.close()
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: confirm(), range(2)))
    assert len({result['voce_timesheet_id'] for result in results}) == 1
    assert sorted(result['gia_presente'] for result in results) == [False, True]
    assert len(open_manager().tutte()) == 3


def test_errore_dopo_creazione_non_lascia_voce_ne_conferma(proposal):
    repo, open_manager, row = proposal
    manager = open_manager()
    def fail(data):
        manager.crea(**data)
        raise ValueError('Errore controllato dopo la voce')
    with pytest.raises(ValueError, match='Errore controllato'):
        repo.transition(row['id'], actor_id='user', timesheet=manager, create=fail)
    assert repo.get(row['id'])['stato'] == 'BOZZA'
    assert len(manager.tutte()) == len(open_manager().tutte()) == 2


def test_scarto_non_puo_sovrascrivere_conferma(proposal):
    repo, open_manager, row = proposal
    manager = open_manager()
    repo.transition(row['id'], actor_id='user', timesheet=manager,
                     create=lambda data: manager.crea(**data))
    with pytest.raises(TimesheetConflict):
        repo.transition(row['id'], actor_id='user', reason='Snapshot superato')
    assert repo.get(row['id'])['stato'] == 'CONFERMATA'


def test_altro_utente_non_puo_confermare_o_scartare(proposal):
    repo, open_manager, row = proposal
    manager = open_manager()
    with pytest.raises(KeyError):
        repo.transition(row['id'], actor_id='altro', timesheet=manager,
                         create=lambda data: manager.crea(**data))
    with pytest.raises(KeyError):
        repo.transition(row['id'], actor_id='altro', reason='Non autorizzato')
    assert repo.get(row['id'])['stato'] == 'BOZZA'


def test_scarto_ripetuto_non_ripropone_la_sessione(proposal):
    repo, _, row = proposal
    assert not repo.transition(row['id'], actor_id='user', reason='Non lavorata')['gia_presente']
    assert repo.transition(row['id'], actor_id='user', reason='Non lavorata')['gia_presente']
    assert repo.insert([dict(row, id='altro-id')]) == []
    assert repo.bozze(utente_id='user') == []


def test_conferma_ripetuta_non_cambia_la_durata_gia_registrata(proposal):
    repo, open_manager, row = proposal
    manager = open_manager()
    first = repo.transition(row['id'], actor_id='user', timesheet=manager,
                             create=lambda data: manager.crea(**data))
    with pytest.raises(TimesheetConflict, match='durata differente'):
        repo.transition(row['id'], actor_id='user', timesheet=manager, minutes=99,
                         create=lambda data: manager.crea(**data))
    assert open_manager().get(first['voce_timesheet_id']).minuti == 12


def test_collegamento_mancante_non_viene_ricreato_automaticamente(proposal):
    repo, open_manager, row = proposal
    manager = open_manager()
    first = repo.transition(row['id'], actor_id='user', timesheet=manager,
                             create=lambda data: manager.crea(**data))
    repo.database.conn.execute('DELETE FROM timesheet_entries WHERE id=?', (first['voce_timesheet_id'],))
    (getattr(repo.database, 'raw_conn', None) or repo.database.conn).commit()
    with pytest.raises(TimesheetConflict, match='non reperibile'):
        repo.transition(row['id'], actor_id='user', timesheet=manager,
                         create=lambda data: manager.crea(**data))
    assert len(open_manager().tutte()) == 2


def test_callback_senza_voce_persistita_non_conferma(proposal):
    repo, open_manager, row = proposal
    with pytest.raises(ValueError, match='non dimostra'):
        repo.transition(row['id'], actor_id='user', timesheet=open_manager(),
                         create=lambda data: {'id': 'inesistente'})
    assert repo.get(row['id'])['stato'] == 'BOZZA'


def test_audit_recente_paginato_non_perde_timestamp_uguali(proposal):
    repo, _, _ = proposal
    columns = ('id', 'timestamp', 'id_utente', 'username', 'azione', 'risorsa_tipo', 'risorsa_id', 'dettagli', 'ip', 'esito')
    repo.database.conn.execute('CREATE TABLE IF NOT EXISTS audit_log (' +
        ','.join(name + ' TEXT' + (' PRIMARY KEY' if name == 'id' else '') for name in columns) + ')')
    for key in range(7):
        repo.database.conn.execute('INSERT INTO audit_log (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')',
            (str(key), '2026-10-17T10:00:00', 'user', 'avvocato', 'fascicoli.apri', 'fascicolo', 'case', '', '', 'OK'))
    (getattr(repo.database, 'raw_conn', None) or repo.database.conn).commit()
    events = list(repo.recent_events('2026-10-17T09:00:00', '2026-10-17T11:00:00', batch_size=2))
    assert [event.id for event in events] == [str(i) for i in range(7)]
    assert list(repo.recent_events('2026-10-17T10:01:00', '2026-10-17T11:00:00', batch_size=2)) == []


def test_produttore_normale_usa_sql_senza_leggere_o_scrivere_json(proposal, tmp_path):
    from types import SimpleNamespace
    from pct.time_tracking_passivo import GestioneTrackingPassivo
    repo, _, _ = proposal
    source = tmp_path / 'archivio' / 'tracking_passivo.json'
    events = [SimpleNamespace(timestamp=f'2026-10-17T11:{minute}:00', azione='fascicoli.apri',
        risorsa_tipo='fascicolo', risorsa_id='case', id_utente='user', username='avvocato', esito='OK')
        for minute in ('00', '10')]
    producer = GestioneTrackingPassivo(str(source), studio_db=repo.database)
    created = producer.genera_da_eventi(iter(events))
    assert len(created) == 1
    assert not source.parent.exists()
    assert producer.genera_da_eventi(iter(events)) == []
    producer.scarta(created[0]['id'], actor_id='user', motivo='Valutazione professionale')
    assert producer.genera_da_eventi(iter(events)) == []
    assert repo.get(created[0]['id'])['stato'] == 'SCARTATA'
    assert len(repo.bozze(utente_id='user')) == 1
    assert repo.bozze(utente_id='altro') == []


def test_scheduler_risolve_il_proprietario_senza_creare_baseline_json(proposal, tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from flask import Flask
    from pct.scheduler import start_scheduler
    from pct.tenant import DatabaseConfig, StatoTenant
    import pct.tenant
    import pct.core_storage_backend
    repo, _, _ = proposal
    database_config = DatabaseConfig(mode='SQLITE')
    resolved = []
    class Registry:
        def __init__(self, **kwargs):
            pass
        def lista(self):
            return [SimpleNamespace(slug='owner', stato=StatoTenant.ATTIVO, database=database_config, id='owner')]
        def percorsi_dati(self, slug, **kwargs):
            assert kwargs == dict(reconcile_aliases=False, ensure_baseline=False)
            resolved.append(slug)
            return dict(STUDIO_DB=str(tmp_path / 'owner.db'), TIMESHEET_DB=str(tmp_path / 'no-json' / 'entries.json'))
    def backend(config, **kwargs):
        assert config is database_config
        assert kwargs['initialize_schema'] is False
        return repo.database
    now = datetime.now()
    events = [SimpleNamespace(timestamp=(now - timedelta(minutes=minute)).isoformat(), azione='fascicoli.apri',
        risorsa_tipo='fascicolo', risorsa_id='case', id_utente='user', username='avvocato', esito='OK') for minute in (10, 0)]
    monkeypatch.setattr(pct.tenant, 'GestioneTenant', Registry)
    monkeypatch.setattr(pct.core_storage_backend, 'build_core_storage_backend', backend)
    monkeypatch.setattr(TrackingPassivoSQL, 'recent_events', lambda *a, **kw: iter(events))
    monkeypatch.setattr(repo.database, 'chiudi', lambda: None, raising=False)
    monkeypatch.delenv('PCT_SCHEDULER_RUNNING', raising=False)
    app = Flask(__name__)
    app.config.update(SECRET_KEY='controlled', BACKUP_ORA='02:00', WA_REMINDER_ORA='18:00',
        PCT_SCHEDULER_WORKER=True, MULTI_TENANT=True, TENANTS_REGISTRY=str(tmp_path / 'registry.json'),
        SCHEDULER_REGISTRY_DB=str(tmp_path / 'jobs.db'), FEATURE_FLAGS={'lex.dailyPlan.scheduledRuns': False})
    # Il contratto qui e il job richiamato esplicitamente, non gli altri timer.
    # Avviarli introdurrebbe letture concorrenti del Registry fittizio, specie
    # nell'ora ripetuta del cambio all'ora solare.
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.schedulers.base import STATE_PAUSED

    original_start = BackgroundScheduler.start
    monkeypatch.setattr(BackgroundScheduler, 'start', lambda self: original_start(self, paused=True))
    scheduler = start_scheduler(app)
    assert scheduler.state == STATE_PAUSED
    try:
        scheduler.get_job('time_tracking_passivo').func()
        assert resolved == ['owner']
        assert len(repo.bozze(utente_id='user')) == 2
        assert not (tmp_path / 'no-json').exists()
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv('PCT_SCHEDULER_RUNNING', raising=False)


def test_conferma_autorizzata_per_operatore_conserva_autore_e_confermatore(proposal):
    repo, open_manager, row = proposal
    manager = open_manager()
    result = repo.transition(row['id'], actor_id='responsabile', owner_id='user',
                            timesheet=manager, create=lambda data: manager.crea(**data))
    entry = open_manager().get(result['voce_timesheet_id'])
    assert entry.id_utente == 'user'
    assert repo.get(row['id'])['definito_da'] == 'responsabile'
