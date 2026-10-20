"""Guardrail della ripresa: nessuna reimportazione di archivi già adottati."""
from types import SimpleNamespace

import pytest

from tools.prepare_invoice_receipts import adoption_status


@pytest.mark.parametrize('phase,state,expected', [
    (None, None, (False, None)),
    ('committed', ('a' * 64, '/backup/prima-nota/studio'), (True, None)),
    ('prepared', ('a' * 64, '/backup/prima-nota/studio'), (False, '/backup/prima-nota')),
    ('prepared', None, (False, None)),
])
def test_adoption_skips_committed_and_resumes_only_original_backup(monkeypatch, phase, state, expected):
    marker = None if phase is None else dict(phase=phase, tenant='studio', source_sha256='a' * 64)
    monkeypatch.setattr('tools.prepare_invoice_receipts.read_transition', lambda path: marker)
    monkeypatch.setattr('web.services.prima_nota_runtime._read_adoption', lambda *args, **kwargs: state)
    adopted, root = adoption_status(SimpleNamespace(conn=object()), 'cash.json', 'studio')
    assert adopted == expected[0]
    assert (root.as_posix() if root else None) == expected[1]


@pytest.mark.parametrize('marker,state', [
    (None, ('a' * 64, '/backup/studio')),
    (dict(phase='committed', tenant='studio', source_sha256='a' * 64), None),
    (dict(phase='committed', tenant='other', source_sha256='a' * 64), ('a' * 64, '/backup/studio')),
    (dict(phase='prepared', tenant='studio', source_sha256='a' * 64), ('b' * 64, '/backup/studio')),
    (dict(phase='committed', tenant='studio', source_sha256='a' * 64), ('a' * 64, '')),
])
def test_inconsistent_ownership_never_authorizes_import(monkeypatch, marker, state):
    monkeypatch.setattr('tools.prepare_invoice_receipts.read_transition', lambda path: marker)
    monkeypatch.setattr('web.services.prima_nota_runtime._read_adoption', lambda *args, **kwargs: state)
    with pytest.raises(RuntimeError):
        adoption_status(SimpleNamespace(conn=object()), 'cash.json', 'studio')


def test_preflight_opens_the_native_sqlite_backend_in_readonly_mode(tmp_path):
    from pct.storage import StudioDB
    from tools.prepare_invoice_receipts import open_database
    path = tmp_path / 'studio.db'
    owner = StudioDB(str(path))
    owner.chiudi()
    reader = open_database(SimpleNamespace(uses_sqlite=True, studio_db_path=str(path)), None, readonly=True)
    try:
        assert reader.conn.execute('PRAGMA query_only').fetchone()[0] == 1
        with pytest.raises(PermissionError):
            reader._conn_per_scrittura()
    finally:
        reader.chiudi()
