"""Fonti vere SQL controllate e unica consegna cassa/outbox, SQLite e PostgreSQL."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import re

import pytest

from pct.pagamenti import GestionePagamenti
from pct.payment_evidence import stripe_facts
from pct.payment_confirmations import ingest, deliver, for_invoice, TABLE, EVENT
from tests.test_parcella_incassi_repository import invoice_receipts as invoice_receipts
from tests.test_parcella_incassi_repository import invoice_status_db as invoice_status_db
from tests.test_parcella_incassi_repository import _receive


@pytest.fixture
def confirmed_payment(invoice_receipts, tmp_path):
    from pct.parcella_incassi_preparation import prepare_invoice_receipts
    repo, cash, manager, invoice_id = invoice_receipts
    if repo.postgres:
        from pct.storage_postgres import CORE_POSTGRES_SCHEMA_SQL
        for table in ('_meta', 'audit_log', 'payment_config'):
            statement = re.search(r'CREATE TABLE IF NOT EXISTS ' + table + r' \(.*?\);', CORE_POSTGRES_SCHEMA_SQL, re.S)
            assert statement is not None
            repo.db.conn.execute(statement.group(0))
        cash._finish(repo.db.conn)
    prepare_invoice_receipts(repo.db, repo.tenant, tmp_path / 'prepared-backup')
    _receive(repo, manager, invoice_id, 40000)
    gp = GestionePagamenti(str(tmp_path / 'links'), studio_db=repo.db)
    link = gp.crea_link(invoice_id, 'cliente-1', 600, 'CONTROLLED-BALANCE')
    facts = stripe_facts(dict(id='cs_controlled', payment_status='paid', amount_total=60000, currency='eur',
        metadata={'link_id': link.id, 'parcella': invoice_id}), link,
        verified_event_created=int(datetime(2026, 10, 19, 12, tzinfo=timezone.utc).timestamp()),
        observed_at='2026-10-20T06:00:00Z', verified_event_id='evt_controlled',
        verified_event_type='checkout.session.completed')
    assert facts.paid_on == '2026-10-19'
    return repo, cash, gp, link, facts


def test_partial_manual_then_verified_balance_is_one_atomic_cash_fact(confirmed_payment):
    repo, cash, gp, link, facts = confirmed_payment
    key = ingest(repo.db, repo.tenant, facts, verification_kind='signed_event')
    assert gp.get_by_id(link.id).stato == 'PAGATO'
    assert repo.summary(link.id_parcella)['paid_cents'] == 40000
    assert deliver(repo.db, repo.tenant) == {'delivered': 1, 'failed': 0}
    assert repo.summary(link.id_parcella)['paid_cents'] == 100000
    assert len(cash.load()) == 2
    assert ingest(repo.db, repo.tenant, replace(facts, observed_at='2026-10-20T07:00:00Z'),
                  verification_kind='authenticated_api') == key
    assert deliver(repo.db, repo.tenant) == {'delivered': 0, 'failed': 0}
    assert len(cash.load()) == 2
    stored = repo.db.conn.execute('SELECT facts_json FROM ' + TABLE + ' WHERE source_key=?', (key,)).fetchone()[0]
    assert json.loads(stored)['observed_at'] == facts.observed_at


def test_source_and_link_rollback_if_enqueue_fails(confirmed_payment, monkeypatch):
    repo, _, gp, link, facts = confirmed_payment

    def fail(*args, **kwargs):
        raise RuntimeError('CONTROLLED-QUEUE-FAILURE')

    monkeypatch.setattr('pct.transactional_outbox.enqueue', fail)
    with pytest.raises(RuntimeError, match='QUEUE-FAILURE'):
        ingest(repo.db, repo.tenant, facts, verification_kind='signed_event')
    assert gp.get_by_id(link.id).stato == 'ATTESO'
    assert repo.db.conn.execute('SELECT COUNT(*) FROM ' + TABLE).fetchone()[0] == 0
    assert repo.summary(link.id_parcella)['paid_cents'] == 40000


def test_cash_and_delivery_ack_rollback_together(confirmed_payment, monkeypatch):
    from pct.parcella_incassi_repository import ParcellaIncassiRepository
    repo, cash, _, link, facts = confirmed_payment
    ingest(repo.db, repo.tenant, facts, verification_kind='signed_event')
    register = ParcellaIncassiRepository.register

    def fail_after_cash(self, **kwargs):
        register(self, **kwargs)
        raise RuntimeError('CONTROLLED-ACK-FAILURE')

    monkeypatch.setattr(ParcellaIncassiRepository, 'register', fail_after_cash)
    assert deliver(repo.db, repo.tenant) == {'delivered': 0, 'failed': 1}
    assert len(cash.load()) == 1
    assert repo.summary(link.id_parcella)['paid_cents'] == 40000
    state = repo.db.conn.execute('SELECT status,attempts FROM transactional_outbox WHERE event_type=?', (EVENT,)).fetchone()
    assert tuple(state[index] for index in (0, 1)) == ('PENDING', 1)


def test_sources_are_immutable_and_missing_day_is_not_invented(confirmed_payment):
    repo, cash, _, link, facts = confirmed_payment
    unknown = replace(facts, paid_on=None, paid_at=None, date_origin='', date_issue='Data non dimostrata')
    key = ingest(repo.db, repo.tenant, unknown, verification_kind='authenticated_api')
    assert deliver(repo.db, repo.tenant) == {'delivered': 0, 'failed': 0}
    assert repo.summary(link.id_parcella)['paid_cents'] == 40000
    for sql in ('UPDATE ' + TABLE + " SET currency='USD' WHERE source_key=?",
                'DELETE FROM ' + TABLE + ' WHERE source_key=?'):
        with pytest.raises(Exception, match='immutabile'):
            repo.db.conn.execute(sql, (key,))
        cash._finish(repo.db.conn, rollback=True)
    assert repo.db.conn.execute('SELECT paid_on FROM ' + TABLE + ' WHERE source_key=?', (key,)).fetchone()[0] is None
    assert for_invoice(repo.db, repo.tenant, link.id_parcella)[0]['status'] == 'DATE_REQUIRED'


def test_verified_income_requires_refund_proof_instead_of_manual_reversal(confirmed_payment):
    from uuid import uuid4
    repo, cash, _, link, facts = confirmed_payment
    key = ingest(repo.db, repo.tenant, facts, verification_kind='signed_event')
    assert deliver(repo.db, repo.tenant, source_key=key) == {'delivered': 1, 'failed': 0}
    source = for_invoice(repo.db, repo.tenant, link.id_parcella)[0]
    assert source['status'] == 'RECORDED' and source['amount_cents'] == 60000
    summary = repo.summary(link.id_parcella)
    movement = next(row for row in summary['receipts'] if row['movement_id'] == source['movement_id'])
    assert movement['provider_confirmed']
    with pytest.raises(ValueError, match='rimborso'):
        repo.reverse(invoice_id=link.id_parcella, movement_id=movement['movement_id'], paid_on='2026-10-20',
            reason='CONTROLLED-NOT-A-REFUND', command_key=str(uuid4()), expected_revision=summary['revision'])
    assert repo.summary(link.id_parcella)['paid_cents'] == 100000 and len(cash.load()) == 2


def test_callback_delivery_does_not_process_an_unrelated_payment(confirmed_payment, tmp_path):
    from pct.fatturazione import GestioneFatturazione, VoceParcella, StatoParcella
    repo, cash, gp, link, facts = confirmed_payment
    first = ingest(repo.db, repo.tenant, facts, verification_kind='signed_event')
    billing = GestioneFatturazione(str(tmp_path / 'other-invoice.json'), studio_db=repo.db)
    other = billing.crea(id_cliente='cliente-1', voci=[VoceParcella(descrizione='OTHER-CONTROLLED', prezzo_unitario=1000)],
        applica_iva=False, applica_cassa=False, applica_bollo=False, applica_ritenuta=False)
    billing.cambia_stato(other.id, StatoParcella.EMESSA)
    other_link = gp.crea_link(other.id, 'cliente-1', 600, 'OTHER-CONTROLLED')
    other_facts = stripe_facts({'id': 'cs_other', 'payment_status': 'paid', 'amount_total': 60000, 'currency': 'eur',
        'metadata': {'link_id': other_link.id}}, other_link,
        verified_event_created=int(datetime(2026, 10, 19, 12, tzinfo=timezone.utc).timestamp()),
        verified_event_id='evt_other', verified_event_type='checkout.session.completed')
    ingest(repo.db, repo.tenant, other_facts, verification_kind='signed_event')
    assert deliver(repo.db, repo.tenant, source_key=first, limit=1) == {'delivered': 1, 'failed': 0}
    assert repo.summary(link.id_parcella)['paid_cents'] == 100000
    assert repo.summary(other.id)['paid_cents'] == 0 and len(cash.load()) == 2
    assert for_invoice(repo.db, repo.tenant, other.id)[0]['status'] == 'PENDING'


def test_manual_command_cannot_impersonate_a_verified_provider_receipt(confirmed_payment):
    from pct.payment_confirmations import _command_key
    repo, cash, _, link, facts = confirmed_payment
    with pytest.raises(ValueError, match='UUID casuale'):
        repo.register(invoice_id=link.id_parcella, amount_cents=60000, paid_on=facts.cash_date(), method='altro',
            note=f'Pagamento {facts.provider}: {facts.transaction_id}', command_key=_command_key(repo.tenant, facts),
            expected_revision=repo.summary(link.id_parcella)['revision'])
    ingest(repo.db, repo.tenant, facts, verification_kind='signed_event')
    assert for_invoice(repo.db, repo.tenant, link.id_parcella)[0]['status'] == 'PENDING'
    assert deliver(repo.db, repo.tenant) == {'delivered': 1, 'failed': 0}
    observed = for_invoice(repo.db, repo.tenant, link.id_parcella)[0]
    assert observed['status'] == 'RECORDED' and observed['movement_id']
    assert len(cash.load()) == 2  # Non aggiungere una seconda registrazione.
