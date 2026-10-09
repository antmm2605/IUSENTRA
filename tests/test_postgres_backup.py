"""Guardrail del backup nativo; non sostituiscono una prova di ripristino."""
from types import SimpleNamespace
import os

import pytest

pytest.importorskip('psycopg2.extensions', reason='Richiede il parser libpq nativo, non lo stub dei test Windows')

from scripts.postgres_backup import backup_postgres


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.setattr('scripts.postgres_backup.shutil.which', lambda name, **kwargs: '/tools/' + name)


def test_backup_credenziali_fuori_da_argv_e_manifest(monkeypatch, tmp_path, tools):
    calls = []
    monkeypatch.setenv('PGDATABASE', 'database-non-autorizzato')
    monkeypatch.setenv('PGPASSWORD', 'password-esterna')
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[0].endswith('pg_dump'):
            kwargs['stdout'].write(b'PGDMP-controlled-test')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('scripts.postgres_backup.subprocess.run', run)
    result = backup_postgres('dbname=controlled user=test password=secret-test host=localhost', tmp_path / 'backup.dump')
    assert len(calls) == 2
    assert calls[0][1]['env']['PGDATABASE'] == 'controlled'
    assert calls[0][1]['env']['PGPASSWORD'] == 'secret-test'
    assert 'secret-test' not in str([call[0] for call in calls]) + str(result)
    assert result['archive_index_verified'] is True and result['restore_verified'] is False
    assert result['backup_bytes'] > 0 and len(result['sha256']) == 64


def test_backup_non_sovrascrive_archivio(tmp_path, tools):
    path = tmp_path / 'backup.dump'
    path.write_bytes(b'originale')
    with pytest.raises(FileExistsError):
        backup_postgres('dbname=controlled', path)
    assert path.read_bytes() == b'originale'


def test_strumenti_assenti_non_creano_backup(monkeypatch, tmp_path):
    monkeypatch.setattr('scripts.postgres_backup.shutil.which', lambda name, **kwargs: None)
    path = tmp_path / 'backup.dump'
    with pytest.raises(RuntimeError, match='non disponibili'):
        backup_postgres('dbname=controlled', path)
    assert not path.exists()


@pytest.mark.parametrize('phase', ['dump', 'empty', 'verify'])
def test_backup_fallito_non_dichiara_successo(monkeypatch, tmp_path, tools, phase):
    def run(argv, **kwargs):
        dumping = argv[0].endswith('pg_dump')
        if dumping and phase != 'empty':
            kwargs['stdout'].write(b'partial-controlled')
        return SimpleNamespace(returncode=1 if (dumping and phase == 'dump') or (not dumping and phase == 'verify') else 0)
    monkeypatch.setattr('scripts.postgres_backup.subprocess.run', run)
    path = tmp_path / 'backup.dump'
    with pytest.raises(RuntimeError):
        backup_postgres('dbname=controlled', path)
    assert path.exists()  # parziale preservato, mai presentato come backup valido


@pytest.mark.skipif(os.environ.get('PRIMA_NOTA_TEST_POSTGRES') != '1', reason='Richiede PostgreSQL nativo controllato')
def test_backup_e_ripristino_postgres_nativi_con_dati_controllati(tmp_path):
    import subprocess
    import uuid
    import psycopg2
    from psycopg2.extensions import make_dsn
    suffix = uuid.uuid4().hex
    source, target = 'test_backup_source_' + suffix, 'test_backup_restore_' + suffix
    parameters = {
        'host': os.environ.get('PRIMA_NOTA_TEST_PG_HOST', 'audit-postgres'),
        'user': os.environ.get('AUDIT_POSTGRES_USER', 'iusentra_audit'),
        'password': os.environ['AUDIT_POSTGRES_PASSWORD'],
    }
    admin = psycopg2.connect(**parameters, dbname=os.environ.get('AUDIT_POSTGRES_DB', 'iusentra_audit'))
    admin.autocommit = True
    created = []
    connection = restored = None
    expected = [(1, 'È una prova controllata: € 260,00', '260.00'), (2, 'Seconda fonte — nessun dato dello studio', '500.00')]
    try:
        for name in (source, target):
            with admin.cursor() as cursor:
                cursor.execute(f'CREATE DATABASE "{name}" TEMPLATE template0')
            created.append(name)
        with psycopg2.connect(**parameters, dbname=source) as connection:
            with connection.cursor() as cursor:
                cursor.execute('CREATE TABLE controlled(id INTEGER PRIMARY KEY, testo TEXT NOT NULL, importo NUMERIC(12,2) NOT NULL)')
                cursor.executemany('INSERT INTO controlled VALUES (%s,%s,%s)', expected)
        # Le connessioni del context manager psycopg2 restano aperte: chiusura esplicita.
        connection.close()
        destination = tmp_path / 'controlled.dump'
        result = backup_postgres(make_dsn(**parameters, dbname=source), destination)
        assert result['archive_index_verified'] and not result['restore_verified']
        env = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
        env.update(PGHOST=parameters['host'], PGUSER=parameters['user'], PGPASSWORD=parameters['password'])
        restore_result = subprocess.run(['/usr/lib/postgresql/16/bin/pg_restore', '--no-owner', '--exit-on-error', '--dbname', target, str(destination)],
                                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
        assert restore_result.returncode == 0, restore_result.stderr.decode('utf-8', errors='replace')
        with psycopg2.connect(**parameters, dbname=target) as restored:
            with restored.cursor() as cursor:
                cursor.execute('SELECT id,testo,importo::text FROM controlled ORDER BY id')
                assert cursor.fetchall() == expected
        restored.close()
    finally:
        for client in (connection, restored):
            if client is not None:
                client.close()
        # Nomi generati localmente, esclusivamente database controllati creati da questa prova.
        for name in reversed(created):
            with admin.cursor() as cursor:
                cursor.execute(f'DROP DATABASE "{name}"')
        admin.close()
