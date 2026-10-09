"""Guardrail su archivi controllati: non accettazione sullo studio reale."""
import hashlib
import os
import sqlite3
from types import SimpleNamespace

import pytest

from pct.prima_nota import GestionePrimaNota, MovimentoPrimaNota
from pct.prima_nota_repository import PrimaNotaConflict, PrimaNotaRepository, validate_legacy_payload


@pytest.fixture
def database(tmp_path):
    connections = []
    def connect():
        if os.environ.get('PRIMA_NOTA_TEST_POSTGRES') == '1':
            import psycopg2
            from pct.storage_postgres import PostgresCompatConnection
            raw = psycopg2.connect(
                host=os.environ.get('PRIMA_NOTA_TEST_PG_HOST', 'audit-postgres'),
                dbname=os.environ.get('AUDIT_POSTGRES_DB', 'iusentra_audit'),
                user=os.environ.get('AUDIT_POSTGRES_USER', 'iusentra_audit'),
                password=os.environ['AUDIT_POSTGRES_PASSWORD'],
            )
            # Tabelle temporanee isolate da tutti i dati applicativi; stessa connessione.
            db = SimpleNamespace(raw_conn=raw)
            db.conn = PostgresCompatConnection(db)
        else:
            raw = sqlite3.connect(tmp_path / 'controlled.db')
            db = SimpleNamespace(conn=raw)
        connections.append(raw)
        return db
    db = connect()
    repo = PrimaNotaRepository(db, 'studio-test')
    if os.environ.get('PRIMA_NOTA_TEST_POSTGRES') == '1':
        from pct.prima_nota_repository import DDL
        for statement in DDL:
            db.conn.execute(statement.replace('CREATE TABLE IF NOT EXISTS', 'CREATE TEMP TABLE'))
        from pct.transactional_outbox import SQLITE_SCHEMA
        statement = SQLITE_SCHEMA.split(';')[0].replace('CREATE TABLE IF NOT EXISTS', 'CREATE TEMP TABLE')
        db.conn.execute(statement)
        db.raw_conn.commit()
    else:
        repo.ensure_schema()
    db.conn.execute(('CREATE TEMP TABLE' if hasattr(db, 'raw_conn') else 'CREATE TABLE') + ' audit_log ('
                    'id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,azione TEXT,'
                    'risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)')
    PrimaNotaRepository(db,'studio-test')._finish(db.conn)
    yield db
    for connection in connections:
        connection.close()


def initialized(db, tenant='studio-test', payload=None):
    repo = PrimaNotaRepository(db, tenant, actor_key='attore-test')
    repo.initialize(payload or {}, source_sha256=hashlib.sha256(b'controlled').hexdigest(), backup_reference='controlled-test-backup')
    return repo


@pytest.mark.skipif(os.environ.get('PRIMA_NOTA_TEST_POSTGRES') != '1', reason='Richiede PostgreSQL nativo controllato')
def test_riscontro_adozione_postgres_sola_lettura(database):
    from web.services.prima_nota_runtime import _read_adoption
    initialized(database)
    database.raw_conn.rollback()
    database.raw_conn.set_session(readonly=True)
    try:
        state = _read_adoption(database.raw_conn, 'studio-test', postgres=True)
        assert state == (hashlib.sha256(b'controlled').hexdigest(), 'controlled-test-backup')
        assert _read_adoption(database.raw_conn, 'altro-studio', postgres=True) is None
        with database.raw_conn.cursor() as cursor:
            cursor.execute('SHOW transaction_read_only')
            assert cursor.fetchone()[0] == 'on'
    finally:
        database.raw_conn.rollback()
        database.raw_conn.set_session(readonly=False)


