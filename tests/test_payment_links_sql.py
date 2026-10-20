"""Link reali SQLite/PostgreSQL: concorrenza e replay senza riscritture globali."""
import json
import re

import pytest

from pct.pagamenti import GestionePagamenti
from pct.payment_links_sql import PaymentLinkConflict
from tests.test_fatturazione import invoice_status_db as invoice_status_db


@pytest.fixture
def payment_database(invoice_status_db):
    database = invoice_status_db
    if getattr(database, 'backend_kind', '') == 'postgresql':
        from pct.storage_postgres import CORE_POSTGRES_SCHEMA_SQL
        for table in ('payment_links', 'payment_config'):
            ddl = re.search(r'CREATE TABLE IF NOT EXISTS ' + table + r' \(.*?\);',
                            CORE_POSTGRES_SCHEMA_SQL, re.S)
            assert ddl is not None
            database.conn.execute(ddl.group(0))
        database.raw_conn.commit()
    database.conn.execute("INSERT INTO clienti(id) VALUES ('cliente-1') ON CONFLICT(id) DO NOTHING")
    from pct.fatturazione import Parcella, VoceParcella, _write_parcella_row
    for key in ('invoice-controlled', 'invoice-other'):
        invoice = Parcella(id=key, numero=key, id_cliente='cliente-1', id_fascicolo=None,
            data_emissione='2026-10-20', data_scadenza=None, voci=[VoceParcella(descrizione='CONTROLLED', prezzo_unitario=1000)])
        _write_parcella_row(database.conn, invoice, postgres=getattr(database, 'backend_kind', '') == 'postgresql')
    (database.raw_conn if getattr(database, 'backend_kind', '') == 'postgresql' else database.conn).commit()
    return database


def manager(database, tmp_path):
    return GestionePagamenti(str(tmp_path / 'links'), studio_db=database)


def new_link(ledger, label='TEST'):
    return ledger.crea_link('invoice-controlled', 'cliente-1', 600, label)


def test_concurrent_creation_and_confirmation_preserve_other_links(payment_database, tmp_path):
    first = manager(payment_database, tmp_path)
    second = manager(payment_database, tmp_path)
    a = new_link(first, 'A')
    b = new_link(second, 'B')
    first.segna_pagato(a.id, 'Stripe', 'TX-A')
    rows = {row[0]: json.loads(row[1]) for row in payment_database.conn.execute(
        'SELECT id,dati_json FROM payment_links').fetchall()}
    assert set(rows) == {a.id, b.id}
    assert rows[a.id]['stato'] == 'PAGATO'
    assert rows[b.id]['stato'] == 'ATTESO'


def test_confirmation_replay_preserves_date_and_rejects_other_transaction(payment_database, tmp_path):
    original = manager(payment_database, tmp_path)
    link = new_link(original)
    stale = manager(payment_database, tmp_path)
    original.segna_pagato(link.id, 'Stripe', 'TX-1')
    before = payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (link.id,)).fetchone()[0]
    stale.segna_pagato(link.id, 'Stripe', 'TX-1')
    assert stale.get_by_token(link.token).pagato_il == link.pagato_il
    assert payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (link.id,)).fetchone()[0] == before
    with pytest.raises(PaymentLinkConflict, match='transazione differente'):
        stale.segna_pagato(link.id, 'Stripe', 'TX-2')
    with pytest.raises(PaymentLinkConflict):
        stale.segna_fallito(link.id, 'Stripe')
    assert stale.get_by_token(link.token).stato == 'PAGATO'
    assert payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (link.id,)).fetchone()[0] == before


def test_stale_writer_cannot_replace_a_confirmed_source(payment_database, tmp_path):
    original = manager(payment_database, tmp_path)
    link = new_link(original)
    stale = manager(payment_database, tmp_path)
    original.segna_pagato(link.id, 'PayPal', 'TX-CONTROLLED')
    with pytest.raises(PaymentLinkConflict):
        stale.segna_fallito(link.id, 'PayPal')
    current = manager(payment_database, tmp_path).get_by_token(link.token)
    assert current.stato == 'PAGATO' and current.provider_tx_id == 'TX-CONTROLLED'


def test_source_discordance_is_not_repaired_by_silently_overwriting_columns(payment_database, tmp_path):
    ledger = manager(payment_database, tmp_path)
    link = new_link(ledger)
    payment_database.conn.execute('UPDATE payment_links SET importo=? WHERE id=?', (900, link.id))
    (payment_database.raw_conn if getattr(payment_database, 'backend_kind', '') == 'postgresql' else payment_database.conn).commit()
    with pytest.raises(PaymentLinkConflict, match='discordante'):
        ledger.segna_pagato(link.id, 'Stripe', 'TX-CONTROLLED')
    assert payment_database.conn.execute('SELECT importo FROM payment_links WHERE id=?', (link.id,)).fetchone()[0] == 900
    assert link.stato == 'ATTESO'


