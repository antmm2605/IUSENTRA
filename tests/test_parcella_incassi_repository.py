"""Guardrail del prossimo incarico: un solo registro di cassa, conferma atomica."""
from uuid import uuid4
import hashlib
import json

import pytest

from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella, parcella_revision
from pct.prima_nota_repository import PrimaNotaRepository
from pct.parcella_incassi_repository import ParcellaIncassiRepository, ParcellaIncassoConflict
from tests.test_fatturazione import invoice_status_db as invoice_status_db


@pytest.fixture
def invoice_receipts(invoice_status_db, tmp_path):
    db = invoice_status_db
    # Il registro nuovo mantiene i vincoli FK: il cliente controllato esiste
    # realmente anche nel backend SQLite, non soltanto nel JSON della parcella.
    db.conn.execute("INSERT INTO clienti(id) VALUES ('cliente-1') ON CONFLICT(id) DO NOTHING")
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    backup = tmp_path / 'empty-cash-source.json'
    backup.write_text('{}')
    cash = PrimaNotaRepository(db, 'controlled', actor_key='operator')
    cash.ensure_schema()
    cash.initialize({}, source_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(), backup_reference=str(backup))
    repo = ParcellaIncassiRepository(db, 'controlled', actor_key='operator')
    repo.ensure_schema()
    manager = GestioneFatturazione(str(tmp_path / 'invoices.json'), studio_db=db)
    invoice = manager.crea(id_cliente='cliente-1', voci=[VoceParcella(descrizione='Compenso', prezzo_unitario=1000)],
        applica_iva=False, applica_cassa=False, applica_ritenuta=False, applica_bollo=False)
    manager.cambia_stato(invoice.id, StatoParcella.EMESSA)
    return repo, cash, manager, invoice.id


def _invoice(manager, invoice_id):
    fresh = GestioneFatturazione(manager.db_path, studio_db=manager._studio_db)
    return fresh.get(invoice_id)


def _receive(repo, manager, invoice_id, cents, *, command=None, revision=None):
    return repo.register(invoice_id=invoice_id, amount_cents=cents, paid_on='2026-10-20', method='banca', note='Prova controllata',
        command_key=command or str(uuid4()), expected_revision=revision or parcella_revision(_invoice(manager, invoice_id)))