@pytest.mark.skipif(os.environ.get('PRIMA_NOTA_TEST_POSTGRES') != '1', reason='Richiede PostgreSQL nativo controllato')
def test_backend_postgres_esistente_non_esegue_ddl(database, tmp_path, monkeypatch):
    import uuid
    from psycopg2.extensions import make_dsn
    from pct.storage_postgres import PostgresStudioDB
    schema = 'test_existing_prima_nota_' + uuid.uuid4().hex
    database.conn.execute(f'CREATE SCHEMA "{schema}"')
    database.conn.execute(f'SET search_path TO "{schema}", pg_catalog')
    database.raw_conn.commit()
    backend = None
    try:
        dsn = make_dsn(host=os.environ.get('PRIMA_NOTA_TEST_PG_HOST', 'audit-postgres'),
                       dbname=os.environ.get('AUDIT_POSTGRES_DB', 'iusentra_audit'),
                       user=os.environ.get('AUDIT_POSTGRES_USER', 'iusentra_audit'),
                       password=os.environ['AUDIT_POSTGRES_PASSWORD'],
                       options=f'-csearch_path={schema},pg_catalog')
        backend = PostgresStudioDB(dsn, initialize_schema=False)
        repo = PrimaNotaRepository(backend, 'studio-test')
        repo.ensure_schema()
        from pct.operational_live import ensure_live_schema
        backend.conn.execute('CREATE TABLE _meta (chiave TEXT PRIMARY KEY, valore TEXT)')
        ensure_live_schema(backend.conn, postgres=True)
        initialized(backend)
        backend.chiudi()
        monkeypatch.setattr(PostgresStudioDB, '_ensure_schema', lambda _: pytest.fail('Nessun DDL nella richiesta'))
        backend = PostgresStudioDB(dsn, initialize_schema=False)
        before = [row[0] for row in backend.conn.execute('SELECT tablename FROM pg_tables WHERE schemaname=? ORDER BY tablename', (schema,)).fetchall()]
        revision = backend.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='incassi'").fetchone()[0]
        ledger = GestionePrimaNota(str(tmp_path / 'non-leggere.json'), studio_db=backend, tenant_key='studio-test', actor_key='attore-test')
        ledger.registra(importo=260)
        assert ledger.saldi()['saldo'] == 260
        assert backend.conn.execute('SELECT actor_key FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 'attore-test'
        assert backend.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='incassi'").fetchone()[0] == revision + 1
        after = [row[0] for row in backend.conn.execute('SELECT tablename FROM pg_tables WHERE schemaname=? ORDER BY tablename', (schema,)).fetchall()]
        assert before == after == ['_meta', 'operational_live_revisions', 'prima_nota_audit', 'prima_nota_commands', 'prima_nota_records', 'prima_nota_state', 'transactional_outbox']
        from flask import Flask
        from pct.prima_nota_transition import prima_nota_source_lock, prepare_transition_locked, commit_transition_locked
        import web.services.prima_nota_runtime as runtime
        import web.services.storage_runtime as storage_runtime
        source = tmp_path / 'historical.json'
        source.write_bytes(b'non-leggere-il-json')
        with prima_nota_source_lock(source):
            prepare_transition_locked(source, tenant='studio-test', source_sha256=hashlib.sha256(b'controlled').hexdigest())
            commit_transition_locked(source, tenant='studio-test', source_sha256=hashlib.sha256(b'controlled').hexdigest())
        profile = SimpleNamespace(uses_sqlite=False, effective_mode='POSTGRESQL', tenant_slug='studio-test')
        monkeypatch.setattr(storage_runtime, 'get_request_storage_runtime', lambda _: profile)
        monkeypatch.setattr(runtime, '_postgres_request_dsn', lambda: dsn)
        with Flask(__name__).test_request_context('/'):
            try:
                opened = runtime.open_prima_nota_runtime(source, anchor='clienti.json', tenant_key='studio-test', actor_key='attore-test',
                                                        get_profile=lambda _: profile, get_database=runtime.get_existing_prima_nota_database)
                assert opened.saldi()['saldo'] == 260
                command_key = str(uuid.uuid4())
                confirmed = opened.registra(importo=500, command_key=command_key)
                assert opened.registra(importo=500, command_key=command_key).id == confirmed.id
                assert opened.saldi()['saldo'] == 760
                assert opened._repository.db.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='incassi'").fetchone()[0] == revision + 2
                assert opened._repository.db.conn.execute('SELECT COUNT(*) FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 2
            finally:
                runtime.close_prima_nota_database()
        assert source.read_bytes() == b'non-leggere-il-json'
    finally:
        if backend is not None:
            backend.chiudi()
        database.raw_conn.rollback()
        database.conn.execute('SET search_path TO public')
        database.conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        database.raw_conn.commit()


def manager(db, tmp_path):
    return GestionePrimaNota(str(tmp_path / 'historical.json'), studio_db=db, tenant_key='studio-test', actor_key='attore-test')


def test_comando_ripetuto_restituisce_stesso_movimento_senza_nuovi_audit(database, tmp_path):
    from uuid import uuid4
    initialized(database)
    key = str(uuid4())
    original = manager(database, tmp_path).registra(importo=260, command_key=key)
    again = manager(database, tmp_path)
    repeated = again.registra(importo=260, command_key=key)
    assert repeated.to_dict() == original.to_dict()
    assert again._repository.last_command_replayed is True
    assert again.saldi()['saldo'] == 260
    assert again._repository.revision == 1
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 1
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 1


@pytest.mark.parametrize('difference', ['importo', 'attore'])
def test_identificativo_comando_non_riutilizzabile_per_dati_o_attore_diversi(database, tmp_path, difference):
    from uuid import uuid4
    initialized(database)
    key = str(uuid4())
    manager(database, tmp_path).registra(importo=260, command_key=key)
    again = manager(database, tmp_path)
    if difference == 'attore':
        again._repository.actor_key = 'altro-attore'
    with pytest.raises(PrimaNotaConflict):
        again.registra(importo=500 if difference == 'importo' else 260, command_key=key)
    assert manager(database, tmp_path).saldi()['saldo'] == 260
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 1


def test_errore_dopo_commit_recupera_conferma_persistente(database, tmp_path, monkeypatch):
    from uuid import uuid4
    initialized(database)
    first = manager(database, tmp_path)
    finish = first._repository._finish
    def interrupted(conn, *, rollback=False):
        finish(conn, rollback=rollback)
        if not rollback:
            raise OSError('Risposta interrotta dopo commit controllato')
    monkeypatch.setattr(first._repository, '_finish', interrupted)
    key = str(uuid4())
    with pytest.raises(OSError):
        first.registra(importo=260, command_key=key)
    again = manager(database, tmp_path)
    recovered = again.registra(importo=260, command_key=key)
    assert recovered.importo == 260
    assert again._repository.last_command_replayed is True
    assert len(again.registro()) == 1
    assert again._repository.revision == 1
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 1


def test_audit_fallito_annulla_anche_prenotazione_comando(database, tmp_path):
    from uuid import uuid4
    initialized(database)
    database.conn.execute('DROP TABLE prima_nota_audit')
    PrimaNotaRepository(database, 'studio-test')._finish(database.conn)
    with pytest.raises(Exception):
        manager(database, tmp_path).registra(importo=260, command_key=str(uuid4()))
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 0
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_records').fetchone()[0] == 0
    assert database.conn.execute('SELECT revision FROM prima_nota_state').fetchone()[0] == 0


def test_comando_uguale_isolato_per_tenant(database, tmp_path):
    from uuid import uuid4
    initialized(database)
    initialized(database, 'altro-studio')
    key = str(uuid4())
    first = manager(database, tmp_path).registra(importo=260, command_key=key)
    other = GestionePrimaNota(str(tmp_path / 'other.json'), studio_db=database, tenant_key='altro-studio', actor_key='attore-test')
    second = other.registra(importo=500, command_key=key)
    assert first.id != second.id
    assert manager(database, tmp_path).saldi()['saldo'] == 260
    assert other.saldi()['saldo'] == 500


def test_risultato_comando_discordante_non_viene_confermato(database):
    from uuid import uuid4
    repo = initialized(database)
    movement = MovimentoPrimaNota(importo=260).to_dict()
    command = {'key': str(uuid4()), 'operation': 'registrazione', 'request_sha256': 'a' * 64,
               'result': {'movement': {**movement, 'importo': 500}}}
    with pytest.raises(ValueError, match='discordante'):
        repo.save({movement['id']: movement}, command=command)
    assert repo.load() == {}
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 0


@pytest.mark.parametrize('key', ['non-uuid', ' ', 'A' * 36])
def test_chiave_comando_invalida_non_scrive(database, tmp_path, key):
    initialized(database)
    with pytest.raises(ValueError):
        manager(database, tmp_path).registra(importo=260, command_key=key)
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 0
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_records').fetchone()[0] == 0


@pytest.mark.parametrize('missing', ['movimento', 'audit'])
def test_conferma_senza_prova_materiale_non_diventa_successo(database, tmp_path, missing):
    from uuid import uuid4
    initialized(database)
    key = str(uuid4())
    manager(database, tmp_path).registra(importo=260, command_key=key)
    database.conn.execute('DELETE FROM prima_nota_records' if missing == 'movimento' else 'DELETE FROM prima_nota_audit WHERE revision>0')
    PrimaNotaRepository(database, 'studio-test')._finish(database.conn)
    with pytest.raises(RuntimeError, match='non riscontrati'):
        manager(database, tmp_path).registra(importo=260, command_key=key)
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 1


def test_comando_ripetuto_preserva_riconciliazione_successiva(database, tmp_path):
    from uuid import uuid4
    initialized(database)
    key = str(uuid4())
    ledger = manager(database, tmp_path)
    movement = ledger.registra(importo=260, command_key=key)
    ledger.marca_riconciliato(movement.id, riga_estratto_id='riga-controllata', importo_riga=260, verso_riga='INCASSO')
    repeated = ledger.registra(importo=260, command_key=key)
    assert repeated.id == movement.id
    assert ledger.registro()[0].riga_estratto_id == 'riga-controllata'
    assert ledger._repository.revision == 2


def test_errore_comando_non_nascosto_da_rilettura_fallita(database, tmp_path, monkeypatch):
    initialized(database)
    ledger = manager(database, tmp_path)
    ledger.registra(importo=260)
    def failed_save(*args, **kwargs):
        raise OSError('Errore primario del comando controllato')
    def failed_load(*args, **kwargs):
        raise RuntimeError('Connessione non disponibile nella rilettura')
    monkeypatch.setattr(ledger._repository, 'save', failed_save)
    monkeypatch.setattr(ledger, '_carica', failed_load)
    with pytest.raises(OSError, match='Errore primario'):
        ledger.registra(importo=500)
    assert ledger.saldi()['saldo'] == 260
    assert len(ledger.registro()) == 1


def test_stesso_comando_con_due_connessioni_sqlite_non_duplica(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4
    path = tmp_path / 'concurrent-commands.db'
    with sqlite3.connect(path) as connection:
        db = SimpleNamespace(conn=connection)
        PrimaNotaRepository(db, 'studio-test').ensure_schema()
        initialized(db)
    barrier = Barrier(2)
    key = str(uuid4())
    def write(_):
        with sqlite3.connect(path, timeout=10) as connection:
            ledger = manager(SimpleNamespace(conn=connection), tmp_path)
            lookup = ledger._repository.command_replay
            def simultaneous(command):
                result = lookup(command)
                assert result is None
                barrier.wait(timeout=10)
                return result
            ledger._repository.command_replay = simultaneous
            result = ledger.registra(importo=260, command_key=key)
            return result.id, ledger._repository.last_command_replayed
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, (0, 1)))
    assert results[0][0] == results[1][0]
    assert sorted(result[1] for result in results) == [False, True]
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT revision FROM prima_nota_state').fetchone()[0] == 1
        assert connection.execute('SELECT COUNT(*) FROM prima_nota_records').fetchone()[0] == 1
        assert connection.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 1
        assert connection.execute('SELECT COUNT(*) FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 1


def test_sql_non_inizializzato_non_inventa_archivio(database):
    with pytest.raises(ValueError, match='non inizializzata'):
        PrimaNotaRepository(database, 'studio-test', actor_key='attore-test').load()


def test_adozione_ripetuta_non_rilegge_mirror(database):
    initialized(database)
    assert initialized(database, payload={'stale': MovimentoPrimaNota(id='stale', importo=999).to_dict()}).load() == {}


def test_tenant_isolati(database):
    initialized(database, payload={'one': MovimentoPrimaNota(id='one', importo=10).to_dict()})
    other = initialized(database, 'altro-studio')
    assert other.load() == {}


def test_registra_storna_conserva_originale_e_json(database, tmp_path):
    initialized(database)
    path = tmp_path / 'historical.json'
    path.write_bytes(b'fonte-storica-non-toccare')
    first = manager(database, tmp_path)
    original = first.registra(tipo='INCASSO', importo=260, categoria='onorari')
    first.storna(original.id, motivo='rettifica controllata')
    again = manager(database, tmp_path)
    assert len(again.registro()) == 2
    assert again.saldi()['saldo'] == 0
    assert path.read_bytes() == b'fonte-storica-non-toccare'


def test_scrittura_obsoleta_non_cancella_movimenti(database, tmp_path):
    initialized(database)
    first, second = manager(database, tmp_path), manager(database, tmp_path)
    first.registra(tipo='INCASSO', importo=10, categoria='onorari')
    with pytest.raises(PrimaNotaConflict):
        second.registra(tipo='INCASSO', importo=20, categoria='onorari')
    assert second.saldi()['saldo'] == 10
    assert len(manager(database, tmp_path).registro()) == 1


def test_lotto_parcelle_conferma_una_sola_revisione_sql(database, tmp_path):
    initialized(database)
    ledger = manager(database, tmp_path)
    bills = [SimpleNamespace(id=pid, stato='PAGATA', totale=amount, data_pagamento='2026-10-08')
             for pid, amount in [('P1', 260), ('P2', 500)]]
    created = ledger.incassi_da_parcelle(SimpleNamespace(tutte=lambda: bills))
    assert len(created) == 2 and ledger._repository.revision == 1
    assert manager(database, tmp_path).saldi()['incassi'] == 760
    assert ledger.incassi_da_parcelle(SimpleNamespace(tutte=lambda: bills)) == []
    assert ledger._repository.revision == 1
    audit = database.conn.execute("SELECT revision,actor_key,record_key FROM prima_nota_audit WHERE revision>0 AND tenant_key=?", ('studio-test',)).fetchall()
    assert len(audit) == 2
    assert all(row[0] == 1 and row[1] == 'attore-test' for row in audit)


def test_audit_sql_non_disponibile_annulla_movimento_e_revisione(database, tmp_path):
    initialized(database)
    ledger = manager(database, tmp_path)
    database.conn.execute('DROP TABLE prima_nota_audit')
    if hasattr(database, 'raw_conn'):
        database.raw_conn.commit()
    else:
        database.conn.commit()
    with pytest.raises(Exception):
        ledger.registra(importo=260)
    assert manager(database, tmp_path).registro() == []
    assert ledger._repository.revision == 0


def test_attore_assente_non_autorizza_scrittura_sql(database, tmp_path):
    initialized(database)
    ledger = GestionePrimaNota(str(tmp_path / 'historical.json'), studio_db=database, tenant_key='studio-test')
    with pytest.raises(ValueError, match='Attore.*mancante'):
        ledger.registra(importo=260)
    assert ledger.registro() == [] and ledger._repository.revision == 0
    assert database.conn.execute('SELECT count(*) FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 0


@pytest.mark.skipif(os.environ.get('PRIMA_NOTA_TEST_POSTGRES') != '1', reason='Richiede PostgreSQL nativo controllato')
def test_runtime_postgres_nativo_riscontra_marker_senza_rileggere_json(database, tmp_path):
    from web.services.prima_nota_runtime import open_prima_nota_runtime
    from pct.prima_nota_transition import prima_nota_source_lock, prepare_transition_locked, commit_transition_locked
    repo = initialized(database)
    sha = hashlib.sha256(b'controlled').hexdigest()
    source = tmp_path / 'historical.json'
    source.write_bytes(b'fonte-storica-non-rileggere')
    with prima_nota_source_lock(source):
        prepare_transition_locked(source, tenant='studio-test', source_sha256=sha)
        commit_transition_locked(source, tenant='studio-test', source_sha256=sha)
    ledger = open_prima_nota_runtime(source, anchor='canonical-clienti.json', tenant_key='studio-test', actor_key='attore-test',
        get_profile=lambda _: SimpleNamespace(uses_sqlite=False, tenant_slug='studio-test'), get_database=lambda _: database)
    ledger.registra(importo=260)
    assert repo.load()[ledger.registro()[0].id]['importo'] == 260
    assert ledger._repository.actor_key == 'attore-test'
    assert source.read_bytes() == b'fonte-storica-non-rileggere'


def test_audit_conserva_prima_e_dopo_riconciliazione_senza_riscrivere_storia(database, tmp_path):
    import json
    initialized(database)
    ledger = manager(database, tmp_path)
    movement = ledger.registra(importo=260)
    ledger.marca_riconciliato(movement.id, riga_estratto_id='riga-controllata', importo_riga=260)
    rows = database.conn.execute(
        'SELECT revision,action,before_json,after_json FROM prima_nota_audit WHERE revision>0 AND tenant_key=? ORDER BY revision',
        ('studio-test',),
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][0] == 1 and rows[0][1] == 'registrazione'
    assert json.loads(rows[0][2]) == {}
    assert json.loads(rows[0][3])['riga_estratto_id'] == ''
    assert rows[1][0] == 2 and rows[1][1] == 'riconciliazione'
    assert json.loads(rows[1][2]) == json.loads(rows[0][3])
    assert json.loads(rows[1][3])['riga_estratto_id'] == 'riga-controllata'


def test_lotto_parcelle_obsoleto_non_conferma_sottoinsieme(database, tmp_path):
    initialized(database)
    first, stale = manager(database, tmp_path), manager(database, tmp_path)
    first.registra(importo=10)
    bills = [SimpleNamespace(id=pid, stato='PAGATA', totale=amount, data_pagamento='2026-10-08')
             for pid, amount in [('P1', 260), ('P2', 500)]]
    with pytest.raises(PrimaNotaConflict):
        stale.incassi_da_parcelle(SimpleNamespace(tutte=lambda: bills))
    assert stale.saldi()['incassi'] == 10
    assert len(manager(database, tmp_path).registro()) == 1


def test_storno_concorrente_non_duplica(database, tmp_path):
    initialized(database)
    initial = manager(database, tmp_path)
    movement = initial.registra(tipo='INCASSO', importo=260, categoria='onorari')
    first, second = manager(database, tmp_path), manager(database, tmp_path)
    first.storna(movement.id, motivo='rettifica')
    with pytest.raises(PrimaNotaConflict):
        second.storna(movement.id, motivo='stessa rettifica')
    assert len(manager(database, tmp_path).registro()) == 2


def test_cancellazione_o_modifica_importo_non_consentite(database):
    movement = MovimentoPrimaNota(importo=260).to_dict()
    repo = initialized(database, payload={movement['id']: movement})
    with pytest.raises(ValueError, match='eliminati'):
        repo.save({})
    with pytest.raises(ValueError, match='riscritto'):
        repo.save({movement['id']: {**movement, 'importo': 500}})
    assert repo.load()[movement['id']]['importo'] == 260


def test_riconciliazione_obsoleta_non_sovrascrive(database, tmp_path):
    initialized(database)
    initial = manager(database, tmp_path)
    movement = initial.registra(tipo='INCASSO', importo=260, categoria='onorari')
    first, second = manager(database, tmp_path), manager(database, tmp_path)
    first.marca_riconciliato(movement.id, riga_estratto_id='riga-1', importo_riga=260, verso_riga='INCASSO')
    with pytest.raises(PrimaNotaConflict):
        second.marca_riconciliato(movement.id, riga_estratto_id='riga-2', importo_riga=260, verso_riga='INCASSO')
    assert manager(database, tmp_path).registro()[0].riga_estratto_id == 'riga-1'


def test_importo_non_finito_non_entra_in_sql(database):
    repo = initialized(database)
    with pytest.raises(ValueError):
        repo.save({'invalid': {'importo': float('nan')}})
    assert repo.load() == {}


def test_retry_parcella_dopo_conflitto_non_duplica_incasso(database, tmp_path):
    initialized(database)
    billing = SimpleNamespace(tutte=lambda: [SimpleNamespace(
        id='parcella-controllata', stato='PAGATA', totale=260, data_pagamento='2026-10-08',
    )])
    first, second = manager(database, tmp_path), manager(database, tmp_path)
    assert len(first.incassi_da_parcelle(billing)) == 1
    with pytest.raises(PrimaNotaConflict):
        second.incassi_da_parcelle(billing)
    assert second.incassi_da_parcelle(billing) == []
    assert len(manager(database, tmp_path).registro()) == 1


def test_backend_sqlite_nativo_supporta_scritture_governate(tmp_path):
    from pct.storage import StudioDB
    db = StudioDB(str(tmp_path / 'native.db'))
    try:
        repo = PrimaNotaRepository(db, 'studio-test')
        repo.ensure_schema()
        initialized(db)
        movement = manager(db, tmp_path).registra(tipo='INCASSO', importo=260, categoria='onorari')
        assert manager(db, tmp_path).registro()[0].id == movement.id
    finally:
        db._close_thread_connection()


def test_fonte_storica_preserva_movementi_e_collegamento_storno():
    original = MovimentoPrimaNota(importo=260, data='2026-10-08').to_dict()
    reverse = MovimentoPrimaNota(importo=260, tipo='PAGAMENTO', categoria='altri_pagamenti',
                                note=f"Storno di {original['id']}: rettifica").to_dict()
    result = validate_legacy_payload({original['id']: original, reverse['id']: reverse})
    assert result[original['id']] == original
    assert result[reverse['id']]['storno_di'] == original['id']


@pytest.mark.parametrize('field,value', [('id','altro'), ('importo',float('nan')), ('importo','260'),
                                      ('data','2026-02-30'), ('data','2026-1-1'), ('creato_il',''),
                                      ('creato_il','ieri'), ('creato_il','2026-10-08'),
                                      ('metodo','sconosciuto'), ('cliente_id',None),
                                      ('riconciliato_il','2026-10-08T12:00:00'),
                                      ('categoria','sconosciuta'), ('campo_nuovo','non eliminare')])
def test_fonte_storica_incoerente_non_adottata(field, value):
    original = MovimentoPrimaNota(importo=260).to_dict()
    invalid = {**original, field: value}
    with pytest.raises(ValueError):
        validate_legacy_payload({original['id']: invalid})


def test_righe_bancarie_storiche_duplicate_non_unificate():
    first = MovimentoPrimaNota(importo=260, riga_estratto_id='riga-1', riconciliato_il='2026-10-08T12:00:00').to_dict()
    second = {**first, 'id': 'secondo'}
    with pytest.raises(ValueError, match='duplicata'):
        validate_legacy_payload({first['id']: first, second['id']: second})


def test_lettura_fonte_assente_non_crea_json(tmp_path):
    from scripts.migra_prima_nota_sql import read_source
    path = tmp_path / 'assente.json'
    payload, fingerprint, content = read_source(path)
    assert payload == {} and content is None and len(fingerprint) == 64
    assert not path.exists()


def test_migrazione_usa_database_canonico_non_sottocartella_contabile(tmp_path):
    from scripts.migra_prima_nota_sql import canonical_sql_anchor
    from web.services.storage_runtime import _derive_studio_db_path
    root = tmp_path / 'tenants' / 'studio-controllato'
    paths = {'CLIENTI_DB': root / 'clienti' / 'anagrafica.json',
             'PRIMA_NOTA_DB': root / 'contabilita' / 'prima_nota.json'}
    anchor = canonical_sql_anchor(paths.get)
    assert anchor == str(paths['CLIENTI_DB'])
    assert _derive_studio_db_path(anchor) == str((root / 'studio.db').resolve())
    assert not (root / 'contabilita' / 'studio.db').exists()


def test_migrazione_senza_riferimento_canonico_bloccata():
    from scripts.migra_prima_nota_sql import canonical_sql_anchor
    with pytest.raises(RuntimeError, match='canonico'):
        canonical_sql_anchor(lambda _: None)


def test_adozione_non_attivabile_senza_barriera_produttori(monkeypatch, tmp_path):
    import sys
    from scripts.migra_prima_nota_sql import main
    backup = tmp_path / 'backup'
    report = tmp_path / 'report.jsonl'
    monkeypatch.setattr(sys, 'argv', ['migra_prima_nota_sql', '--tenant', 'studio-controllato',
                                    '--report', str(report), '--apply', '--backup-dir', str(backup)])
    with pytest.raises(SystemExit) as rejected:
        main()
    assert rejected.value.code == 2
    assert not backup.exists() and not report.exists()


def test_scritture_simultanee_connessioni_sqlite_non_perdono_movimenti(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    path = tmp_path / 'concurrent.db'
    with sqlite3.connect(path) as connection:
        db = SimpleNamespace(conn=connection)
        PrimaNotaRepository(db, 'studio-test').ensure_schema()
        initialized(db)
    barrier = Barrier(2)
    def write(amount):
        connection = sqlite3.connect(path, timeout=10)
        try:
            ledger = manager(SimpleNamespace(conn=connection), tmp_path)
            barrier.wait(timeout=10)
            try:
                ledger.registra(importo=amount)
                return 'saved'
            except PrimaNotaConflict:
                # Ripresa governata: carica la revisione vincente prima del retry.
                ledger.registra(importo=amount)
                return 'retried'
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, (260, 500)))
    assert sorted(results) == ['retried', 'saved']
    with sqlite3.connect(path) as connection:
        records = PrimaNotaRepository(SimpleNamespace(conn=connection), 'studio-test').load()
    assert sorted(value['importo'] for value in records.values()) == [260, 500]


def test_segnale_live_nativo_commit_rollback_e_scrittura_vuota(database):
    import uuid
    from pct.operational_live import ensure_live_schema
    conn = database.conn
    postgres = os.environ.get('PRIMA_NOTA_TEST_POSTGRES') == '1'
    schema = 'test_prima_nota_live_' + uuid.uuid4().hex
    try:
        if postgres:
            # Solo lo schema controllato di questa prova, senza dati applicativi.
            conn.execute('DROP TABLE pg_temp.prima_nota_records')
            conn.execute('DROP TABLE pg_temp.prima_nota_state')
            conn.execute(f'CREATE SCHEMA "{schema}"')
            conn.execute(f'SET search_path TO "{schema}", pg_catalog')
        conn.execute('CREATE TABLE _meta(chiave TEXT PRIMARY KEY, valore TEXT)')
        repo = PrimaNotaRepository(database, 'studio-test', actor_key='attore-test')
        repo.ensure_schema()
        ensure_live_schema(conn, postgres=postgres)
        repo = initialized(database)
        def revision():
            return conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='incassi'").fetchone()[0]
        initial = revision()
        movements = {key: MovimentoPrimaNota(id=key, importo=amount).to_dict() for key, amount in [('one',260),('two',500)]}
        repo.save(movements)
        assert revision() == initial + 1
        repo.save(movements)
        assert revision() == initial + 1
        conn.execute("UPDATE prima_nota_state SET revision=revision+1 WHERE tenant_key='studio-test'")
        repo._finish(conn, rollback=True)
        assert revision() == initial + 1
    finally:
        if postgres:
            database.raw_conn.rollback()
            conn.execute('SET search_path TO public')
            conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            database.raw_conn.commit()


@pytest.mark.parametrize('operation', ['initialize', 'save', 'load'])
@pytest.mark.parametrize('field,value', [('id','wrong'), ('importo',-1), ('data','2026-02-30'), ('categoria','invalid')])
def test_repository_rifiuta_dati_incoerenti_su_ogni_percorso(database, operation, field, value):
    valid = MovimentoPrimaNota(id='controlled', importo=260).to_dict()
    payload = {'controlled': {**valid, field: value}}
    repo = PrimaNotaRepository(database, 'studio-test', actor_key='attore-test')
    if operation == 'initialize':
        with pytest.raises(ValueError):
            repo.initialize(payload, source_sha256='a'*64, backup_reference='controlled-backup')
        assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_state').fetchone()[0] == 0
    else:
        repo = initialized(database)
        if operation == 'load':
            import json
            database.conn.execute('INSERT INTO prima_nota_records VALUES (?,?,?,?)',
                                  ('studio-test','controlled',json.dumps(payload['controlled']),'controlled-test'))
            repo._finish(database.conn)
            with pytest.raises(ValueError):
                repo.load()
        else:
            with pytest.raises(ValueError):
                repo.save(payload)
            assert repo.load() == {}
        assert database.conn.execute('SELECT revision FROM prima_nota_state').fetchone()[0] == 0


@pytest.mark.skipif(os.environ.get('PRIMA_NOTA_TEST_POSTGRES') != '1', reason='Richiede PostgreSQL nativo controllato')
@pytest.mark.parametrize('same_command', [False, True])
def test_scritture_simultanee_postgres_preservano_movimenti_e_conflitto(tmp_path, same_command):
    import uuid
    import psycopg2
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from pct.storage_postgres import PostgresCompatConnection
    schema = 'test_prima_nota_concurrent_' + uuid.uuid4().hex
    def connect():
        raw = psycopg2.connect(host=os.environ.get('PRIMA_NOTA_TEST_PG_HOST','audit-postgres'),
                              dbname=os.environ.get('AUDIT_POSTGRES_DB','iusentra_audit'),
                              user=os.environ.get('AUDIT_POSTGRES_USER','iusentra_audit'),
                              password=os.environ['AUDIT_POSTGRES_PASSWORD'])
        db = SimpleNamespace(raw_conn=raw)
        db.conn = PostgresCompatConnection(db)
        return db
    admin = connect()
    try:
        admin.conn.execute(f'CREATE SCHEMA "{schema}"')
        admin.conn.execute(f'SET search_path TO "{schema}", pg_catalog')
        PrimaNotaRepository(admin, 'studio-test', actor_key='attore-test').ensure_schema()
        initialized(admin)
        barrier = Barrier(2)
        command_key = str(uuid.uuid4())
        def write(amount):
            db = connect()
            try:
                db.conn.execute(f'SET search_path TO "{schema}", pg_catalog')
                # Mantiene lo schema di test anche quando il conflitto fa rollback.
                db.raw_conn.commit()
                # Ogni operatore ha una connessione e una revisione autonome.
                ledger = manager(db, tmp_path)
                if same_command:
                    lookup = ledger._repository.command_replay
                    def simultaneous(command):
                        result = lookup(command)
                        assert result is None
                        barrier.wait(timeout=10)
                        return result
                    ledger._repository.command_replay = simultaneous
                    result = ledger.registra(importo=260, command_key=command_key)
                    return result.id, ledger._repository.last_command_replayed
                barrier.wait(timeout=10)
                try:
                    ledger.registra(importo=amount)
                    return 'saved'
                except PrimaNotaConflict:
                    ledger.registra(importo=amount)
                    return 'retried'
            finally:
                db.raw_conn.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, (260, 500)))
        if same_command:
            assert results[0][0] == results[1][0]
            assert sorted(result[1] for result in results) == [False, True]
        else:
            assert sorted(results) == ['retried','saved']
        # Chiude lo snapshot della lettura iniziale; legge la revisione confermata.
        admin.raw_conn.rollback()
        admin.conn.execute(f'SET search_path TO "{schema}", pg_catalog')
        repo = PrimaNotaRepository(admin, 'studio-test', actor_key='attore-test')
        assert sorted(v['importo'] for v in repo.load().values()) == ([260] if same_command else [260,500])
        assert repo.revision == (1 if same_command else 2)
        if same_command:
            assert admin.conn.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 1
            assert admin.conn.execute('SELECT COUNT(*) FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 1
    finally:
        admin.raw_conn.rollback()
        admin.conn.execute('SET search_path TO public')
        admin.conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        admin.raw_conn.commit()
        admin.raw_conn.close()


def test_revisione_schermata_obsoleta_non_registra_ma_retry_confermato_recupera(database, tmp_path):
    import uuid
    initialized(database)
    stale = manager(database, tmp_path)
    fresh = manager(database, tmp_path)
    key = str(uuid.uuid4())
    first = fresh.registra(importo=260, command_key=key, expected_revision=0)
    current = manager(database, tmp_path)
    with pytest.raises(PrimaNotaConflict, match='registro è cambiato'):
        current.registra(importo=500, command_key=str(uuid.uuid4()), expected_revision=0)
    assert current.saldi()['saldo'] == 260
    replay = current.registra(importo=260, command_key=key, expected_revision=0)
    assert replay.id == first.id
    assert current.write_protocol['persistentCommands'] is True and current.write_protocol['revision'] == 1
    assert len(current.write_protocol['scope']) == 64
    with pytest.raises(PrimaNotaConflict):
        stale.registra(importo=500, command_key=str(uuid.uuid4()), expected_revision=0)
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 1
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 1


@pytest.mark.parametrize('revision', [True, False, -1, 0.0, '0'])
def test_revisione_comando_non_valida_non_scrive(database, tmp_path, revision):
    import uuid
    initialized(database)
    ledger = manager(database, tmp_path)
    with pytest.raises(ValueError, match='Revisione'):
        ledger.registra(importo=260, command_key=str(uuid.uuid4()), expected_revision=revision)
    assert ledger.registro() == []
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 0


def test_api_protocollo_sql_revisione_e_retry(database, tmp_path):
    import uuid
    from flask import Flask, g
    from web.bootstrap.prima_nota_routes import register_prima_nota_routes
    initialized(database)
    app = Flask(__name__)
    @app.before_request
    def actor():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda _key: True, username='prova')
    audits = []
    register_prima_nota_routes(app, {'get_prima_nota': lambda: manager(database, tmp_path),
        'get_fatturazione': lambda: None, 'audit': lambda *args, **kwargs: audits.append(args)})
    client = app.test_client()
    payload = {'data': '2026-10-09', 'tipo': 'INCASSO', 'importo': 260, 'categoria': 'onorari'}
    assert client.post('/prima-nota/registra', json=payload).status_code == 428
    key = str(uuid.uuid4())
    payload.update(commandKey=key, expectedRevision=None)
    assert client.post('/prima-nota/registra', json=payload).status_code == 400
    payload['expectedRevision'] = 0
    first = client.post('/prima-nota/registra', json=payload)
    assert first.status_code == 200 and first.json['writeProtocol']['revision'] == 1
    second = client.post('/prima-nota/registra', json=payload)
    assert second.status_code == 200 and second.json['movimentoId'] == first.json['movimentoId']
    payload['commandKey'] = str(uuid.uuid4())
    assert client.post('/prima-nota/registra', json=payload).status_code == 409
    read = client.get('/api/v1/ui/prima-nota')
    assert read.status_code == 200 and read.json['writeProtocol']['revision'] == 1
    assert read.json['summary']['saldo'] == 260
    assert len(manager(database, tmp_path).registro()) == 1
    # Audit generale ancora separato: non confondere il replay di dominio con un outbox completo.
    assert audits == []
    assert database.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1


