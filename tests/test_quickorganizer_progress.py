import pytest
from web.services.quickorganizer_progress import ImportProgress, ImportBusy, import_lock, read_import_progress


def test_progress_isolation_and_stale_worker(tmp_path):
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    old = ImportProgress(first, 'same-package')
    old.update('Documenti', 3, 10)
    assert read_import_progress(second, 'same-package') == {'status': 'idle'}
    current = ImportProgress(first, 'same-package')
    old.finish('complete')
    state = read_import_progress(first, 'same-package')
    assert state['status'] == 'running'
    assert state['runId'] == current.run_id
    current.finish('partial')
    assert read_import_progress(first, 'same-package')['status'] == 'partial'


def test_abandoned_progress_marked_interrupted(tmp_path):
    ImportProgress(tmp_path, 'abandoned')
    ImportProgress(tmp_path, 'new')
    assert read_import_progress(tmp_path, 'abandoned')['status'] == 'interrupted'


def test_lock_exception_release_and_tenant_isolation(tmp_path):
    path = tmp_path / 'first' / 'lock.sqlite'
    with pytest.raises(RuntimeError, match='failed import'):
        with import_lock(path):
            with pytest.raises(ImportBusy):
                with import_lock(path):
                    pytest.fail('Concurrent import entered')
            with import_lock(tmp_path / 'second' / 'lock.sqlite'):
                pass
            raise RuntimeError('failed import')
    with import_lock(path):
        pass
