"""Retry persistenti: attesa, arresto finito e ripresa per un nuovo evento."""
import pytest

from tests.test_receipt_sources_consultation import registry as registry


@pytest.fixture
def clock(monkeypatch):
    now = ['2026-10-20T00:00:00Z']
    monkeypatch.setattr('pct.registro_letture.repository._adesso', lambda: now[0])
    return now


def test_failure_waits_and_stops_after_three_attempts(registry, clock):
    registry.accoda_evento('study-a', 'case-a', forza=True, presidi=True)
    for attempt in range(1, 4):
        event = registry.reclama_evento('study-a', 'case-a', 'worker-' + str(attempt))
        assert event == {'generation': 1, 'forza': True, 'presidi': True}
        pending = registry.concludi_evento('study-a', 'case-a', 'worker-' + str(attempt), 1,
            riuscito=False, errore='Schema documentale non preparato', codice_errore='DocumentAISchemaNotPrepared')
        state = registry.esito_evento('study-a', 'case-a')
        assert state['attempts'] == attempt and state['last_error'] == 'Schema documentale non preparato'
        assert registry.reclama_evento('study-a', 'case-a', 'too-early') is None
        assert registry.eventi_da_riprendere('study-a') == []
        assert registry.esito_evento('other-study', 'case-a')['stato'] == 'idle'
        if attempt < 3:
            assert pending and state['stato'] == 'pending' and state['available_at'] > clock[0]
            clock[0] = state['available_at']
        else:
            assert not pending and state['stato'] == 'failed'
            clock[0] = '2026-10-21T00:00:00Z'
            assert registry.eventi_da_riprendere('study-a') == []
    registry.accoda_evento('study-a', 'case-a')
    state = registry.esito_evento('study-a', 'case-a')
    assert state['attempts'] == 0 and state['last_error'] == ''
    event = registry.reclama_evento('study-a', 'case-a', 'new-source')
    assert event['generation'] == 2
    assert not registry.concludi_evento('study-a', 'case-a', 'new-source', 2)
    assert registry.esito_evento('study-a', 'case-a')['stato'] == 'idle'


def test_new_generation_is_not_delayed_by_old_failed_work(registry, clock):
    registry.accoda_evento('study-a', 'case-a')
    registry.reclama_evento('study-a', 'case-a', 'worker-old')
    registry.accoda_evento('study-a', 'case-a', presidi=True)
    assert registry.concludi_evento('study-a', 'case-a', 'worker-old', 1, riuscito=False, errore='Errore vecchio')
    event = registry.reclama_evento('study-a', 'case-a', 'worker-new')
    assert event == {'generation': 2, 'forza': False, 'presidi': True}
    state = registry.esito_evento('study-a', 'case-a')
    assert state['attempts'] == 1 and state['last_error'] == ''


def _scade(registry, case='case-a'):
    with registry.connection() as conn:
        conn.execute("UPDATE letture_eventi SET lease_until=? WHERE tenant_id=? AND fascicolo_id=?",
                     ('2000-01-01T00:00:00Z', 'study-a', case))


def test_expired_leases_have_a_finite_budget_and_preserve_the_cause(registry, clock):
    """Le prime MAX_INTERRUZIONI scadenze (riavvii) non contano; oltre, tre scadenze senza avanzamento sospendono."""
    from pct.registro_letture.event_retry import ERRORE_SOSPESA, MAX_INTERRUZIONI
    registry.accoda_evento('study-a', 'case-a')
    for claim in range(1, MAX_INTERRUZIONI + 4):
        assert registry.reclama_evento('study-a', 'case-a', 'worker-' + str(claim)), claim
        _scade(registry)
    assert registry.reclama_evento('study-a', 'case-a', 'one-too-many') is None
    state = registry.esito_evento('study-a', 'case-a')
    assert state['stato'] == 'failed' and state['attempts'] == 3 and state['last_error'] == ERRORE_SOSPESA
    with registry.connection() as conn:
        assert conn.execute("SELECT count(*) FROM letture_eventi_esiti WHERE fascicolo_id='case-a' AND stato='expired'").fetchone()[0] == MAX_INTERRUZIONI + 3