def test_api_sql_esito_interrotto_recupera_stesso_movimento(database, tmp_path, monkeypatch):
    import uuid
    from flask import Flask, g
    from web.bootstrap.prima_nota_routes import register_prima_nota_routes
    initialized(database)
    app = Flask(__name__)
    @app.before_request
    def actor():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda _key: True, username='prova')
    attempts = []
    native_delivery = PrimaNotaRepository.deliver_audit
    def interrupted(self, **kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise OSError('Consegna audit interrotta dopo persistenza movimento')
        return native_delivery(self, **kwargs)
    monkeypatch.setattr(PrimaNotaRepository,'deliver_audit',interrupted)
    def audit(*args, **kwargs):
        pytest.fail('Audit SQL non deve tornare al percorso storico')
    register_prima_nota_routes(app, {'get_prima_nota': lambda: manager(database, tmp_path),
        'get_fatturazione': lambda: None, 'audit': audit})
    client = app.test_client()
    payload = {'data':'2026-10-09', 'tipo':'INCASSO', 'importo':260, 'categoria':'onorari',
               'commandKey':str(uuid.uuid4()), 'expectedRevision':0}
    first = client.post('/prima-nota/registra', json=payload)
    assert first.status_code == 503 and first.json['code'] == 'outcome_not_confirmed'
    saved = manager(database, tmp_path).registro()[0]
    second = client.post('/prima-nota/registra', json=payload)
    assert second.status_code == 200 and second.json['movimentoId'] == saved.id
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_records').fetchone()[0] == 1
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_audit WHERE revision>0').fetchone()[0] == 1
    assert database.conn.execute('SELECT revision FROM prima_nota_state').fetchone()[0] == 1
    # Il problema dell'audit generale non viene dichiarato risolto da questa prova.


def test_replay_revision_cambiata_non_equivale_comando_originario(database, tmp_path):
    import uuid
    initialized(database)
    ledger = manager(database, tmp_path)
    key = str(uuid.uuid4())
    ledger.registra(importo=260, command_key=key, expected_revision=0)
    with pytest.raises(PrimaNotaConflict):
        ledger.registra(importo=260, command_key=key, expected_revision=1)
    assert len(ledger.registro()) == 1


def test_outbox_audit_atomicamente_confermato_senza_dispatch(database, tmp_path):
    import json
    import uuid
    initialized(database)
    ledger = manager(database, tmp_path)
    key = str(uuid.uuid4())
    movement = ledger.registra(importo=260, command_key=key, expected_revision=0)
    ledger.registra(importo=260, command_key=key, expected_revision=0)
    rows = database.conn.execute('SELECT tenant_id,aggregate_id,aggregate_version,event_type,actor_id,payload_json,status,attempts FROM transactional_outbox').fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert tuple(row[i] for i in range(5)) == ('studio-test',movement.id,1,'prima_nota.audit_requested','attore-test')
    payload = json.loads(row[5])
    assert payload['before'] == {} and payload['after'] == movement.to_dict()
    assert (row[6],row[7]) == ('PENDING',0)
    assert payload['action'] == 'registrazione'


def test_outbox_non_disponibile_annulla_movimento_audit_e_comando(database, tmp_path):
    import uuid
    initialized(database)
    database.conn.execute('DROP TABLE transactional_outbox')
    PrimaNotaRepository(database,'studio-test')._finish(database.conn)
    ledger = manager(database, tmp_path)
    with pytest.raises(Exception):
        ledger.registra(importo=260,command_key=str(uuid.uuid4()),expected_revision=0)
    assert ledger.registro() == []
    for table in ['prima_nota_records','prima_nota_audit','prima_nota_commands']:
        assert database.conn.execute(f'SELECT COUNT(*) FROM {table}' + (' WHERE revision>0' if table == 'prima_nota_audit' else '')).fetchone()[0] == 0
    assert database.conn.execute('SELECT revision FROM prima_nota_state').fetchone()[0] == 0


def test_replay_senza_richiesta_audit_non_dichiara_conferma(database, tmp_path):
    import uuid
    initialized(database)
    ledger = manager(database,tmp_path)
    key = str(uuid.uuid4())
    movement = ledger.registra(importo=260,command_key=key,expected_revision=0)
    database.conn.execute('DELETE FROM transactional_outbox')
    ledger._repository._finish(database.conn)
    with pytest.raises(RuntimeError,match='audit Prima nota non riscontrata'):
        ledger.registra(importo=260,command_key=key,expected_revision=0)
    assert ledger.registro()[0].id == movement.id
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_commands').fetchone()[0] == 1


def test_outbox_discordante_non_produce_falsa_conferma(database,tmp_path,monkeypatch):
    from dataclasses import replace
    import pct.transactional_outbox as outbox
    initialized(database)
    ledger = manager(database,tmp_path)
    enqueue = outbox.enqueue
    def wrong_actor(conn,event):
        return enqueue(conn,replace(event,actor_id='attore-diverso'))
    monkeypatch.setattr(outbox,'enqueue',wrong_actor)
    with pytest.raises(RuntimeError,match='audit Prima nota non riscontrata'):
        ledger.registra(importo=260)
    assert ledger.registro() == []
    assert database.conn.execute('SELECT COUNT(*) FROM transactional_outbox').fetchone()[0] == 0
    assert database.conn.execute('SELECT revision FROM prima_nota_state').fetchone()[0] == 0


def test_consegna_audit_ripetuta_conserva_un_evento_confermato(database,tmp_path):
    initialized(database)
    ledger = manager(database,tmp_path)
    movement = ledger.registra(importo=260)
    assert ledger.confirm_audit(movement.id) == 1
    confirmed_at = database.conn.execute('SELECT processed_at FROM transactional_outbox').fetchone()[0]
    assert ledger.confirm_audit(movement.id) == 1
    assert database.conn.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0] == 1
    row = database.conn.execute('SELECT status,processed_at FROM transactional_outbox').fetchone()
    assert row[0] == 'PROCESSED' and row[1]
    assert row[1] == confirmed_at
    audit = database.conn.execute('SELECT id_utente,azione,risorsa_id,dettagli FROM audit_log').fetchone()
    assert tuple(audit[i] for i in range(4)) == ('attore-test','prima_nota.registrato',movement.id,'INCASSO € 260,00')


