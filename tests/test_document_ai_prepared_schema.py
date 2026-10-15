"""La consultazione usa lo schema predisposto senza DDL o commit."""
import pytest
from pct.document_intelligence.repository import DocumentAIRepository
from tests.test_document_intelligence_repository_sql import _record
from tests.test_fascicoli_rinomina_sql_mirata import commit, rename_case as rename_case_fixture

rename_case = rename_case_fixture


def test_prepared_sql_consultation_does_not_initialize(rename_case, monkeypatch, tmp_path):
    _, backend, _, _ = rename_case
    backend.conn.execute('CREATE TABLE _meta (chiave TEXT PRIMARY KEY,valore TEXT NOT NULL)')
    commit(backend)
    root = tmp_path / 'ai'
    prepared = DocumentAIRepository(root / 'legacy.json', root, structured_db=backend)
    prepared.create_document_record(_record(id='retained'))
    def forbidden(*args, **kwargs):
        raise AssertionError('La consultazione non deve inizializzare né committare')
    monkeypatch.setattr(DocumentAIRepository, '_ensure_sql_schema', forbidden)
    monkeypatch.setattr(DocumentAIRepository, '_commit', forbidden)
    import pct.operational_live as live
    monkeypatch.setattr(live, 'ensure_live_schema', forbidden)
    from types import SimpleNamespace
    statements = []
    class ReadConnection:
        def execute(self, sql, params=()):
            assert sql.lstrip().upper().startswith('SELECT ')
            statements.append(sql)
            return backend.conn.execute(sql, params)
        commit = forbidden
        executescript = forbidden
    guarded = SimpleNamespace(backend_kind=prepared.backend_kind, conn=ReadConnection(),
                              raw_conn=SimpleNamespace(commit=forbidden, cursor=forbidden))
    reader = DocumentAIRepository(root / 'legacy.json', root, structured_db=guarded, initialize_schema=False)
    assert reader.get_document('tenant-a','fas-1','retained') is not None
    assert len(statements) == 3


def test_unprepared_consultation_is_explicit_and_does_not_create_storage(rename_case, tmp_path):
    from pct.document_intelligence.repository import DocumentAISchemaNotPrepared
    _, backend, _, _ = rename_case
    root = tmp_path / 'not-created'
    with pytest.raises(DocumentAISchemaNotPrepared, match='preparazione SQL governata'):
        DocumentAIRepository(root / 'legacy.json', root, structured_db=backend, initialize_schema=False)
    assert not root.exists()


def test_explicit_preparation_preserves_records_and_repeated_attempt(rename_case, tmp_path, monkeypatch):
    from pct.document_intelligence.preparation import prepare_document_ai_schema
    from pct.document_intelligence.repository import DocumentAISchemaNotPrepared
    _, backend, _, _ = rename_case
    backend.conn.execute('CREATE TABLE _meta (chiave TEXT PRIMARY KEY,valore TEXT NOT NULL)')
    commit(backend)
    anchor = tmp_path / 'fascicoli' / 'fascicoli.json'
    backup_dir = tmp_path / 'backup'
    assert prepare_document_ai_schema(backend, anchor, backup_dir=backup_dir)
    prepared = DocumentAIRepository.from_fascicoli_db(anchor, structured_db=backend, initialize_schema=False)
    prepared.create_document_record(_record(id='retained'))
    copies = list(backup_dir.glob('*.db'))
    if prepared.backend_kind == 'sqlite':
        assert len(copies) == 1
        import sqlite3
        with sqlite3.connect(copies[0]) as backup:
            assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert backup.execute('SELECT COUNT(*) FROM fascicoli').fetchone()[0] == 2
    else:
        assert copies == []
    def forbidden(*args, **kwargs):
        raise AssertionError('La preparazione già confermata non va ripetuta')
    with monkeypatch.context() as patch:
        patch.setattr(DocumentAIRepository, '_ensure_sql_schema', forbidden)
        assert not prepare_document_ai_schema(backend, anchor, backup_dir=backup_dir)
    assert list(backup_dir.glob('*.db')) == copies
    assert prepared.get_document('tenant-a','fas-1','retained').id == 'retained'
    assert prepared.get_document('another-tenant','fas-1','retained') is None
    backend.conn.execute("UPDATE document_ai_schema_readiness SET signature='obsolete'")
    commit(backend)
    with pytest.raises(DocumentAISchemaNotPrepared):
        DocumentAIRepository.from_fascicoli_db(anchor, structured_db=backend, initialize_schema=False)
    assert prepare_document_ai_schema(backend, anchor, backup_dir=backup_dir)
    assert DocumentAIRepository.from_fascicoli_db(anchor, structured_db=backend, initialize_schema=False).get_document('tenant-a','fas-1','retained').id == 'retained'


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_runtime_command_uses_prepared_repository_without_initialization(rename_case, monkeypatch, tmp_path, method):
    from flask import Flask
    from web.services import document_intelligence_runtime as runtime
    from pct.document_intelligence.preparation import prepare_document_ai_schema
    manager, backend, _, _ = rename_case
    backend.conn.execute('CREATE TABLE _meta (chiave TEXT PRIMARY KEY,valore TEXT NOT NULL)')
    commit(backend)
    anchor = str(tmp_path / 'fascicoli' / 'fascicoli.json')
    prepare_document_ai_schema(backend, anchor, backup_dir=tmp_path / 'backup')
    monkeypatch.setattr(runtime, 'fascicoli_db_path', lambda: anchor)
    monkeypatch.setattr(runtime, 'get_request_studio_db', lambda _: backend)
    monkeypatch.setattr(runtime, 'document_ai_tenant_id', lambda: 'tenant-a')
    monkeypatch.setattr(runtime, 'get_fascicoli', lambda: manager)
    def forbidden(*args, **kwargs):
        raise AssertionError('Il comando non deve preparare lo schema')
    monkeypatch.setattr(DocumentAIRepository, '_ensure_sql_schema', forbidden)
    app = Flask(__name__)
    with app.test_request_context('/catalogo', method=method):
        service = runtime.build_document_ai_service()
        assert service.repository.backend_kind == ('postgresql' if getattr(backend, 'backend_kind', '') == 'postgresql' else 'sqlite')
        assert service.repository.list_documents('tenant-a','F1') == []


