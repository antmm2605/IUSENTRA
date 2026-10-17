import importlib.util
import sqlite3
from pathlib import Path

import pytest

from tests.test_pec_deposit_query_repository import add_receipt
from tests.test_studio_readonly_request import studies as studies


def test_backup_nativo_e_worker_solo_su_eventi_pendenti(studies, tmp_path, monkeypatch):
    from pct.pec_deposit_query_repository import PecDepositQueryRepository
    from web.services.deposit_query_events_runtime import resume_deposit_query_events

    app, owners, _, root = studies
    app.secret_key = 'controlled-deposit-worker'
    path = root / 'tenants' / owners[0].slug / 'email' / 'pec_audit.sqlite'
    schema = (Path(__file__).resolve().parents[1] / 'pct/sql/20260521_pec_audit_pipeline.sql').read_text(encoding='utf-8')
    spec = importlib.util.spec_from_file_location('deposit_query_migration_controlled',
        Path(__file__).resolve().parents[1] / 'scripts/mailbox/rebuild-deposit-query-index.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(schema)
        add_receipt(conn, 'registry', 'accettazione_deposito')
        conn.commit()
        before = conn.execute('SELECT mime_sha256,original_mime FROM pec_messages').fetchone()
        result = module.rebuild(conn, tenant='study-a', path=path, destination=tmp_path / 'receipt-backup')
        assert result['phase'] == 'COMPLETED'
        assert len(result['backup_sha256']) == 64
        conn.execute("UPDATE pec_validation_reports SET event_type='altro' WHERE id='registry-report'")
        conn.commit()
    monkeypatch.setattr('pct.pec_pipeline.PecAuditRepository.__init__', lambda *a, **kw: pytest.fail('Pipeline PEC non richiesta'))
    assert resume_deposit_query_events(app, limit=1) == dict(delivered=1, failed=0, not_migrated=1)
    assert resume_deposit_query_events(app, limit=1)['delivered'] == 0
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        assert PecDepositQueryRepository(conn, 'study-a').list_page(state='ACCETTATO_CANCELLERIA')['rows'] == []
        assert tuple(conn.execute('SELECT mime_sha256,original_mime FROM pec_messages').fetchone()) == tuple(before)
    assert not (root / 'tenants' / owners[1].slug / 'email' / 'pec_audit.sqlite').exists()