def test_consegna_audit_guasta_preserva_movimento_e_pendenza(database,tmp_path):
    initialized(database)
    ledger = manager(database,tmp_path)
    movement = ledger.registra(importo=260)
    database.conn.execute('DROP TABLE audit_log')
    ledger._repository._finish(database.conn)
    with pytest.raises(Exception):
        ledger.confirm_audit(movement.id)
    assert ledger.registro()[0].id == movement.id
    assert database.conn.execute('SELECT status FROM transactional_outbox').fetchone()[0] == 'PENDING'


def test_consegna_audit_collisione_non_sovrascrive_evento(database,tmp_path):
    initialized(database)
    ledger = manager(database,tmp_path)
    movement = ledger.registra(importo=260)
    event_id = database.conn.execute('SELECT id FROM transactional_outbox').fetchone()[0]
    database.conn.execute("INSERT INTO audit_log(id,timestamp,azione) VALUES(?,?,'altro-evento')",(event_id,'controllato'))
    ledger._repository._finish(database.conn)
    with pytest.raises(RuntimeError,match='Audit generale discordante'):
        ledger.confirm_audit(movement.id)
    assert database.conn.execute('SELECT azione FROM audit_log').fetchone()[0] == 'altro-evento'
    assert database.conn.execute('SELECT status FROM transactional_outbox').fetchone()[0] == 'PENDING'