def test_schema_error_has_explicit_service_response():
    from flask import Flask
    from web.blueprints.api_v1_documenti_ai import _handle_error
    from pct.document_intelligence.repository import DocumentAISchemaNotPrepared
    with Flask(__name__).app_context():
        response, status = _handle_error(DocumentAISchemaNotPrepared('Schema documentale non preparato.'))
        assert status == 503
        assert response.get_json()['code'] == 'document_ai_schema_not_prepared'
        assert response.get_json()['mock_fallback'] is False


def test_new_tenant_is_prepared_before_first_document_get(tmp_path):
    from pct.tenant import GestioneTenant
    from pct.storage import StudioDB
    registry = GestioneTenant(registry_path=str(tmp_path / 'tenants.json'))
    studio = registry.crea('Studio controllato schema', 'controlled-schema')
    paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
    backend = StudioDB(paths['STUDIO_DB'], initialize_schema=False)
    try:
        reader = DocumentAIRepository.from_fascicoli_db(paths['FASCICOLI_DB'], structured_db=backend, initialize_schema=False)
        assert reader.list_documents(studio.slug, 'not-yet-created') == []
        triggers = {row[0] for row in backend.conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        assert 'iusentra_live_fascicolo_documenti_ai_update' in triggers
    finally:
        backend.chiudi()


def test_preparation_command_reuses_tenant_owner_and_is_repeatable(tmp_path, monkeypatch, capsys):
    from pct.tenant import GestioneTenant
    from pct.storage import StudioDB
    from tools.prepare_document_ai_schema import main
    import sys
    registry_path = tmp_path / 'tenants.json'
    registry = GestioneTenant(registry_path=str(registry_path))
    studio = registry.crea('Studio comando controllato', 'controlled-command')
    paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
    backend = StudioDB(paths['STUDIO_DB'], initialize_schema=False)
    try:
        backend.conn.execute("UPDATE document_ai_schema_readiness SET signature='obsolete'")
        backend.conn.commit()
    finally:
        backend.chiudi()
    monkeypatch.setattr(sys, 'argv', ['prepare', '--tenant-registry', str(registry_path),
                                    '--backup-dir', str(tmp_path / 'command-backup')])
    main()
    output = capsys.readouterr().out
    assert '"changed": true' in output
    main()
    assert '"changed": false' in capsys.readouterr().out
    assert len(list((tmp_path / 'command-backup').glob('*/*.db'))) == 1


def test_sqlite_backup_timeout_does_not_prepare_or_change_source(tmp_path, monkeypatch):
    from pct.storage import StudioDB
    from pct.document_intelligence import preparation
    import sqlite3
    with sqlite3.connect(tmp_path / 'studio.db'):
        pass
    backend = StudioDB(str(tmp_path / 'studio.db'), initialize_schema=False)
    try:
        backend.conn.execute('CREATE TABLE controlled_source(id TEXT PRIMARY KEY, value TEXT)')
        backend.conn.execute("INSERT INTO controlled_source VALUES ('kept','original')")
        backend.conn.commit()
        ticks = iter((0, 1801))
        with monkeypatch.context() as patch:
            patch.setattr(preparation.time, 'monotonic', lambda: next(ticks, 1801))
            with pytest.raises(TimeoutError, match='30 minuti'):
                preparation.prepare_document_ai_schema(backend, tmp_path / 'fascicoli.json',
                                                       backup_dir=tmp_path / 'backup')
        assert backend.conn.execute('SELECT value FROM controlled_source').fetchone()[0] == 'original'
        assert backend.conn.execute("SELECT name FROM sqlite_master WHERE name='document_ai_schema_readiness'").fetchone() is None
        assert list((tmp_path / 'backup').glob('*.pending.db'))
    finally:
        backend.chiudi()
