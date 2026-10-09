"""Provenienza OCR nei repository controllati, senza dati dello studio."""
from __future__ import annotations

import io
import os
from uuid import uuid4

import pytest

from pct.document_intelligence.extraction import ExtractionResult
from pct.document_intelligence.models import DocumentAIPageText
from pct.document_intelligence.repository import DocumentAIRepository, _pages_from_json
from pct.document_intelligence.service import DocumentAIService, IDENTITY_PROVENANCE_MARKER
from legal_ocr.motore.identita import RECUPERO_IDENTITA_VERSIONE


@pytest.fixture(params=['sqlite', 'postgres'])
def repo(request, tmp_path):
    if request.param == 'sqlite':
        repository = DocumentAIRepository.from_sqlite_db(tmp_path / 'identity.db', storage_root=tmp_path / 'blobs')
        try:
            yield repository
        finally:
            repository.close()
        return
    if os.environ.get('IDENTITY_SOURCES_TEST_POSTGRES') != '1':
        pytest.skip('Richiede PostgreSQL locale controllato')
    import psycopg2
    from psycopg2.extensions import make_dsn
    from psycopg2 import sql
    options = dict(host=os.environ.get('IDENTITY_SOURCES_TEST_PG_HOST', 'audit-postgres'),
                   dbname=os.environ.get('AUDIT_POSTGRES_DB', 'iusentra_audit'),
                   user=os.environ.get('AUDIT_POSTGRES_USER', 'iusentra_audit'),
                   password=os.environ['AUDIT_POSTGRES_PASSWORD'], connect_timeout=10)
    connection = psycopg2.connect(**options)
    schema = 'test_identity_sources_' + uuid4().hex
    repository = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        connection.commit()
        repository = DocumentAIRepository.from_postgres_dsn(
            make_dsn(**options, options=f'-csearch_path={schema},pg_catalog -clock_timeout=3000 -cstatement_timeout=10000'),
            storage_root=tmp_path / 'blobs')
        yield repository
    finally:
        if repository is not None:
            repository.close()
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        connection.commit()
        connection.close()


CONTEXT = {'skip_permission_check': True, 'user_id': 'identity-controlled-test'}
BODY = b'controlled original document'


def source(text, mode='recovery', page=1):
    return {'page_number': page, 'mode': mode, 'text': text}


def extraction(text='Testo storico conservato', *, sources=None, pages=None, warnings=None):
    return ExtractionResult(ok=True, text=text, extraction_engine='controlled-test',
                            pages=pages if pages is not None else [DocumentAIPageText(1, text)],
                            identity_sources=sources or [], warnings=warnings or [])


def upload(repo, monkeypatch, result):
    monkeypatch.setattr('pct.document_intelligence.service.extract_text_from_document', lambda *_a, **_k: result)
    file = io.BytesIO(BODY)
    file.filename, file.content_type = 'controlled.txt', 'text/plain'
    service = DocumentAIService(repo)
    record = service.upload_document_for_fascicolo('tenant-test', 'case-test', file, CONTEXT).document
    return service, record


def read(repo, record, version=None):
    return repo.get_extracted_text('tenant-test', 'case-test', record.id, version)


def reacquire(service, record, *, identity=True):
    return service.reacquire_existing_version('tenant-test', 'case-test', record.id, BODY, CONTEXT,
                                              identity_recovery=identity)


def test_legacy_pages_have_empty_sources_without_inventing_origin():
    pages = _pages_from_json('[{"page_number":1,"text":"storico"},{"page_number":null,"text":"senza pagina"}]')
    assert [(page.page_number, page.text, page.identity_sources) for page in pages] == [
        (1, 'storico', []), (None, 'senza pagina', [])]


def test_upload_and_generic_reacquire_roundtrip_sources(repo, monkeypatch):
    sources = [source('testo nativo', 'native'), source('candidato OCR', 'ocr'), source('dato riscontrato')]
    service, record = upload(repo, monkeypatch, extraction(sources=sources))
    archived = read(repo, record)
    assert archived.pages[0].identity_sources == sources
    if repo.backend_kind == 'postgresql':
        repo.close()  # Chiude la transazione di lettura prima del DDL idempotente di riapertura.
    # Un secondo repository rilegge SQL, non l'ExtractionResult in memoria.
    reopened = (DocumentAIRepository.from_postgres_dsn(repo.structured_db.dsn, storage_root=repo.storage_root)
                if repo.backend_kind == 'postgresql' else
                DocumentAIRepository.from_sqlite_db(repo.structured_db.db_path, storage_root=repo.storage_root))
    try:
        assert read(reopened, record).pages[0].identity_sources == sources
    finally:
        reopened.close()
    assert repo.get_extracted_text('altro-tenant', 'case-test', record.id, archived.version_id) is None
    next_sources = [source('solo fonte nuova', 'native', 2)]
    monkeypatch.setattr('pct.document_intelligence.service.extract_text_from_document',
                        lambda *_a, **_k: extraction('nuova pagina', sources=next_sources,
                                                   pages=[DocumentAIPageText(2, 'nuova pagina')]))
    renewed = reacquire(service, record, identity=False)
    assert read(repo, record).pages[0].identity_sources == next_sources
    assert read(repo, record, archived.version_id).pages[0].identity_sources == sources
    assert renewed.version_id != archived.version_id