def test_unrecognised_source_metadata_survives_a_targeted_update(payment_database, tmp_path):
    ledger = manager(payment_database, tmp_path)
    link = new_link(ledger)
    payload = json.loads(payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (link.id,)).fetchone()[0])
    payload['source_extension'] = {'reference': 'CONTROLLED-ORIGINAL'}
    payment_database.conn.execute('UPDATE payment_links SET dati_json=? WHERE id=?', (json.dumps(payload), link.id))
    (payment_database.raw_conn if getattr(payment_database, 'backend_kind', '') == 'postgresql' else payment_database.conn).commit()
    current = manager(payment_database, tmp_path)
    current.segna_pagato(link.id, 'Stripe', 'TX-CONTROLLED')
    saved = json.loads(payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (link.id,)).fetchone()[0])
    assert saved['source_extension'] == payload['source_extension']


def test_point_confirmation_does_not_load_the_payment_archive(payment_database, tmp_path, monkeypatch):
    initial = manager(payment_database, tmp_path)
    target = new_link(initial)
    foreign = initial.crea_link('invoice-other', 'cliente-1', 300, 'OTHER-CONTROLLED')
    untouched = payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (foreign.id,)).fetchone()[0]
    original_load = payment_database.carica_tabella

    def no_archive(table):
        assert table != 'payment_links', 'Consultazione globale estranea al singolo pagamento'
        return original_load(table)

    monkeypatch.setattr(payment_database, 'carica_tabella', no_archive)
    from pct import payment_links_sql
    original_list = payment_links_sql.read_links

    def scoped_list(database, **filters):
        assert filters.get('client_id') or filters.get('invoice_id'), 'Elenco globale non richiesto'
        return original_list(database, **filters)

    monkeypatch.setattr(payment_links_sql, 'read_links', scoped_list)
    current = manager(payment_database, tmp_path)
    assert not current._link
    assert current.get_by_token(target.token).id == target.id
    assert current.get_by_parcella(target.id_parcella).id == target.id
    current.segna_pagato(target.id, 'Stripe', 'TX-CONTROLLED')
    assert current.get_by_id(target.id).stato == 'PAGATO'
    assert payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (foreign.id,)).fetchone()[0] == untouched


def test_confirmation_preserves_unknown_creation_and_expiry_dates(payment_database, tmp_path):
    initial = manager(payment_database, tmp_path)
    link = new_link(initial)
    payload = json.loads(payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (link.id,)).fetchone()[0])
    payload.update(creato_il=None, scade_il=None)
    payment_database.conn.execute('UPDATE payment_links SET creato_il=NULL,scade_il=NULL,dati_json=? WHERE id=?',
                                 (json.dumps(payload), link.id))
    (payment_database.raw_conn if getattr(payment_database, 'backend_kind', '') == 'postgresql' else payment_database.conn).commit()
    current = manager(payment_database, tmp_path)
    assert current.get_by_id(link.id).creato_il is None
    current.segna_pagato(link.id, 'Stripe', 'TX-CONTROLLED')
    saved = payment_database.conn.execute('SELECT creato_il,scade_il FROM payment_links WHERE id=?', (link.id,)).fetchone()
    assert saved[0] is None and saved[1] is None


def test_missing_customer_cannot_create_an_orphan_link(payment_database, tmp_path):
    import sqlite3
    expected_error = sqlite3.IntegrityError
    if getattr(payment_database, 'backend_kind', '') == 'postgresql':
        from psycopg2 import IntegrityError as PostgresIntegrityError
        expected_error = PostgresIntegrityError
    ledger = manager(payment_database, tmp_path)
    with pytest.raises((expected_error, PaymentLinkConflict)):
        ledger.crea_link('invoice-controlled', 'missing-client', 600, 'CONTROLLED-INVALID')
    assert payment_database.conn.execute('SELECT COUNT(*) FROM payment_links').fetchone()[0] == 0
    assert ledger.tutti_link() == []


