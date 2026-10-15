"""Il repository SQL non consulta il mirror storico di un altro percorso."""
import json

import pytest

from pct.document_intelligence.repository import DocumentAIRepository
from tests.test_document_intelligence_repository_sql import _record
from tests.test_fascicoli_rinomina_sql_mirata import commit, rename_case  # noqa: F401


@pytest.mark.parametrize('populated', [False, True])
def test_sql_never_reads_or_adopts_historical_json(rename_case, monkeypatch, tmp_path, populated):
    _, backend, _, _ = rename_case
    backend.conn.execute('CREATE TABLE _meta (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL)')
    commit(backend)
    root = tmp_path / 'documenti-ai'
    root.mkdir()
    mirror = root / 'documenti_ai.json'
    historical = _record(id='historical', fascicolo_id='F1', tenant_id='other-studio').to_dict()
    original = json.dumps({'documents': [historical]}).encode()
    mirror.write_bytes(original)
    repository = DocumentAIRepository(mirror, root, structured_db=backend)
    if populated:
        repository.create_document_record(_record(id='current', fascicolo_id='F1'))

    def forbidden(*args, **kwargs):
        raise AssertionError('Il backend SQL non deve aprire il JSON storico')

    monkeypatch.setattr(DocumentAIRepository, '_load_json', forbidden)
    reopened = DocumentAIRepository(mirror, root, structured_db=backend)
    expected = ['current'] if populated else []
    assert [row.id for row in reopened.list_documents('tenant-a', 'F1')] == expected
    assert reopened.list_documents('other-studio', 'F1') == []
    assert reopened.storage_stats('tenant-a', 'F1')['documents'] == len(expected)
    assert mirror.read_bytes() == original


def test_explicit_json_repository_keeps_its_own_records(tmp_path):
    mirror = tmp_path / 'documenti_ai.json'
    record = _record(id='legacy-json')
    mirror.write_text(json.dumps({'documents': [record.to_dict()]}), encoding='utf-8')
    repository = DocumentAIRepository(mirror, tmp_path)
    assert repository.backend_kind == 'json'
    assert [row.id for row in repository.list_documents('tenant-a', 'fas-1')] == ['legacy-json']
    assert repository.list_documents('other-studio', 'fas-1') == []
