"""Le sole consultazioni riusano le impronte SQL senza preparare il registro."""
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, g

from pct.registro_letture import Oggetto, RegistroLetture
from tests.test_condivisioni_sql_repository import SQLFactory
from web.services import document_intelligence_runtime as sources
from web.services import registro_letture_runtime as registry_runtime


@pytest.fixture(params=['sqlite', 'postgresql'])
def registry_case(request, tmp_path, monkeypatch):
    if request.param == 'postgresql' and not os.environ.get('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato')
    factory = SQLFactory(request.param)
    dsn = ''
    if request.param == 'postgresql':
        from psycopg2.extensions import make_dsn
        dsn = make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}')
    path = tmp_path / 'registry.db'
    registry = RegistroLetture(path, postgres_dsn=dsn)
    app = Flask(__name__)
    app.config['REGISTRO_LETTURE_DB'] = str(path)
    monkeypatch.setattr(registry_runtime, '_dsn_postgres', lambda *_: dsn)
    monkeypatch.setattr(registry_runtime, 'tenant_corrente', lambda: g.controlled_tenant)
    try:
        yield app, registry, path
    finally:
        registry.close()
        factory.close()


def configure_source(monkeypatch, tmp_path, *, archive_hash):
    file = tmp_path / 'controlled.pdf'
    file.write_bytes(b'controlled encrypted bytes')
    document = SimpleNamespace(id='D1', nome='controlled.pdf', percorso=file.name,
                               dimensione_bytes=file.stat().st_size, hash_sha256=archive_hash,
                               hash_contenuto_sha256='')
    fascicolo = SimpleNamespace(id='F1', documenti=[document])
    monkeypatch.setattr(sources, 'get_fascicoli', lambda: SimpleNamespace(
        get=lambda _: fascicolo, documents_dir=tmp_path))
    return document, file


def observe_registry_open(monkeypatch):
    calls = []
    def open_registry(*args, **kwargs):
        calls.append(bool(kwargs.get('read_only', False)))
        return RegistroLetture(*args, **kwargs)
    monkeypatch.setattr(registry_runtime, 'RegistroLetture', open_registry)
    return calls


def test_consultation_reuses_plaintext_hash_without_ddl_or_decryption(registry_case, monkeypatch, tmp_path):
    app, registry, _ = registry_case
    archive_hash, plain_hash, other_hash = 'a' * 64, 'b' * 64, 'c' * 64
    document, file = configure_source(monkeypatch, tmp_path, archive_hash=archive_hash)
    for tenant, digest in [('first', plain_hash), ('second', other_hash)]:
        registry.registra_inventario(tenant, 'F1', [Oggetto(tipo='documento', oggetto_id='D1',
            nome=document.nome, sha256=digest, sha256_archivio=archive_hash)])
    before = [registry.oggetti(tenant, 'F1') for tenant in ('first', 'second')]
    calls = observe_registry_open(monkeypatch)
    from web.services import document_crypto
    def forbidden(*_):
        raise AssertionError('La consultazione non deve aprire o decifrare la fonte')
    monkeypatch.setattr(document_crypto, 'decrypt_doc', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    for tenant, digest in [('first', plain_hash), ('second', other_hash)]:
        with app.test_request_context('/'):
            g.controlled_tenant = tenant
            for _ in range(2):
                result = sources.collect_document_ai_sources_for_fascicolo(
                    'F1', tenant_id=tenant, allow_content_read=False)
                assert len(result) == 1 and result[0].sha256 == digest
                assert result[0].content_bytes is None and result[0].content_path == file
    assert calls == [True, True]
    assert [registry.oggetti(tenant, 'F1') for tenant in ('first', 'second')] == before


def test_acquisition_still_learns_the_new_plaintext_hash(registry_case, monkeypatch, tmp_path):
    app, registry, _ = registry_case
    archive_hash = 'd' * 64
    document, _ = configure_source(monkeypatch, tmp_path, archive_hash=archive_hash)
    registry.registra_inventario('first', 'F1', [Oggetto(tipo='documento', oggetto_id='D1',
        nome=document.nome, sha256_archivio=archive_hash)])
    plaintext = b'controlled original source, no personal data'
    digest = hashlib.sha256(plaintext).hexdigest()
    from web.services import document_crypto
    monkeypatch.setattr(document_crypto, 'decrypt_doc', lambda _: plaintext)
    calls = observe_registry_open(monkeypatch)
    with app.test_request_context('/'):
        g.controlled_tenant = 'first'
        result = sources.collect_document_ai_sources_for_fascicolo('F1', tenant_id='first')
        assert result[0].sha256 == digest and result[0].content_bytes == plaintext
    assert calls == [False]
    assert registry.impronta_contenuto('first', 'documento', archive_hash) == digest
    assert registry.impronta_contenuto('second', 'documento', archive_hash) == ''


def test_missing_registry_consultation_does_not_create_a_database(monkeypatch, tmp_path):
    path = tmp_path / 'not-provisioned' / 'registry.db'
    app = Flask(__name__)
    app.config['REGISTRO_LETTURE_DB'] = str(path)
    monkeypatch.setattr(registry_runtime, '_dsn_postgres', lambda *_: '')
    monkeypatch.setattr(registry_runtime, 'tenant_corrente', lambda: 'first')
    configure_source(monkeypatch, tmp_path, archive_hash='e' * 64)
    calls = observe_registry_open(monkeypatch)
    with app.test_request_context('/'):
        result = sources.collect_document_ai_sources_for_fascicolo(
            'F1', tenant_id='first', allow_content_read=False)
        assert len(result) == 1 and result[0].content_bytes is None
    assert calls == [True]
    assert not path.exists() and not path.parent.exists()