def test_identity_reacquire_preserves_raw_and_all_qualified_sources_once(repo, monkeypatch):
    old = '  Storico integrale con spazi finali  '
    service, record = upload(repo, monkeypatch, extraction(old))
    qualified = [source('COGNOME ROSSI\nNOME MARIO'), source('Via del Test 4'), source('DATO NATIVO', 'native', 2)]
    fresh = extraction('rumore OCR da non adottare', sources=[source('rumore OCR da non adottare', 'ocr')] + qualified)
    calls = []
    def reader(*_a, **_k):
        calls.append(True)
        return fresh
    monkeypatch.setattr('pct.document_intelligence.service.extract_text_from_document', reader)
    renewed = reacquire(service, record)
    saved = read(repo, record)
    assert saved.text.startswith(old + '\n\n')
    assert saved.pages[0].text.startswith(old + '\n\n')
    assert 'rumore OCR da non adottare' not in saved.text
    assert saved.pages[0].identity_sources == [source(old, 'ocr')] + qualified[:2]
    assert saved.pages[1].page_number == 2 and saved.pages[1].identity_sources == qualified[2:]
    assert IDENTITY_PROVENANCE_MARKER in saved.warnings
    assert reacquire(service, record).version_id == renewed.version_id
    assert len(calls) == 1 and len(repo.list_versions('tenant-test', 'case-test', record.id)) == 2


@pytest.mark.parametrize('positive', [False, True])
def test_archive_without_pages_preserves_unknown_text_and_real_recovery_position(repo, monkeypatch, positive):
    old = 'Archivio senza informazioni sulla pagina'
    service, record = upload(repo, monkeypatch, extraction(old, pages=[]))
    sources = [source('Dato nuovo verificato', page=3)] if positive else []
    fresh = extraction('lettura generale insufficiente', pages=[], sources=sources)
    monkeypatch.setattr('pct.document_intelligence.service.extract_text_from_document', lambda *_a, **_k: fresh)
    result = reacquire(service, record)
    assert result.text.startswith(old)
    assert [page.page_number for page in result.pages] == ([3] if positive else [])
    assert 'lettura generale insufficiente' not in result.text
    assert not any(item['mode'] == 'native' for page in result.pages for item in page.identity_sources)
    assert reacquire(service, record).version_id == result.version_id


def test_old_recovery_marker_is_upgraded_once_preserving_existing_metadata(repo, monkeypatch):
    original_source = source('dato già verificato', 'native')
    old = extraction('dato già verificato', sources=[original_source], warnings=[
        f'Recupero identità {RECUPERO_IDENTITA_VERSIONE}: esito storico.'])
    service, record = upload(repo, monkeypatch, old)
    initial_id = record.current_version_id
    calls = []
    def reader(*_a, **_k):
        calls.append(True)
        return ExtractionResult(ok=False, text='', pages=[], extraction_engine='controlled-test', warnings=['nessun nuovo riscontro'])
    monkeypatch.setattr('pct.document_intelligence.service.extract_text_from_document', reader)
    renewed = reacquire(service, record)
    assert renewed.version_id != initial_id
    assert renewed.pages[0].identity_sources == [original_source]
    assert renewed.text == old.text
    assert reacquire(service, record).version_id == renewed.version_id and len(calls) == 1


def test_failed_sql_save_keeps_previous_sources_and_version(repo, monkeypatch):
    sources = [source('fonte originale', 'native')]
    service, record = upload(repo, monkeypatch, extraction(sources=sources))
    original_id = record.current_version_id
    save = repo.save_extracted_text
    monkeypatch.setattr('pct.document_intelligence.service.extract_text_from_document',
                        lambda *_a, **_k: extraction(sources=[source('fonte nuova')]))
    def fail(*_a, **_k):
        raise RuntimeError('errore SQL controllato')
    monkeypatch.setattr(repo, 'save_extracted_text', fail)
    with pytest.raises(RuntimeError, match='errore SQL controllato'):
        reacquire(service, record)
    assert repo.get_document('tenant-test', 'case-test', record.id).current_version_id == original_id
    assert read(repo, record).pages[0].identity_sources == sources
    assert len(repo.list_versions('tenant-test', 'case-test', record.id)) == 1
    monkeypatch.setattr(repo, 'save_extracted_text', save)
    assert reacquire(service, record).version_id != original_id
