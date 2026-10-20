"""Backup, ripresa e scritture SQL puntuali dei documenti con incassi."""
import pytest

from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella, parcella_revision
from tests.test_parcella_incassi_repository import invoice_receipts as invoice_receipts
from tests.test_parcella_incassi_repository import invoice_status_db as invoice_status_db
from tests.test_parcella_incassi_repository import _receive, _invoice
from uuid import uuid4


def test_explicit_preparation_keeps_financial_rows_and_installs_live_guards(invoice_receipts, tmp_path):
    from pct.parcella_incassi_preparation import prepare_invoice_receipts, financial_snapshot
    repo, cash, _, _ = invoice_receipts
    if repo.postgres:
        import re
        from pct.storage_postgres import CORE_POSTGRES_SCHEMA_SQL
        for table in ('_meta', 'audit_log'):
            statement = re.search(r'CREATE TABLE IF NOT EXISTS ' + table + r' \(.*?\);', CORE_POSTGRES_SCHEMA_SQL, re.S)
            assert statement is not None
            repo.db.conn.execute(statement.group(0))
        repo.db.raw_conn.commit()
    before = financial_snapshot(repo.db)
    result = prepare_invoice_receipts(repo.db, repo.tenant, tmp_path / 'receipt-preparation')
    assert result['changed'] and len(result['backup_sha256']) == 64
    assert financial_snapshot(repo.db) == before
    repo.require_prepared()
    assert prepare_invoice_receipts(repo.db, repo.tenant, tmp_path / 'unused-backup') == {'changed': False}
    assert not (tmp_path / 'unused-backup').exists()
    repo.db.conn.execute('DROP TRIGGER iusentra_live_parcelle ON parcelle' if repo.postgres
                         else 'DROP TRIGGER iusentra_live_parcelle_update')
    cash._finish(repo.db.conn)
    from pct.parcella_incassi_preparation import InvoiceReceiptsNotPrepared
    with pytest.raises(InvoiceReceiptsNotPrepared):
        repo.require_prepared()
    repaired = prepare_invoice_receipts(repo.db, repo.tenant, tmp_path / 'receipt-repair')
    assert repaired['changed'] and financial_snapshot(repo.db) == before
    repo.require_prepared()


def test_deleting_one_draft_preserves_concurrent_invoices_and_receipts(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    _receive(repo, manager, invoice_id, 40000)
    draft = manager.crea(id_cliente='cliente-1', voci=[VoceParcella(descrizione='Bozza controllata', prezzo_unitario=100)])
    stale = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    another = manager.crea(id_cliente='cliente-1', voci=[VoceParcella(descrizione='Altra bozza', prezzo_unitario=50)])
    stale.elimina(draft.id)
    fresh = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    assert fresh.get(draft.id) is None and fresh.get(another.id) is not None
    assert len(cash.load()) == 1 and repo.summary(invoice_id)['paid_cents'] == 40000


def test_stale_draft_delete_never_removes_a_concurrently_issued_invoice(invoice_receipts):
    from pct.fatturazione import ParcellaConcurrentUpdate
    repo, _, manager, _ = invoice_receipts
    draft = manager.crea(id_cliente='cliente-1', voci=[VoceParcella(descrizione='Bozza controllata', prezzo_unitario=100)])
    stale = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    manager.cambia_stato(draft.id, StatoParcella.EMESSA)
    with pytest.raises(ParcellaConcurrentUpdate):
        stale.elimina(draft.id)
    assert stale.get(draft.id) is not None
    assert _invoice(manager, draft.id).stato == StatoParcella.EMESSA


def test_delete_api_requires_the_revision_seen_in_the_open_sheet(invoice_receipts):
    from types import SimpleNamespace
    from web.services.react_fatturazione_scheda_azioni import elimina_bozza
    repo, _, manager, _ = invoice_receipts
    draft = manager.crea(id_cliente='cliente-1', voci=[VoceParcella(descrizione='Bozza controllata', prezzo_unitario=100)])
    seen = parcella_revision(draft)
    user = SimpleNamespace(id='operator', username='operator')
    fields = dict(get_fatturazione=lambda: GestioneFatturazione(manager.db_path, studio_db=repo.db),
        get_utenti=lambda: pytest.fail('Nessun audit di cancellazione senza cancellazione'),
        current_user=user, id_parcella=draft.id)
    assert elimina_bozza(**fields)[1] == 428
    manager.aggiorna(draft.id, note='Modifica concorrente', expected_revision=seen)
    assert elimina_bozza(**fields, expected_revision=seen)[1] == 409
    assert _invoice(manager, draft.id).note == 'Modifica concorrente'


def test_due_status_refresh_does_not_replace_the_invoice_archive(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    _receive(repo, manager, invoice_id, 40000)
    manager.aggiorna(invoice_id, data_scadenza='2020-01-01', expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    stale = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    another = manager.crea(id_cliente='cliente-1', voci=[VoceParcella(descrizione='Bozza concorrente', prezzo_unitario=50)])
    stale.aggiorna_scadute()
    fresh = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    assert fresh.get(another.id) is not None
    assert fresh.get(invoice_id).stato == StatoParcella.SCADUTA
    assert len(cash.load()) == 1


def test_proven_receipt_dates_and_amounts_cannot_be_rewritten_or_deleted(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    first = _receive(repo, manager, invoice_id, 40000)
    for statement in ('UPDATE parcella_incassi_proofs SET paid_on=? WHERE movement_id=?',
                      'DELETE FROM parcella_incassi_proofs WHERE paid_on=? AND movement_id=?'):
        with pytest.raises(Exception, match='immutabili'):
            repo.db.conn.execute(statement, ('2026-10-20', first['movement_id']))
        cash._finish(repo.db.conn, rollback=True)
    assert repo.summary(invoice_id)['paid_cents'] == 40000


def test_monthly_read_validates_only_the_cash_events_in_the_requested_period(invoice_receipts, monkeypatch):
    import pct.parcella_incassi_period as period
    repo, _, manager, invoice_id = invoice_receipts
    repo.register(invoice_id=invoice_id, amount_cents=40000, paid_on='2026-09-20', method='banca',
        note='Acconto precedente', command_key=str(uuid4()), expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    second = _receive(repo, manager, invoice_id, 60000)
    verified, original = [], period.verified_receipt
    def record(*fields):
        verified.append(fields[1])
        return original(*fields)
    monkeypatch.setattr(period, 'verified_receipt', record)
    fresh = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    assert fresh.incassi_periodo('2026-10-01', '2026-11-01') == {'importo': 600, 'movimenti': 1}
    assert verified == [second['movement_id']]


def test_financial_snapshot_hashes_row_values_on_both_backends(invoice_receipts):
    from pct.parcella_incassi_preparation import financial_snapshot
    repo, _, manager, invoice_id = invoice_receipts
    before = financial_snapshot(repo.db)
    manager.aggiorna(invoice_id, note='Variazione controllata del contenuto',
        expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    after = financial_snapshot(repo.db)
    assert before['parcelle']['records'] == after['parcelle']['records']
    assert before['parcelle']['sha256'] != after['parcelle']['sha256']
    assert before['prima_nota_records'] == after['prima_nota_records']
