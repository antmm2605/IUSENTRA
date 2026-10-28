from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from time import sleep
from types import SimpleNamespace
import pytest

from pct.document_intelligence.index_retry import index_source
from pct.document_intelligence.sources import source_from_uploaded_document


def test_two_workers_with_stale_snapshots_create_one_document(tmp_path: Path):
    source = source_from_uploaded_document(
        tenant_id="studio", fascicolo_id="fascicolo", document_id="source",
        filename="atto.txt", content=b"same content", source_type="documenti_fascicolo",
        mime_type="text/plain", metadata={},
    )
    class Service:
        def __init__(self):
            self.repository = SimpleNamespace(storage_root=tmp_path, get_document=lambda *args: self.rows[0])
            self.rows = []
            self.guard = Lock()
            self.uploads = 0

        def list_fascicolo_documents(self, tenant_id, fascicolo_id, context):
            with self.guard:
                return list(self.rows)

        def upload_document_bytes_for_fascicolo(self, **kwargs):
            sleep(0.05)
            record = SimpleNamespace(id="new", tenant_id=source.tenant_id,
                fascicolo_id=source.fascicolo_id, sha256=source.sha256,
                current_version_id="v1", updated_at="now")
            with self.guard:
                self.uploads += 1
                self.rows.append(record)
            return SimpleNamespace(document=record)

        def reacquire_existing_version(self, tenant_id, fascicolo_id, document_id, content, context):
            assert document_id == "new"

    service = Service()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(index_source, service, source, [], {}) for _ in range(2)]
        assert [future.result().id for future in futures] == ["new", "new"]
    assert service.uploads == 1
    assert len(service.rows) == 1


def test_json_backend_refreshes_stale_repository_after_lock(tmp_path: Path):
    source = source_from_uploaded_document(
        tenant_id="studio", fascicolo_id="fascicolo", document_id="source",
        filename="atto.txt", content=b"same content", source_type="documenti_fascicolo",
        mime_type="text/plain", metadata={},
    )
    record = SimpleNamespace(id="existing", tenant_id="studio", fascicolo_id="fascicolo",
                             sha256=source.sha256, current_version_id="v1", updated_at="now")
    class Repository:
        backend_kind = "json"
        storage_root = tmp_path
        json_path = tmp_path / "state.json"
        _data = []
        def _load_json(self):
            return [record]
        def get_document(self, *args):
            return self._data[0]
    class Service:
        repository = Repository()
        def list_fascicolo_documents(self, *args):
            return self.repository._data
        def reacquire_existing_version(self, *args):
            pass
        def upload_document_bytes_for_fascicolo(self, **kwargs):
            raise AssertionError("a stale JSON cache must not create a document")
    assert index_source(Service(), source, [], {}).id == "existing"


def test_invalid_json_is_not_replaced_as_empty(tmp_path: Path):
    source = source_from_uploaded_document(
        tenant_id="studio", fascicolo_id="fascicolo", document_id="source",
        filename="atto.txt", content=b"same content", source_type="documenti_fascicolo",
        mime_type="text/plain", metadata={},
    )
    path = tmp_path / "damaged.json"
    path.write_text("{broken", encoding="utf-8")
    service = SimpleNamespace(repository=SimpleNamespace(
        backend_kind="json", storage_root=tmp_path, json_path=path))
    with pytest.raises(ValueError):
        index_source(service, source, [], {})
    assert path.read_text(encoding="utf-8") == "{broken"
