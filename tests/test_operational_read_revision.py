from contextlib import closing
from types import SimpleNamespace

import pytest
from flask import Flask, g

from pct.operational_live import ensure_live_schema, read_tenant_live_revisions
from pct.registro_letture import Oggetto
from tests.test_archivio_fatti_request_snapshot import snapshot_registry
from tests.test_fascicoli_rinomina_sql_mirata import rename_case, commit
from web.services.operational_read_revision import (
    read_authorized_revision_snapshot, with_confirmed_read_revision,
)


@pytest.mark.parametrize('change', ['none', 'source', 'tenant', 'user', 'backend'])
def test_proof_covers_only_an_unchanged_read_and_owner(snapshot_registry, change):
    registry = snapshot_registry
    registry.registra_inventario('studio', 'F1', [Oggetto(tipo='documento', oggetto_id='D1')])
    context = ['a' * 64]
    def read():
        connection = registry.connection()
        with (connection if registry.backend_kind == 'postgres' else closing(connection)) as conn:
            revisions = read_tenant_live_revisions(conn, 'letture', 'studio', {'fascicoli'},
                                                  postgres=registry.backend_kind == 'postgres')
        return {'context': context[0], 'revisions': revisions}
    def build():
        if change == 'source':
            registry.registra_inventario('studio', 'F1', [
                Oggetto(tipo='documento', oggetto_id='D1'), Oggetto(tipo='documento', oggetto_id='D2')])
        elif change != 'none':
            context[0] = 'b' * 64
        return {'fascicolo': {'id': 'F1'}, 'documents': ['originale']}
    with Flask(__name__).app_context():
        payload = with_confirmed_read_revision(build, read)
    assert payload['documents'] == ['originale']
    assert payload['fascicolo']['id'] == 'F1'
    if change == 'none':
        assert payload['readRevision'] == read()['revisions']
        assert payload['readRevisionContext'] == 'a' * 64
    else:
        assert payload['readRevision'] is None and payload['readRevisionContext'] is None


@pytest.mark.parametrize('phase', ['first', 'last', 'empty'])
def test_missing_or_failed_revision_is_never_a_confirmed_proof(phase):
    calls = []
    def read():
        calls.append(1)
        if (phase == 'first' and len(calls) == 1) or (phase == 'last' and len(calls) == 2):
            raise RuntimeError('SQL counter unavailable')
        return {'context': 'a' * 64, 'revisions': {} if phase == 'empty' else {'fascicoli': 3}}
    with Flask(__name__).app_context():
        result = with_confirmed_read_revision(lambda: {'value': 'source value'}, read)
    assert result == {'value': 'source value', 'readRevision': None, 'readRevisionContext': None, 'readFailed': False}


def test_projection_failure_propagates_without_confirming_a_read():
    def broken():
        raise ValueError('projection failed')
    with Flask(__name__).app_context(), pytest.raises(ValueError, match='projection failed'):
        with_confirmed_read_revision(broken, lambda: {'context': 'a' * 64, 'revisions': {'fascicoli': 3}})


def test_the_before_snapshot_cannot_be_changed_through_a_shared_dictionary():
    snapshot = {'context': 'a' * 64, 'revisions': {'fascicoli': 3}}
    def build():
        snapshot['revisions']['fascicoli'] = 4
        return {'value': 'fresh source'}
    with Flask(__name__).app_context():
        result = with_confirmed_read_revision(build, lambda: snapshot)
    assert result['readRevision'] is None
    assert result['value'] == 'fresh source'


def test_a_handled_repository_error_cannot_confirm_empty_values_as_a_fresh_view():
    from web.services.react_fascicoli_bridge import _safe
    def failed_repository():
        raise RuntimeError('controlled SQL failure')
    with Flask(__name__).app_context():
        result = with_confirmed_read_revision(
            lambda: {'count': _safe('controlled', failed_repository, 0)},
            lambda: {'context': 'a' * 64, 'revisions': {'fascicoli': 3}},
        )
        # A later independent successful read is not poisoned by the failure.
        recovered = with_confirmed_read_revision(
            lambda: {'count': _safe('controlled', lambda: 4, 0)},
            lambda: {'context': 'a' * 64, 'revisions': {'fascicoli': 3}},
        )
    assert result['readFailed'] and result['readRevision'] is None
    assert recovered['readFailed'] is False and recovered['count'] == 4
    assert recovered['readRevision'] == {'fascicoli': 3}


def test_revisions_are_permission_filtered_and_bound_to_the_current_owner(rename_case, monkeypatch):
    _, backend, _, _ = rename_case
    backend.conn.execute('CREATE TABLE _meta(chiave TEXT PRIMARY KEY,valore TEXT)')
    backend_kind = getattr(backend, 'backend_kind', 'sqlite')
    ensure_live_schema(backend.conn, postgres=backend_kind == 'postgresql')
    commit(backend)
    requested = []
    def database(_):
        g._runtime_studio_db_key = ('studio', backend_kind, g.source)
        return backend
    def vertical(domains):
        requested.append(domains)
        return {'fascicoli': 3, 'privacy': 99}
    monkeypatch.setattr('web.services.storage_runtime.get_request_studio_db', database)
    monkeypatch.setattr('web.services.tenant_paths.tenant_data_path', lambda *_, **__: 'controlled')
    monkeypatch.setattr('web.services.operational_live_sources.read_vertical_revisions', vertical)
    user = SimpleNamespace(id='U1', username='lawyer', ha_permesso=lambda permission: permission == 'fascicoli.leggi')
    with Flask(__name__).test_request_context('/'):
        g.tenant = SimpleNamespace(slug='studio')
        g.source = 'first'
        first = read_authorized_revision_snapshot(user)
        assert first['revisions'] == {'fascicoli': 3}
        assert read_authorized_revision_snapshot(user) == first
        user.username = 'another'
        assert read_authorized_revision_snapshot(user)['context'] != first['context']
        user.username = 'lawyer'
        g.tenant.slug = 'another-studio'
        assert read_authorized_revision_snapshot(user)['context'] != first['context']
        g.tenant.slug = 'studio'
        g.source = 'second'
        assert read_authorized_revision_snapshot(user)['context'] != first['context']
    assert all(domains == {'fascicoli'} for domains in requested)