def test_adozione_audit_conserva_impronta_e_backup(database):
    import json
    initialized(database)
    rows = database.conn.execute("SELECT actor_key,action,after_json FROM prima_nota_audit WHERE revision=0").fetchall()
    assert len(rows) == 1 and rows[0][1] == 'adozione'
    proof = json.loads(rows[0][2])
    assert proof['records'] == 0 and proof['backup_reference'] == 'controlled-test-backup'
    assert len(proof['source_sha256']) == 64
    initialized(database)
    assert database.conn.execute('SELECT COUNT(*) FROM prima_nota_audit WHERE revision=0').fetchone()[0] == 1


def test_retry_audit_attende_dopo_errore_e_recupera(database,tmp_path):
    initialized(database)
    ledger = manager(database,tmp_path)
    ledger.registra(importo=260)
    database.conn.execute('ALTER TABLE audit_log RENAME TO audit_saved')
    ledger._repository._finish(database.conn)
    assert ledger._repository.retry_pending_audit() == {'delivered':0,'failed':1}
    row = database.conn.execute('SELECT attempts,last_error,status FROM transactional_outbox').fetchone()
    assert tuple(row[i] for i in range(3)) == (1,'Consegna audit non confermata: recupero necessario.','PENDING')
    assert ledger._repository.retry_pending_audit() == {'delivered':0,'failed':0}
    database.conn.execute('ALTER TABLE audit_saved RENAME TO audit_log')
    database.conn.execute("UPDATE transactional_outbox SET available_at='2000-01-01'")
    ledger._repository._finish(database.conn)
    assert ledger._repository.retry_pending_audit() == {'delivered':1,'failed':0}
    assert database.conn.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0] == 1


