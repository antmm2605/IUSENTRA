import sqlite3

import pytest
from flask import g

from tests.test_studio_readonly_request import studies as studies
from web.services.pec_audit_query_connection import pec_audit_query_connection


def test_lettore_analisi_pec_non_crea_non_scrive_e_rispetta_studio(studies):
    app, owners, _, root = studies
    owner = owners[0]
    path = root / 'tenants' / owner.slug / 'email' / 'pec_audit.sqlite'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE controlled_source (id TEXT PRIMARY KEY)')
        connection.execute("INSERT INTO controlled_source VALUES ('controlled')")
    before = path.read_bytes()
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owner
        g.data_paths = {'PEC_AUDIT_DB': str(path)}
        with pec_audit_query_connection(tenant=owner.slug) as connection:
            assert connection.execute('SELECT id FROM controlled_source').fetchone()[0] == 'controlled'
            with pytest.raises(sqlite3.OperationalError):
                connection.execute('DELETE FROM controlled_source')
        with pytest.raises(PermissionError):
            with pec_audit_query_connection(tenant=owners[1].slug):
                pytest.fail('Studio discordante')
    assert path.read_bytes() == before


def test_analisi_pec_assenti_non_diventano_zero_risultati(studies):
    app, owners, _, root = studies
    owner = owners[0]
    path = root / 'tenants' / owner.slug / 'email' / 'pec_audit.sqlite'
    with app.test_request_context('/api/assistente/chat'):
        g.tenant = owner
        g.data_paths = {'PEC_AUDIT_DB': str(path)}
        with pytest.raises(RuntimeError, match='nessuna inizializzazione'):
            with pec_audit_query_connection(tenant=owner.slug):
                pytest.fail('Archivio assente')
    assert not path.exists()