def test_rejected_sqlite_command_does_not_rollback_the_callers_work(payment_database, tmp_path):
    if getattr(payment_database, 'backend_kind', '') == 'postgresql':
        pytest.skip('Proprietà della transazione SQLite: PostgreSQL usa il percorso nativo dedicato.')
    ledger = manager(payment_database, tmp_path)
    conn = payment_database.conn
    conn.execute('BEGIN IMMEDIATE')
    conn.execute("INSERT INTO clienti(id) VALUES ('foreign-uncommitted-customer')")
    try:
        with pytest.raises(RuntimeError, match='Transazione estranea'):
            new_link(ledger)
        assert conn.in_transaction
        assert conn.execute("SELECT id FROM clienti WHERE id='foreign-uncommitted-customer'").fetchone()
        assert conn.execute('SELECT COUNT(*) FROM payment_links').fetchone()[0] == 0
        assert not ledger._link
    finally:
        conn.rollback()
    assert conn.execute("SELECT id FROM clienti WHERE id='foreign-uncommitted-customer'").fetchone() is None


def test_rejected_draft_delete_preserves_the_callers_sqlite_transaction(payment_database, tmp_path):
    if getattr(payment_database, 'backend_kind', '') == 'postgresql':
        pytest.skip('Proprietà della transazione SQLite: PostgreSQL usa il percorso nativo dedicato.')
    from pct.fatturazione import GestioneFatturazione, VoceParcella, parcella_revision
    from pct.fatturazione_sql_commands import delete_draft
    billing = GestioneFatturazione(str(tmp_path / 'invoices.json'), studio_db=payment_database)
    invoice = billing.crea(id_cliente='cliente-1', voci=[VoceParcella(descrizione='CONTROLLED', prezzo_unitario=100)])
    conn = payment_database.conn
    conn.execute('BEGIN IMMEDIATE')
    conn.execute("INSERT INTO clienti(id) VALUES ('foreign-uncommitted-customer')")
    try:
        with pytest.raises(RuntimeError, match='Transazione estranea'):
            delete_draft(payment_database, invoice.id, parcella_revision(invoice))
        assert conn.in_transaction
        assert conn.execute("SELECT id FROM clienti WHERE id='foreign-uncommitted-customer'").fetchone()
        assert conn.execute('SELECT id FROM parcelle WHERE id=?', (invoice.id,)).fetchone()
    finally:
        conn.rollback()


def test_replacement_failure_keeps_the_previous_link_and_cache(payment_database, tmp_path, monkeypatch):
    from pct import payment_links_sql
    ledger = manager(payment_database, tmp_path)
    previous = new_link(ledger)
    before = payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (previous.id,)).fetchone()[0]
    encode = payment_links_sql._encoded

    def fail_new(payload):
        if payload['id'] != previous.id:
            raise RuntimeError('CONTROLLED-NEW-LINK-FAILURE')
        return encode(payload)

    monkeypatch.setattr(payment_links_sql, '_encoded', fail_new)
    with pytest.raises(RuntimeError, match='NEW-LINK-FAILURE'):
        ledger.crea_link(previous.id_parcella, previous.id_cliente, 500, 'CONTROLLED-REPLACE', replace_pending=True)
    assert ledger.get_by_id(previous.id).stato == 'ATTESO'
    assert len(ledger.tutti_link()) == 1
    assert payment_database.conn.execute('SELECT dati_json FROM payment_links WHERE id=?', (previous.id,)).fetchone()[0] == before


def test_stale_invoice_cannot_revoke_a_link_or_create_a_new_payment(payment_database, tmp_path):
    from pct.fatturazione import ParcellaConcurrentUpdate
    ledger = manager(payment_database, tmp_path)
    previous = new_link(ledger)
    with pytest.raises(ParcellaConcurrentUpdate):
        ledger.crea_link(previous.id_parcella, previous.id_cliente, 500, 'CONTROLLED-STALE', replace_pending=True,
                        expected_invoice_revision='0' * 64)
    assert ledger.get_by_id(previous.id).stato == 'ATTESO' and len(ledger.tutti_link()) == 1


def test_link_requires_its_real_invoice_and_prevents_deleting_that_draft(payment_database, tmp_path):
    from pct.fatturazione import Parcella, parcella_revision
    from pct.fatturazione_sql_commands import delete_draft
    ledger = manager(payment_database, tmp_path)
    with pytest.raises(PaymentLinkConflict, match='Documento o cliente'):
        ledger.crea_link('missing-invoice', 'cliente-1', 600, 'CONTROLLED-ORPHAN')
    link = new_link(ledger)
    row = payment_database.conn.execute('SELECT dati_json FROM parcelle WHERE id=?', (link.id_parcella,)).fetchone()
    invoice = Parcella.from_dict(json.loads(row[0]))
    with pytest.raises(ValueError, match='annulla il documento'):
        delete_draft(payment_database, invoice.id, parcella_revision(invoice))
    assert payment_database.conn.execute('SELECT id FROM parcelle WHERE id=?', (invoice.id,)).fetchone()
    assert ledger.get_by_id(link.id).stato == 'ATTESO'