def test_lease_expired_by_restart_is_not_a_failed_attempt(registry, clock):
    """Deploy o memoria esaurita: la prenotazione scade, ma il tentativo non è fallito."""
    registry.accoda_evento('study-a', 'case-a')
    for claim in range(1, 4):
        assert registry.reclama_evento('study-a', 'case-a', 'worker-' + str(claim))
        assert registry.esito_evento('study-a', 'case-a')['attempts'] == 1
        _scade(registry)  # il processo è stato riavviato: nessuno conclude la prenotazione
    event = registry.reclama_evento('study-a', 'case-a', 'after-deploy')
    assert event == {'generation': 1, 'forza': False}
    state = registry.esito_evento('study-a', 'case-a')
    assert state['stato'] == 'running' and state['attempts'] == 1 and state['last_error'] == ''
    assert registry.concludi_evento('study-a', 'case-a', 'after-deploy', 1) is False
    assert registry.esito_evento('study-a', 'case-a')['stato'] == 'idle'
    with registry.connection() as conn:
        progressivi = [r[0] for r in conn.execute("SELECT attempt FROM letture_eventi_esiti WHERE fascicolo_id='case-a' ORDER BY attempt").fetchall()]
    assert progressivi == [1, 2, 3, 4]


def test_progress_renews_lease_and_restores_budget(registry, clock):
    registry.accoda_evento('study-a', 'case-a')
    registry.reclama_evento('study-a', 'case-a', 'worker')
    with registry.connection() as conn:
        conn.execute("UPDATE letture_eventi SET attempts=2 WHERE fascicolo_id='case-a'")
    clock[0] = '2026-10-20T00:20:00Z'
    assert registry.rinnova_evento('study-a', 'case-a', 'worker', 1, progresso=True)
    state = registry.esito_evento('study-a', 'case-a')
    assert state['attempts'] == 0
    with registry.connection() as conn:
        assert conn.execute("SELECT lease_until FROM letture_eventi WHERE fascicolo_id='case-a'").fetchone()[0] == '2026-10-20T00:50:00Z'
    assert not registry.rinnova_evento('study-a', 'case-a', 'another-worker', 1)


def test_suspended_turn_requeues_without_error_and_keeps_presidi(registry, clock):
    registry.accoda_evento('study-a', 'case-a', presidi=True)
    assert registry.reclama_evento('study-a', 'case-a', 'worker') == {'generation': 1, 'forza': False, 'presidi': True}
    assert registry.sospendi_evento('study-a', 'case-a', 'worker', 1)
    state = registry.esito_evento('study-a', 'case-a')
    assert state['stato'] == 'pending' and state['attempts'] == 0 and state['last_error'] == '' and state['available_at'] == ''
    assert [e['fascicolo_id'] for e in registry.eventi_da_riprendere('study-a')] == ['case-a']
    assert registry.reclama_evento('study-a', 'case-a', 'next-turn') == {'generation': 1, 'forza': False, 'presidi': True}
    assert not registry.sospendi_evento('study-a', 'case-a', 'worker', 1)


