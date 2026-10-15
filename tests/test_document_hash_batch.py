"""Le impronte richieste si leggono in gruppo senza modificare fonti o dati."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import g

from pct.registro_letture import Oggetto
from tests.test_document_source_registry_scope import registry_case as registry_case
from web.services import document_intelligence_runtime as sources


def observe_selects(registry, monkeypatch):
    original = registry.connection
    statements = []
    class ObservedConnection:
        def __init__(self, connection):
            self.connection = connection
        def execute(self, statement, parameters=()):
            statements.append((statement, parameters))
            return self.connection.execute(statement, parameters)
    @contextmanager
    def connection():
        with original() as opened:
            yield ObservedConnection(opened)
    monkeypatch.setattr(registry, 'connection', connection)
    return statements


def seed(registry, tenant, count):
    objects = [Oggetto(tipo='documento', oggetto_id=f'D{i}', nome=f'{i}.pdf',
        sha256=hashlib.sha256(f'{tenant}-clear-{i}'.encode()).hexdigest(),
        sha256_archivio=hashlib.sha256(f'archive-{i}'.encode()).hexdigest()) for i in range(count)]
    registry.registra_inventario(tenant, 'F1', objects)
    return objects


def test_requested_hashes_are_chunked_and_tenant_scoped(registry_case, monkeypatch):
    _, registry, _ = registry_case
    first = seed(registry, 'first', 501)
    seed(registry, 'second', 2)
    before = registry.oggetti('first', 'F1')
    expected = {obj.sha256_archivio: obj.sha256 for obj in first}
    statements = observe_selects(registry, monkeypatch)
    requested = [obj.sha256_archivio for obj in first] + [first[0].sha256_archivio.upper(), '', "x') OR 1=1 --"]
    assert registry.impronte_contenuto_per_archivi('first', 'documento', requested) == expected
    assert len(statements) == 2
    assert all(query.lstrip().upper().startswith('SELECT ') for query, _ in statements)
    assert all(parameters[0:2] == ('first', 'documento') for _, parameters in statements)
    statements.clear()
    assert registry.impronte_contenuto_per_archivi('first', 'documento', []) == {}
    assert not statements
    assert registry.impronta_contenuto('first', 'documento', '') == ''
    assert not statements
    assert registry.impronte_contenuto_per_archivi('missing', 'documento', [first[0].sha256_archivio]) == {}
    with pytest.raises(ValueError, match='Tipo'):
        registry.impronte_contenuto_per_archivi('first', 'not-a-type', [first[0].sha256_archivio])
    assert registry.oggetti('first', 'F1') == before


def test_conflicting_plaintext_hashes_are_explicit_and_preserved(registry_case):
    _, registry, _ = registry_case
    objects = seed(registry, 'first', 1)
    duplicate = Oggetto(tipo='documento', oggetto_id='D2', sha256=objects[0].sha256,
                       sha256_archivio=objects[0].sha256_archivio)
    registry.registra_inventario('first', 'F2', [duplicate])
    assert registry.impronte_contenuto_per_archivi('first', 'documento', [duplicate.sha256_archivio]) == {
        duplicate.sha256_archivio: duplicate.sha256}
    duplicate.sha256 = 'f' * 64
    registry.registra_inventario('first', 'F2', [duplicate])
    before = registry.oggetti('first', 'F2')
    with pytest.raises(ValueError, match='discordant'):
        registry.impronte_contenuto_per_archivi('first', 'documento', [duplicate.sha256_archivio])
    assert registry.oggetti('first', 'F2') == before


def test_collector_reuses_one_hash_query_for_requested_documents(registry_case, monkeypatch, tmp_path):
    app, registry, _ = registry_case
    objects = seed(registry, 'first', 21)
    documents = [SimpleNamespace(id=obj.oggetto_id, nome=obj.nome, percorso=obj.nome,
        hash_sha256=obj.sha256_archivio, hash_contenuto_sha256='', dimensione_bytes=10) for obj in objects]
    documents.append(SimpleNamespace(id='unknown', nome='unknown.pdf', percorso='unknown.pdf',
        hash_sha256='e' * 64, hash_contenuto_sha256='', dimensione_bytes=10))
    fascicolo = SimpleNamespace(id='F1', documenti=documents)
    monkeypatch.setattr(sources, 'get_fascicoli', lambda: SimpleNamespace(
        get=lambda _: fascicolo, documents_dir=tmp_path))
    from web.services import registro_letture_runtime, document_crypto
    monkeypatch.setattr(registro_letture_runtime, 'registro_corrente', lambda **_: registry)
    def forbidden(*_):
        raise AssertionError('La consultazione non deve aprire i documenti')
    monkeypatch.setattr(document_crypto, 'decrypt_doc', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    statements = observe_selects(registry, monkeypatch)
    with app.test_request_context('/'):
        g.controlled_tenant = 'first'
        result = sources.collect_document_ai_sources_for_fascicolo(
            'F1', tenant_id='first', allow_content_read=False)
        assert [source.sha256 for source in result] == [obj.sha256 for obj in objects] + ['e' * 64]
        assert all(source.content_bytes is None for source in result)
    assert len(statements) == 1


def test_preload_skips_known_fields_and_reuses_only_current_instance(registry_case, monkeypatch):
    _, registry, _ = registry_case
    from web.services.registro_letture_runtime import ImpronteContenuto
    objects = seed(registry, 'first', 2)
    requested = SimpleNamespace(hash_sha256=objects[0].sha256_archivio, hash_contenuto_sha256='')
    already_known = SimpleNamespace(hash_sha256=objects[1].sha256_archivio,
                                    hash_contenuto_sha256=objects[1].sha256)
    empty = SimpleNamespace(hash_sha256='', hash_contenuto_sha256='')
    statements = observe_selects(registry, monkeypatch)
    hashes = ImpronteContenuto(registry, 'first', 'F1')
    for _ in range(2):
        hashes.precarica([requested, already_known, empty])
        assert hashes.nota(requested) == objects[0].sha256
    hashes.precarica([])
    assert len(statements) == 1
    assert tuple(statements[0][1][2:]) == (objects[0].sha256_archivio,)
    fresh = ImpronteContenuto(registry, 'first', 'F1')
    fresh.precarica([requested])
    assert len(statements) == 2


def test_archive_hash_is_not_mistaken_for_plaintext_and_errors_propagate(registry_case, monkeypatch):
    _, registry, _ = registry_case
    from web.services.registro_letture_runtime import ImpronteContenuto
    registry.registra_inventario('first', 'F1', [
        Oggetto(tipo='documento', oggetto_id='opaque', sha256='a' * 64, sha256_archivio='a' * 64),
        Oggetto(tipo='documento', oggetto_id='unread', sha256='', sha256_archivio='b' * 64),
    ])
    assert registry.impronte_contenuto_per_archivi('first', 'documento', ['a' * 64, 'b' * 64]) == {}
    hashes = ImpronteContenuto(registry, 'first', 'F1')
    def unavailable():
        raise RuntimeError('SQL temporaneamente non disponibile')
    monkeypatch.setattr(registry, 'connection', unavailable)
    with pytest.raises(RuntimeError, match='SQL temporaneamente'):
        hashes.precarica([SimpleNamespace(hash_sha256='a' * 64)])