def test_consegna_audit_assente_non_conferma_movimento(database,tmp_path):
    initialized(database)
    ledger = manager(database,tmp_path)
    movement = ledger.registra(importo=260)
    database.conn.execute('DELETE FROM transactional_outbox')
    ledger._repository._finish(database.conn)
    with pytest.raises(RuntimeError,match='assente'):
        ledger.confirm_audit(movement.id)
    assert len(ledger.registro()) == 1
    assert database.conn.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0] == 0


def test_bank_row_registration_atomic_and_concordant_replay(database, tmp_path):
    from pct.prima_nota import GestionePrimaNota
    repo = initialized(database)
    manager = GestionePrimaNota(str(tmp_path / 'unused.json'), studio_db=database, tenant_key='studio-test', actor_key='attore-test')
    repo = manager._repository
    fields = dict(data='2026-10-09', tipo='PAGAMENTO', importo=8, categoria='altri_pagamenti', causale='Spesa controllata', metodo='banca')
    first = manager.registra_da_riga(riga_estratto_id='bank-row-1', **fields)
    assert first.riga_estratto_id == 'bank-row-1' and first.riconciliato_il
    assert repo.revision == 1
    second = manager.registra_da_riga(riga_estratto_id='bank-row-1', **fields)
    assert second.id == first.id and repo.revision == 1
    assert len(manager.registro()) == 1
    with pytest.raises(ValueError, match='dati diversi'):
        manager.registra_da_riga(riga_estratto_id='bank-row-1', **{**fields, 'importo': 9})
    assert repo.revision == 1 and len(manager.registro()) == 1
    manager.confirm_audit(first.id)
    manager.confirm_audit(first.id)
    assert database.conn.execute("SELECT count(*) FROM audit_log WHERE azione='prima_nota.registrato'").fetchone()[0] == 1


def test_bank_row_failure_rolls_back_movement_and_reconciliation(database, tmp_path, monkeypatch):
    from pct.prima_nota import GestionePrimaNota
    repo = initialized(database)
    manager = GestionePrimaNota(str(tmp_path / 'unused.json'), studio_db=database, tenant_key='studio-test', actor_key='attore-test')
    repo = manager._repository
    def fail(*args, **kwargs):
        raise RuntimeError('controlled failure')
    monkeypatch.setattr(repo, 'save', fail)
    with pytest.raises(RuntimeError, match='controlled failure'):
        manager.registra_da_riga(riga_estratto_id='bank-row-fail', data='2026-10-09', tipo='INCASSO', importo=10, categoria='onorari')
    assert manager.registro() == [] and repo.revision == 0