def test_partial_then_balance_and_replay_keep_one_native_cash_record_per_receipt(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    command = str(uuid4())
    original = parcella_revision(_invoice(manager, invoice_id))
    first = _receive(repo, manager, invoice_id, 40000, command=command, revision=original)
    assert (first['paid_cents'], first['residual_cents'], first['status']) == (40000, 60000, 'PARTIAL')
    assert _invoice(manager, invoice_id).stato == StatoParcella.EMESSA
    second = _receive(repo, manager, invoice_id, 60000)
    assert (second['paid_cents'], second['residual_cents'], second['status']) == (100000, 0, 'PAID')
    assert _invoice(manager, invoice_id).stato == StatoParcella.PAGATA
    replay = _receive(repo, manager, invoice_id, 40000, command=command, revision=original)
    assert replay['already_present'] and replay['movement_id'] == first['movement_id']
    assert (replay['paid_cents'], replay['residual_cents']) == (100000, 0)
    movements = cash.load()
    assert len(movements) == 2
    assert sorted(row['importo'] for row in movements.values()) == [400, 600]
    assert {row['parcella_id'] for row in movements.values()} == {invoice_id}
    assert cash.db.conn.execute('SELECT count(*) FROM prima_nota_commands WHERE tenant_key=?', ('controlled',)).fetchone()[0] == 2


def test_overpayment_and_stale_revision_do_not_change_cash_or_invoice(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    original = parcella_revision(_invoice(manager, invoice_id))
    _receive(repo, manager, invoice_id, 40000)
    before = _invoice(manager, invoice_id).to_dict()
    with pytest.raises(ParcellaIncassoConflict):
        _receive(repo, manager, invoice_id, 60001)
    with pytest.raises(ParcellaIncassoConflict):
        _receive(repo, manager, invoice_id, 10000, revision=original)
    assert _invoice(manager, invoice_id).to_dict() == before
    assert len(cash.load()) == 1


def test_reversal_keeps_original_cash_and_reopens_only_the_reversed_balance(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    first = _receive(repo, manager, invoice_id, 40000)
    _receive(repo, manager, invoice_id, 60000)
    command, revision = str(uuid4()), parcella_revision(_invoice(manager, invoice_id))
    fields = dict(invoice_id=invoice_id, movement_id=first['movement_id'], paid_on='2026-10-20',
        reason='Storno controllato', command_key=command, expected_revision=revision)
    result = repo.reverse(**fields)
    assert (result['paid_cents'], result['residual_cents'], result['status']) == (60000, 40000, 'PARTIAL')
    assert _invoice(manager, invoice_id).stato == StatoParcella.EMESSA
    movements = cash.load()
    assert len(movements) == 3 and movements[first['movement_id']]['importo'] == 400
    reversed_rows = [row for row in movements.values() if row['storno_di'] == first['movement_id']]
    assert len(reversed_rows) == 1 and reversed_rows[0]['tipo'] == 'PAGAMENTO' and reversed_rows[0]['importo'] == 400
    replay = repo.reverse(**fields)
    assert replay['already_present'] and replay['movement_id'] == result['movement_id']
    assert len(cash.load()) == 3


def test_audit_failure_rolls_back_invoice_cash_command_and_allocation(invoice_receipts, monkeypatch):
    repo, cash, manager, invoice_id = invoice_receipts
    before = _invoice(manager, invoice_id).to_dict()
    def fail(*args, **kwargs):
        raise RuntimeError('Consegna audit indisponibile')
    monkeypatch.setattr('pct.transactional_outbox.enqueue', fail)
    with pytest.raises(RuntimeError, match='audit indisponibile'):
        _receive(repo, manager, invoice_id, 100000)
    assert _invoice(manager, invoice_id).to_dict() == before
    assert cash.load() == {}
    assert cash.db.conn.execute('SELECT count(*) FROM prima_nota_commands WHERE tenant_key=?', ('controlled',)).fetchone()[0] == 0
    assert repo.summary(invoice_id)['paid_cents'] == 0


def test_changed_financial_source_stays_explicit_without_new_cash(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    _receive(repo, manager, invoice_id, 40000)
    manager = GestioneFatturazione(manager.db_path, studio_db=manager._studio_db)
    manager.aggiorna(invoice_id, expected_revision=parcella_revision(manager.get(invoice_id)),
        voci=[VoceParcella(descrizione='Compenso rettificato', prezzo_unitario=2000)])
    summary = repo.summary(invoice_id)
    assert summary['status'] == 'REVIEW' and summary['paid_cents'] == 40000 and summary['residual_cents'] is None
    with pytest.raises(ParcellaIncassoConflict):
        _receive(repo, manager, invoice_id, 10000)
    assert len(cash.load()) == 1


def test_other_actor_cannot_reuse_the_receipt_command(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    command, revision = str(uuid4()), parcella_revision(_invoice(manager, invoice_id))
    _receive(repo, manager, invoice_id, 40000, command=command, revision=revision)
    other = ParcellaIncassiRepository(repo.db, 'controlled', actor_key='other-operator')
    with pytest.raises(ParcellaIncassoConflict):
        _receive(other, manager, invoice_id, 40000, command=command, revision=revision)
    with pytest.raises(ValueError, match='studio'):
        ParcellaIncassiRepository(repo.db, 'unrelated-study', actor_key='operator')
    assert len(cash.load()) == 1


def test_legacy_paid_invoice_without_immutable_cash_is_not_reconstructed(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    manager.cambia_stato(invoice_id, StatoParcella.PAGATA, data_pagamento='2026-10-19')
    result = repo.summary(invoice_id)
    assert result['status'] == 'REVIEW' and result['paid_cents'] is None and result['residual_cents'] is None
    with pytest.raises(ParcellaIncassoConflict):
        _receive(repo, manager, invoice_id, 10000)
    assert cash.load() == {}


def test_changed_calculation_does_not_rewrite_the_original_amount_due(invoice_receipts, monkeypatch):
    from pct.fatturazione import Parcella
    repo, cash, manager, invoice_id = invoice_receipts
    _receive(repo, manager, invoice_id, 40000)
    monkeypatch.setattr(Parcella, 'netto_a_pagare', property(lambda self: 1010.0))
    summary = repo.summary(invoice_id)
    assert summary['status'] == 'REVIEW'
    assert summary['paid_cents'] == 40000 and summary['residual_cents'] is None
    with pytest.raises(ParcellaIncassoConflict):
        _receive(repo, manager, invoice_id, 61000)
    assert len(cash.load()) == 1


def test_amount_losing_a_cent_in_the_native_cash_format_is_rejected_before_writing(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    before = _invoice(manager, invoice_id).to_dict()
    with pytest.raises(ValueError, match='esattamente in centesimi'):
        _receive(repo, manager, invoice_id, 9007199254740991)
    assert cash.load() == {} and _invoice(manager, invoice_id).to_dict() == before


def test_failure_reading_the_committed_result_keeps_the_original_command_recoverable(invoice_receipts, monkeypatch):
    from pct.parcella_incassi_repository import ParcellaIncassoOutcomeUnconfirmed
    repo, cash, manager, invoice_id = invoice_receipts
    command, revision = str(uuid4()), parcella_revision(_invoice(manager, invoice_id))
    original = repo.summary
    calls = 0

    def fail_after_commit(identifier):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ValueError('Consultazione successiva non disponibile')
        return original(identifier)

    monkeypatch.setattr(repo, 'summary', fail_after_commit)
    with pytest.raises(ParcellaIncassoOutcomeUnconfirmed):
        _receive(repo, manager, invoice_id, 40000, command=command, revision=revision)
    assert len(cash.load()) == 1
    monkeypatch.setattr(repo, 'summary', original)
    result = _receive(repo, manager, invoice_id, 40000, command=command, revision=revision)
    assert result['already_present'] and result['paid_cents'] == 40000
    assert len(cash.load()) == 1


def test_reversal_does_not_reissue_a_cancelled_document(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    first = _receive(repo, manager, invoice_id, 40000)
    current = _invoice(manager, invoice_id)
    manager.aggiorna(invoice_id, stato=StatoParcella.ANNULLATA, expected_revision=parcella_revision(current))
    current = _invoice(manager, invoice_id)
    assert repo.summary(invoice_id)['status'] == 'REVIEW'
    result = repo.reverse(invoice_id=invoice_id, movement_id=first['movement_id'], paid_on='2026-10-20',
        reason='Incasso da stornare sul documento annullato', command_key=str(uuid4()), expected_revision=parcella_revision(current))
    assert result['status'] == 'CANCELLED' and result['paid_cents'] == 0 and result['residual_cents'] == 0
    assert _invoice(manager, invoice_id).stato == StatoParcella.ANNULLATA
    assert len(cash.load()) == 2


def test_receipts_keep_the_document_payment_terms_and_the_distinct_cash_methods(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    manager.aggiorna(invoice_id, metodo_pagamento='Bonifico', expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    _receive(repo, manager, invoice_id, 40000)
    assert _invoice(manager, invoice_id).metodo_pagamento == 'Bonifico'
    result = repo.register(invoice_id=invoice_id, amount_cents=60000, paid_on='2026-10-20', method='pos',
        note='Saldo controllato', command_key=str(uuid4()), expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    assert result['status'] == 'PAID'
    assert _invoice(manager, invoice_id).metodo_pagamento == 'Bonifico'
    assert {entry['metodo'] for entry in cash.load().values()} == {'banca', 'pos'}


def test_unproved_duplicate_cannot_enter_the_native_cash_register(invoice_receipts):
    from pct.prima_nota import MovimentoPrimaNota
    repo, cash, manager, invoice_id = invoice_receipts
    _receive(repo, manager, invoice_id, 40000)
    payload = cash.load()
    duplicate = MovimentoPrimaNota(data='2026-10-20', importo=100, parcella_id=invoice_id, creato_da='operator')
    payload[duplicate.id] = duplicate.to_dict()
    with pytest.raises(ValueError, match='duplicato'):
        cash.save(payload)
    assert len(cash.load()) == 1 and repo.summary(invoice_id)['paid_cents'] == 40000


def test_generic_cash_reversal_cannot_bypass_invoice_balance(invoice_receipts, tmp_path):
    from pct.prima_nota import GestionePrimaNota
    repo, cash, manager, invoice_id = invoice_receipts
    first = _receive(repo, manager, invoice_id, 40000)
    register = GestionePrimaNota(str(tmp_path / 'cash.json'), studio_db=repo.db,
        tenant_key=repo.tenant, actor_key='operator')
    with pytest.raises(ValueError, match='aggiornare insieme'):
        register.storna(first['movement_id'], motivo='Rettifica controllata', attore='operator')
    assert len(cash.load()) == 1 and repo.summary(invoice_id)['paid_cents'] == 40000


def test_paid_label_cannot_replace_the_missing_balance_receipt(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    _receive(repo, manager, invoice_id, 40000)
    with pytest.raises(ValueError, match='pagamento effettivo'):
        manager.cambia_stato(invoice_id, StatoParcella.PAGATA)
    assert _invoice(manager, invoice_id).stato == StatoParcella.EMESSA
    assert len(cash.load()) == 1 and repo.summary(invoice_id)['residual_cents'] == 60000


def test_bank_reconciliation_preserves_receipt_and_reversal_proofs(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    first = _receive(repo, manager, invoice_id, 40000)
    reversal = repo.reverse(invoice_id=invoice_id, movement_id=first['movement_id'], paid_on='2026-10-20',
        reason='Rettifica controllata', command_key=str(uuid4()),
        expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    payload = cash.load()
    for movement_id in (first['movement_id'], reversal['movement_id']):
        payload[movement_id]['riconciliato_il'] = '2026-10-20T10:00:00'
        payload[movement_id]['riga_estratto_id'] = 'controlled-bank-' + movement_id
    cash.save(payload)
    balance = repo.summary(invoice_id)
    assert balance['paid_cents'] == 0 and balance['residual_cents'] == 100000
    assert len(cash.load()) == 2


def test_cash_interface_identifies_only_receipts_proven_by_sql(invoice_receipts, tmp_path):
    from pct.prima_nota import GestionePrimaNota
    from web.services.react_prima_nota_bridge import build_react_prima_nota_payload
    repo, _, manager, invoice_id = invoice_receipts
    first = _receive(repo, manager, invoice_id, 40000)
    register = GestionePrimaNota(str(tmp_path / 'cash.json'), studio_db=repo.db,
        tenant_key=repo.tenant, actor_key='operator')
    payload = build_react_prima_nota_payload(get_prima_nota=lambda: register)
    assert len(payload['movimenti']) == 1
    assert payload['movimenti'][0]['id'] == first['movement_id']
    assert payload['movimenti'][0]['incassoCollegato'] is True
    assert payload['movimenti'][0]['parcellaId'] == invoice_id


def test_batch_balance_reads_reuse_the_exact_single_document_rules(invoice_receipts):
    from pct.parcella_incassi_views import balances_for_invoices
    from pct.fatturazione import ParcellaConcurrentUpdate
    repo, _, manager, invoice_id = invoice_receipts
    stale = manager.get(invoice_id)
    _receive(repo, manager, invoice_id, 40000)
    current = _invoice(manager, invoice_id)
    batch = balances_for_invoices(repo.db, {invoice_id: current})
    assert batch == {invoice_id: repo.summary(invoice_id)}
    assert batch[invoice_id]['paid_cents'] == 40000
    assert batch[invoice_id]['residual_cents'] == 60000
    with pytest.raises(ParcellaConcurrentUpdate):
        balances_for_invoices(repo.db, {invoice_id: stale})


def test_partial_receipts_reduce_the_same_customer_and_archive_balances(invoice_receipts):
    repo, _, manager, invoice_id = invoice_receipts
    _receive(repo, manager, invoice_id, 40000)
    fresh = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    assert fresh.crediti_aperti()['importo'] == 600
    assert fresh.statistiche()['incassato'] == 400
    assert fresh.statistiche()['da_incassare'] == 600
    customer = fresh.saldo_cliente('cliente-1')
    assert customer['incassato'] == 400 and customer['insoluto'] == 600
    assert customer['saldo_aperto'] == 600


def test_receipt_history_reports_cash_movements_instead_of_the_invoice_total(invoice_receipts):
    from web.services.invoice_receipts_presenter import receipt_rows
    from web.services.react_incassi_pagamenti_bridge import _receipt_record
    from pct.formatting import format_euro_it
    repo, _, manager, invoice_id = invoice_receipts
    first = _receive(repo, manager, invoice_id, 40000)
    fresh = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    fresh.statistiche()
    rows = receipt_rows(fresh.tutte(), {}, _receipt_record)
    assert len(rows) == 1 and rows[0]['id'] == first['movement_id']
    assert rows[0]['amountDisplay'] == format_euro_it(400)
    assert rows[0]['paidAt'] == '20/10/2026'
    repo.reverse(invoice_id=invoice_id, movement_id=first['movement_id'], paid_on='2026-10-20',
        reason='Rettifica controllata', command_key=str(uuid4()),
        expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    fresh = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    fresh.statistiche()
    rows = receipt_rows(fresh.tutte(), {}, _receipt_record)
    assert {row['amountDisplay'] for row in rows} == {format_euro_it(400), format_euro_it(-400)}
    assert {row['stateLabel'] for row in rows} == {'Incasso poi stornato', 'Storno incasso'}


def test_receipt_period_uses_the_cash_date_even_for_prior_year_invoices(invoice_receipts):
    repo, _, manager, invoice_id = invoice_receipts
    manager.aggiorna(invoice_id, data_emissione='2025-12-01',
        expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    _receive(repo, manager, invoice_id, 40000)
    fresh = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    assert fresh.statistiche(2026)['incassato'] == 400
    assert fresh.statistiche(2025)['incassato'] == 0
    assert fresh.incassi_periodo('2026-10-01', '2026-11-01') == {'importo': 400, 'movimenti': 1}
    assert fresh.incassi_periodo('2026-11-01', '2026-12-01') == {'importo': 0, 'movimenti': 0}


def test_receipt_year_uses_cash_date_instead_of_invoice_year(invoice_receipts):
    from pct.parcella_incassi_views import invoice_cash_year
    repo, _, manager, invoice_id = invoice_receipts
    invoice = manager.get(invoice_id)
    repo.register(invoice_id=invoice_id, amount_cents=40000, paid_on='2026-10-19',
                  method='banca', note='Acconto controllato', command_key=str(uuid4()),
                  expected_revision=parcella_revision(invoice))
    invoice._incassi_projection = repo.summary(invoice_id)
    invoice.data_emissione = '2025-12-31'
    assert invoice_cash_year(invoice, 2026) == 400
    assert invoice_cash_year(invoice, 2025) == 0
    from web.services.react_incassi_pagamenti_bridge import _card_records
    row = _card_records([invoice], [], {}, 2026)[0]
    assert 'incassato' in row['metricIds']
    assert row['annualReceivedDisplay'] == row['receivedDisplay']


def test_filtered_cash_export_keeps_invoice_total_received_and_residual_distinct(invoice_receipts):
    import csv
    import io
    from pct.formatting import format_euro_it
    from web.services.react_incassi_pagamenti_bridge import _card_records, export_incassi_selection_csv
    repo, _, manager, invoice_id = invoice_receipts
    _receive(repo, manager, invoice_id, 40000)
    fresh = GestioneFatturazione(manager.db_path, studio_db=repo.db)
    fresh.statistiche()
    cards = _card_records(fresh.tutte(), [], {}, 2026)
    assert set(cards[0]['metricIds']) == {'incassato', 'da_incassare'}
    content = export_incassi_selection_csv(cards, ['parcella:' + invoice_id])
    rows = list(csv.DictReader(io.StringIO(content.lstrip('\ufeff')), delimiter=';'))
    assert len(rows) == 1
    assert rows[0]['Importo'] == format_euro_it(1000)
    assert rows[0]['Incassato'] == format_euro_it(400)
    assert rows[0]['Residuo'] == format_euro_it(600)


def test_future_cash_date_is_rejected_before_any_invoice_or_cash_write(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    before = _invoice(manager, invoice_id).to_dict()
    with pytest.raises(ValueError, match='futura'):
        repo.register(invoice_id=invoice_id, amount_cents=40000, paid_on='2999-01-01', method='banca',
            note='Data non valida', command_key=str(uuid4()), expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    assert cash.load() == {}
    assert _invoice(manager, invoice_id).to_dict() == before


@pytest.mark.parametrize('case_client', ['cliente-1', 'cliente-2'])
def test_cash_receipt_checks_case_client_and_never_marks_the_judgment_award_paid(invoice_receipts, case_client):
    repo, cash, manager, invoice_id = invoice_receipts
    conn = repo.db.conn
    conn.execute("INSERT INTO clienti(id) VALUES ('cliente-2') ON CONFLICT(id) DO NOTHING")
    source = json.dumps({'pagamenti': {'liquidazione_giudice': {'importo': 5000, 'status': 'non_pagato'}}})
    conn.execute('INSERT INTO fascicoli(id,id_cliente,dati_json) VALUES (?,?,?)', ('controlled-case', case_client, source))
    cash._finish(conn)
    manager.aggiorna(invoice_id, id_fascicolo='controlled-case',
        expected_revision=parcella_revision(_invoice(manager, invoice_id)))
    if case_client == 'cliente-1':
        assert _receive(repo, manager, invoice_id, 40000)['paid_cents'] == 40000
    else:
        with pytest.raises(ValueError, match='fascicolo'):
            _receive(repo, manager, invoice_id, 40000)
        assert cash.load() == {}
    assert conn.execute('SELECT dati_json FROM fascicoli WHERE id=?', ('controlled-case',)).fetchone()[0] == source


def test_discordant_cash_source_is_not_reported_as_a_confirmed_balance(invoice_receipts):
    repo, cash, manager, invoice_id = invoice_receipts
    first = _receive(repo, manager, invoice_id, 40000)
    _receive(repo, manager, invoice_id, 60000)
    source = cash.load()[first['movement_id']]
    source['importo'] = 401
    cash.db.conn.execute('UPDATE prima_nota_records SET payload_json=? WHERE tenant_key=? AND record_key=?',
                         (json.dumps(source), 'controlled', first['movement_id']))
    (getattr(cash.db, 'raw_conn', None) or cash.db.conn).commit()
    with pytest.raises(ValueError, match='discordante'):
        repo.summary(invoice_id)
    with pytest.raises(ValueError, match='discordante'):
        cash.load()