def test_stuck_legacy_timeouts_are_requeued_in_batches_idempotently(registry, clock):
    """Riconvalida: i fascicoli fermi con il vecchio «tempo esaurito» ripartono, a lotti e una volta sola."""
    from pct.registro_letture.event_retry import ERRORE_TEMPO_STORICO
    for case in ('old-1', 'old-2', 'old-3', 'real-error'):
        registry.accoda_evento('study-a', case, presidi=True)
        registry.reclama_evento('study-a', case, 'worker')
    with registry.connection() as conn:
        # Come scriveva la 2.476.0 al terzo riavvio: presìdi richiesti conservati, errore storico.
        conn.execute("UPDATE letture_eventi SET stato='idle',worker_id='',lease_until='',attempts=3,last_error=?,"
                     "pending_presidi=claimed_presidi,claimed_presidi=0,"
                     "last_error_code='LeaseExpired' WHERE fascicolo_id LIKE 'old-%'", (ERRORE_TEMPO_STORICO,))
    registry.concludi_evento('study-a', 'real-error', 'worker', 1, riuscito=False, errore='Causa vera')
    with registry.connection() as conn:
        conn.execute("UPDATE letture_eventi SET stato='idle',available_at='',attempts=3 WHERE fascicolo_id='real-error'")
    primo = registry.riprendi_letture_ferme('study-a', limite=2, solo_tempo_esaurito=True)
    secondo = registry.riprendi_letture_ferme('study-a', limite=2, solo_tempo_esaurito=True)
    assert len(primo) == 2 and len(secondo) == 1 and not set(primo) & set(secondo)
    assert registry.riprendi_letture_ferme('study-a', limite=2, solo_tempo_esaurito=True) == []
    for case in ('old-1', 'old-2', 'old-3'):
        state = registry.esito_evento('study-a', case)
        assert state['stato'] == 'pending' and state['attempts'] == 0 and state['generation'] == 2 and not state['last_error']
    assert registry.esito_evento('study-a', 'real-error')['stato'] == 'failed'
    assert registry.reclama_evento('study-a', 'old-1', 'w')['presidi']
    # La ripresa notturna prende anche gli altri fermi, ma solo se fermi da abbastanza tempo.
    assert registry.riprendi_letture_ferme('study-a', ferme_da_secondi=6 * 3600) == []
    clock[0] = '2026-10-20T07:00:00Z'
    assert registry.riprendi_letture_ferme('study-a', ferme_da_secondi=6 * 3600) == ['real-error']
    assert registry.riprendi_letture_ferme('study-a', ferme_da_secondi=6 * 3600) == []


def test_preparation_recovery_is_targeted_idempotent_and_retains_history(registry, clock):
    from pct.registro_letture.event_retry import recover_prepared_schema_failures
    from web.services.fascicoli_list_events_runtime import registry_outbox_writer
    for tenant, case, code in [('study-a','schema','DocumentAISchemaNotPrepared'),
                               ('study-a','other','IOError'),
                               ('study-b','schema','DocumentAISchemaNotPrepared')]:
        registry.accoda_evento(tenant,case)
        registry.reclama_evento(tenant,case,'worker')
        registry.concludi_evento(tenant,case,'worker',1,riuscito=False,errore='Causa conservata',codice_errore=code)
    with registry_outbox_writer(registry) as conn:
        assert len(recover_prepared_schema_failures(conn,'study-a',clock[0])) == 1
        assert recover_prepared_schema_failures(conn,'study-a',clock[0]) == []
        conn.commit()
    assert registry.esito_evento('study-a','schema')['generation'] == 2
    assert registry.esito_evento('study-a','other')['generation'] == 1
    assert registry.esito_evento('study-b','schema')['generation'] == 1
    with registry.connection() as conn:
        rows = conn.execute("SELECT errore FROM letture_eventi_esiti WHERE tenant_id=? AND fascicolo_id=?",
                            ('study-a','schema')).fetchall()
    assert [row[0] for row in rows] == ['Causa conservata']


def test_legacy_schema_requires_explicit_preparation_and_preserves_pending(registry):
    from pct.registro_letture.event_retry import FIELDS, ReadingEventSchemaNotPrepared, install, require_prepared
    with registry.connection() as conn:
        conn.execute('DROP TABLE letture_eventi_esiti')
        for field in FIELDS:
            conn.execute(f'ALTER TABLE letture_eventi DROP COLUMN {field}')
        conn.execute("INSERT INTO letture_eventi(id,tenant_id,fascicolo_id,generation,stato,pending_force,pending_presidi,creato_il,aggiornato_il) VALUES (?,?,?,1,'pending',1,1,?,?)", ('legacy','study-a','retained','2026-10-20T00:00:00Z','2026-10-20T00:00:00Z'))
    with registry.connection() as conn:
        with pytest.raises(ReadingEventSchemaNotPrepared):
            require_prepared(conn,postgres=registry.backend_kind=='postgres')
        before = dict(conn.execute('SELECT * FROM letture_eventi').fetchone())
        assert install(conn,postgres=registry.backend_kind=='postgres')
        assert not install(conn,postgres=registry.backend_kind=='postgres')
        after = dict(conn.execute('SELECT * FROM letture_eventi').fetchone())
        assert all(after[key] == value for key,value in before.items())
        require_prepared(conn,postgres=registry.backend_kind=='postgres')
    registry._event_retry_prepared = False
    assert registry.reclama_evento('study-a','retained','worker') == dict(generation=1,forza=True,presidi=True)


def test_queue_preparation_backs_up_legacy_sqlite_before_ddl(tmp_path):
    import hashlib
    import json
    import sqlite3

    from pct.registro_letture import RegistroLetture
    from pct.registro_letture.event_retry import FIELDS, columns
    from tools.prepare_reading_runtime import prepare_queue
    path = tmp_path / 'legacy.db'
    original = RegistroLetture(path)
    with original.connection() as conn:
        conn.execute('DROP TABLE letture_eventi_esiti')
        for field in FIELDS:
            conn.execute(f'ALTER TABLE letture_eventi DROP COLUMN {field}')
    original.close()
    readonly = RegistroLetture(path,read_only=True)
    destination = tmp_path / 'verified-backup'
    assert prepare_queue(readonly,'study-a',destination)
    assert not prepare_queue(readonly,'study-a',destination)
    manifest = json.loads((destination/'manifest.json').read_text())
    snapshot = destination/'studio.db'
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == manifest['backup']['sha256']
    with sqlite3.connect(snapshot) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not set(FIELDS).intersection(columns(conn))
    with readonly.connection() as conn:
        assert set(FIELDS).issubset(columns(conn))
    readonly.close()


def test_explicit_recovery_does_not_restart_pending_running_or_completed_delivery(registry):
    state=registry.richiedi_recupero('study-a','case-a',generation=0)
    assert state['generation']==1 and state['stato']=='pending'
    assert registry.richiedi_recupero('study-a','case-a',generation=0)['generation']==1
    event=registry.reclama_evento('study-a','case-a','worker')
    assert registry.richiedi_recupero('study-a','case-a',generation=1)['attempts']==1
    registry.concludi_evento('study-a','case-a','worker',event['generation'])
    assert registry.richiedi_recupero('study-a','case-a',generation=0)['stato']=='idle'
    assert registry.esito_evento('study-a','case-a')['generation']==1
    assert registry.richiedi_recupero('study-a','case-a',generation=1)['generation']==2
    assert registry.esito_evento('study-b','case-a')['generation']==0
    assert registry.richiedi_recupero('study-a','missing',generation=99)['generation']==0


def test_explicit_recovery_after_failure_preserves_history_and_deduplicates_retry(registry,clock):
    registry.accoda_evento('study-a','case-a',presidi=True)
    for _attempt in range(3):
        event=registry.reclama_evento('study-a','case-a','worker')
        registry.concludi_evento('study-a','case-a','worker',event['generation'],riuscito=False,errore='Causa conservata')
        clock[0]=registry.esito_evento('study-a','case-a')['available_at'] or clock[0]
    assert registry.esito_evento('study-a','case-a')['stato']=='failed'
    assert registry.richiedi_recupero('study-a','case-a',generation=0)['stato']=='failed'
    assert registry.richiedi_recupero('study-a','case-a',generation=1)['generation']==2
    assert registry.richiedi_recupero('study-a','case-a',generation=1)['generation']==2
    assert registry.reclama_evento('study-a','case-a','new-worker')['presidi']
    with registry.connection() as conn:
        assert conn.execute("SELECT count(*) FROM letture_eventi_esiti WHERE errore='Causa conservata'").fetchone()[0]==3


def test_concurrent_recovery_delivery_creates_only_one_generation(registry):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    registry.accoda_evento('study-a','schema-seed')
    barrier=Barrier(2)
    def send():
        barrier.wait(timeout=10)
        return registry.richiedi_recupero('study-a','concurrent',generation=0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _: send(), range(2)))
    assert [item['generation'] for item in results]==[1,1]
    assert registry.esito_evento('study-a','concurrent')['attempts']==0
