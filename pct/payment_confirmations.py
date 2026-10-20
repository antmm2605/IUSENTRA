"""Conferme autenticate: fonte immutabile e consegna nella outbox nativa.

I chiamanti sono gli adattatori dei gestori dopo verifica della firma o GET
autenticata. Nessun endpoint accetta questi fatti dal browser del cliente.
Lo schema si prepara esclusivamente nella migrazione con backup.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from uuid import NAMESPACE_URL, uuid5

from pct.payment_evidence import ProviderPaymentFacts, exact_cents


EVENT = 'payment.confirmation_received'
AGGREGATE = 'payment_confirmation'
TABLE = 'payment_confirmation_sources'
DDL = (
    """CREATE TABLE IF NOT EXISTS payment_confirmation_sources (
        source_key TEXT PRIMARY KEY, tenant_key TEXT NOT NULL,
        provider TEXT NOT NULL, transaction_id TEXT NOT NULL,
        link_id TEXT NOT NULL, invoice_id TEXT NOT NULL, client_id TEXT NOT NULL,
        amount_cents BIGINT NOT NULL CHECK(amount_cents>0), currency TEXT NOT NULL,
        paid_on TEXT, observed_at TEXT NOT NULL, source_sha256 TEXT NOT NULL,
        facts_json TEXT NOT NULL, invoice_revision TEXT NOT NULL, invoice_snapshot TEXT NOT NULL, command_key TEXT NOT NULL,
        verification_kind TEXT NOT NULL, actor_key TEXT NOT NULL,
        FOREIGN KEY(link_id) REFERENCES payment_links(id),
        FOREIGN KEY(invoice_id) REFERENCES parcelle(id),
        FOREIGN KEY(client_id) REFERENCES clienti(id))""",
    'CREATE INDEX IF NOT EXISTS idx_payment_confirmation_transaction '
    'ON payment_confirmation_sources(tenant_key,provider,transaction_id,observed_at,source_key)',
    'CREATE INDEX IF NOT EXISTS idx_payment_confirmation_invoice '
    'ON payment_confirmation_sources(tenant_key,invoice_id,observed_at)',
    'CREATE INDEX IF NOT EXISTS idx_payment_confirmation_command '
    'ON payment_confirmation_sources(tenant_key,command_key)',
)


def prepare_schema(conn, *, postgres):
    for statement in DDL:
        conn.execute(statement)
    if postgres:
        schema = str(conn.execute('SELECT current_schema()').fetchone()[0]).replace('"', '""')
        function = f'"{schema}".iusentra_payment_confirmation_immutable'
        conn.execute(f'CREATE OR REPLACE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ '
                     "BEGIN RAISE EXCEPTION 'Fonte pagamento immutabile'; END; $$")
        conn.execute('DROP TRIGGER IF EXISTS iusentra_payment_confirmation_immutable ON ' + TABLE)
        conn.execute('CREATE TRIGGER iusentra_payment_confirmation_immutable BEFORE UPDATE OR DELETE ON '
                     + TABLE + f' FOR EACH ROW EXECUTE FUNCTION {function}()')
    else:
        for action in ('UPDATE', 'DELETE'):
            conn.execute(f'CREATE TRIGGER IF NOT EXISTS iusentra_payment_confirmation_no_{action.lower()} '
                         f'BEFORE {action} ON {TABLE} BEGIN '
                         "SELECT RAISE(ABORT,'Fonte pagamento immutabile'); END")


def require_schema(database):
    conn = database.conn
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    present = (conn.execute("SELECT to_regclass('payment_confirmation_sources')").fetchone()[0] if postgres else
               conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone())
    if not present:
        from pct.parcella_incassi_preparation import InvoiceReceiptsNotPrepared
        raise InvoiceReceiptsNotPrepared('Conferme dei gestori non preparate: eseguire la migrazione con backup.')
    indexes = {'idx_payment_confirmation_transaction', 'idx_payment_confirmation_invoice', 'idx_payment_confirmation_command'}
    if postgres:
        columns = {row[0] for row in conn.execute('SELECT column_name FROM information_schema.columns '
            'WHERE table_schema=current_schema() AND table_name=?', (TABLE,)).fetchall()}
        actual = {row[0] for row in conn.execute('SELECT indexname FROM pg_indexes '
            'WHERE schemaname=current_schema() AND tablename=?', (TABLE,)).fetchall()}
        triggers = {row[0] for row in conn.execute('SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid '
            'JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=current_schema() AND c.relname=? '
            'AND NOT t.tgisinternal', (TABLE,)).fetchall()}
        protected = {'iusentra_payment_confirmation_immutable'}.issubset(triggers)
    else:
        columns = {row[1] for row in conn.execute('PRAGMA table_info(' + TABLE + ')').fetchall()}
        actual = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
                                                (TABLE,)).fetchall()}
        triggers = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
                                                  (TABLE,)).fetchall()}
        protected = {'iusentra_payment_confirmation_no_update', 'iusentra_payment_confirmation_no_delete'}.issubset(triggers)
    if not indexes.issubset(actual) or not protected or not {'invoice_snapshot', 'command_key'}.issubset(columns):
        from pct.parcella_incassi_preparation import InvoiceReceiptsNotPrepared
        raise InvoiceReceiptsNotPrepared('Indici o protezioni delle conferme mancanti: preparazione con backup necessaria.')


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _key(tenant, facts):
    return hashlib.sha256(_encode([tenant, facts.provider, facts.transaction_id, facts.source_sha256]).encode()).hexdigest()


def _command_key(tenant, facts):
    return str(uuid5(NAMESPACE_URL, _encode(['iusentra-provider-receipt', tenant, facts.provider, facts.transaction_id])))


def ingest(database, tenant, facts, *, verification_kind):
    """Conserva la prima osservazione, conferma il link e accoda atomicamente."""
    from pct.fatturazione import Parcella, parcella_revision
    from pct.pagamenti import LinkPagamento
    from pct.payment_links_sql import read_link, save_links
    from pct.transactional_outbox import OutboxEvent, enqueue
    if (not isinstance(facts, ProviderPaymentFacts) or not isinstance(tenant, str) or not tenant.strip()
            or verification_kind not in {'signed_event', 'authenticated_api'}):
        raise ValueError('Conferma autenticata e studio richiesti.')
    require_schema(database)
    if verification_kind == 'signed_event':
        proof = json.loads(facts.source_json)
        if (facts.provider != 'stripe' or not isinstance(proof.get('verified_event_id'), str)
                or not proof['verified_event_id'].startswith('evt_') or proof.get('verified_event_type') not in {
                    'checkout.session.completed', 'checkout.session.async_payment_succeeded'}):
            raise ValueError('Riferimento della notifica firmata non riscontrato nella fonte.')
    source = read_link(database, key=facts.link_id)
    if source is None:
        raise ValueError('Link della conferma non presente nello studio.')
    link = LinkPagamento.from_dict(source)
    if (link.id_parcella != facts.invoice_id or link.id_cliente != facts.client_id
            or exact_cents(link.importo) != facts.amount_cents or link.valuta.upper() != facts.currency):
        raise ValueError('La conferma non concorda con il collegamento dello studio.')
    before = link.to_dict()
    # Una conferma ulteriore non riscrive l'identità del pagamento già presente
    # né una decisione di annullamento. La fonte resta comunque conservata.
    if link.stato == 'ATTESO':
        link.stato, link.pagato_il = 'PAGATO', facts.observed_at
        labels = {'stripe': 'Stripe', 'paypal': 'PayPal', 'sumup': 'SumUp', 'satispay': 'Satispay'}
        link.provider_usato, link.provider_tx_id = labels[facts.provider], facts.transaction_id
    source_key = _key(tenant, facts)
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    result = {}

    def lock_invoice(conn):
        row = conn.execute('SELECT dati_json,id_cliente FROM parcelle WHERE id=?'
                           + (' FOR UPDATE' if postgres else ''), (facts.invoice_id,)).fetchone()
        if row is None or row[1] != facts.client_id:
            raise ValueError('Documento della conferma non riscontrato nello studio.')
        item = Parcella.from_dict(json.loads(row[0]))
        if item.id != facts.invoice_id or item.id_cliente != facts.client_id:
            raise ValueError('Identità del documento SQL discordante.')
        result['revision'] = parcella_revision(item)
        result['snapshot'] = row[0]

    def record(conn):
        conn.execute('INSERT INTO ' + TABLE + ' (source_key,tenant_key,provider,transaction_id,link_id,invoice_id,'
                     'client_id,amount_cents,currency,paid_on,observed_at,source_sha256,facts_json,invoice_revision,'
                     'invoice_snapshot,command_key,verification_kind,actor_key) VALUES (' + ','.join('?' for _ in range(18)) + ') '
                     'ON CONFLICT(source_key) DO NOTHING',
                     (source_key, tenant, facts.provider, facts.transaction_id, facts.link_id, facts.invoice_id,
                      facts.client_id, facts.amount_cents, facts.currency, facts.paid_on, facts.observed_at,
                      facts.source_sha256, _encode(asdict(facts)), result['revision'], result['snapshot'], _command_key(tenant, facts),
                      verification_kind, 'payment-verifier'))
        # Tutte le varianti sono conservate; la prima prova con giorno dimostrato
        # governa il comando stabile. Non ricalcolare la data al retry.
        canonical = conn.execute('SELECT source_key,invoice_id,client_id,amount_cents,currency,paid_on FROM ' + TABLE
            + ' WHERE tenant_key=? AND provider=? AND transaction_id=? AND paid_on IS NOT NULL '
            'ORDER BY observed_at,source_key LIMIT 1', (tenant, facts.provider, facts.transaction_id)).fetchone()
        result['source_key'] = canonical[0] if canonical else source_key
        if canonical and ((canonical[1], canonical[2], int(canonical[3]), canonical[4]) != (
                facts.invoice_id, facts.client_id, facts.amount_cents, facts.currency)
                or facts.paid_on is not None and canonical[5] != facts.paid_on):
            # Non fondere un'identità o una data discordante. La nuova fonte
            # è persistita, ma non autorizza un altro movimento di cassa.
            result['source_key'] = source_key
            result['review'] = True
            return
        if canonical and not conn.execute('SELECT 1 FROM transactional_outbox WHERE idempotency_key=?',
                                          ('payment-confirmation:' + canonical[0],)).fetchone():
            enqueue(conn, OutboxEvent(tenant_id=tenant, aggregate_type=AGGREGATE, aggregate_id=canonical[0],
                aggregate_version=1, event_type=EVENT, idempotency_key='payment-confirmation:' + canonical[0],
                actor_id='payment-verifier', payload={'source_key': canonical[0]}))

    save_links(database, {link.id: link}, {link.id: source}, {link.id: before},
               before_write=lock_invoice, after_write=record)
    return result['source_key']


def deliver(database, tenant, *, limit=50, source_key=None):
    """Cassa e ACK hanno il commit del dispatcher esistente; retry finiti."""
    from pct.parcella_incassi_repository import ParcellaIncassiRepository
    from pct.query_projection_worker import deliver_pending
    require_schema(database)
    repo = ParcellaIncassiRepository(database, tenant, actor_key='payment-verifier')
    repo.require_prepared()
    conn = repo.cash._write_conn()
    if not repo.postgres:
        if conn.in_transaction:
            raise RuntimeError('Transazione estranea alla consegna del pagamento.')
        conn.execute('PRAGMA foreign_keys=ON')

    def project(transaction, source_key):
        from pct.fatturazione import Parcella, parcella_revision
        row = transaction.execute('SELECT facts_json,invoice_revision,source_sha256,invoice_snapshot FROM ' + TABLE
                                  + ' WHERE tenant_key=? AND source_key=?', (tenant, source_key)).fetchone()
        if row is None:
            raise ValueError('Fonte autenticata della consegna assente.')
        facts = ProviderPaymentFacts(**json.loads(row[0]))
        if facts.source_sha256 != row[2] or _key(tenant, facts) != source_key:
            raise ValueError('Impronta della fonte discordante.')
        if facts.currency != 'EUR':
            raise ValueError('Valuta diversa dall’euro: riscontro della conversione necessario prima della registrazione.')
        original = Parcella.from_dict(json.loads(row[3]))
        current = repo._invoice(facts.invoice_id, lock=True)
        if not repo._same_financial_source(original, current):
            raise ValueError('Dati economici modificati dopo la conferma del gestore: riconciliazione necessaria.')
        repo.register(invoice_id=facts.invoice_id, amount_cents=facts.amount_cents, paid_on=facts.cash_date(),
            method='altro', note=f'Pagamento {facts.provider}: {facts.transaction_id}',
            command_key=_command_key(tenant, facts), expected_revision=parcella_revision(current), _transaction=transaction)

    return deliver_pending(conn=conn, finish=repo.cash._finish, tenant=tenant, aggregate=AGGREGATE,
                           event_type=EVENT, project=project, limit=limit, aggregate_id=source_key,
                           failure_message=lambda exc: ('Incasso autenticato non registrato. ' + str(exc))[:700]
                               if isinstance(exc, ValueError) else 'Incasso autenticato non registrato: riconciliazione necessaria.')


def for_invoice(database, tenant, invoice_id):
    """Riscontri della sola fattura richiesta; nessuna lettura o chiamata esterna."""
    require_schema(database)
    rows = database.conn.execute('SELECT s.source_key,s.facts_json,s.source_sha256,s.command_key,'
        'p.movement_id,p.amount_cents,p.paid_on,o.status,o.last_error '
        'FROM ' + TABLE + ' s LEFT JOIN parcella_incassi_proofs p '
        'ON p.tenant_key=s.tenant_key AND p.command_key=s.command_key AND p.parcella_id=s.invoice_id AND p.direction=1 '
        "AND EXISTS(SELECT 1 FROM prima_nota_commands command WHERE command.tenant_key=p.tenant_key "
        "AND command.command_key=p.command_key AND command.actor_key='payment-verifier' AND command.operation='registrazione') "
        'LEFT JOIN transactional_outbox o ON o.tenant_id=s.tenant_key AND o.aggregate_type=? '
        'AND o.aggregate_id=s.source_key AND o.event_type=? '
        'WHERE s.tenant_key=? AND s.invoice_id=? ORDER BY s.observed_at,s.source_key',
        (AGGREGATE, EVENT, tenant, invoice_id)).fetchall()
    groups = {}
    for row in rows:
        facts = ProviderPaymentFacts(**json.loads(row[1]))
        if (facts.source_sha256 != row[2] or _key(tenant, facts) != row[0]
                or _command_key(tenant, facts) != row[3] or facts.invoice_id != invoice_id):
            raise ValueError('Fonte del gestore discordante dal collegamento SQL.')
        if row[4] is not None and int(row[5]) != facts.amount_cents:
            raise ValueError('Importo del gestore discordante dal movimento registrato.')
        groups.setdefault((facts.provider, facts.transaction_id), []).append((row, facts))
    result = []
    for entries in groups.values():
        row, facts = next((item for item in entries if item[1].paid_on is not None), entries[0])
        dates = {item[1].paid_on for item in entries if item[1].paid_on is not None}
        registered = row[4] is not None
        date_conflict = registered and facts.paid_on is not None and row[6] != facts.paid_on
        status = ('REVIEW' if len(dates) > 1 or date_conflict else 'RECORDED' if registered else
                  'DATE_REQUIRED' if facts.paid_on is None else 'REVIEW' if row[7] == 'FAILED' or row[8] else 'PENDING')
        reason = ('Date discordanti nelle conferme del gestore o nella cassa: verifica le fonti.' if len(dates) > 1 or date_conflict else
                  '' if registered else facts.date_issue if facts.paid_on is None else
                  row[8] or 'Conferma ricevuta: registrazione in cassa in attesa.')
        result.append({'source_key': row[0], 'provider': facts.provider, 'transaction_id': facts.transaction_id,
            'amount_cents': facts.amount_cents, 'currency': facts.currency, 'paid_on': facts.paid_on,
            'observed_at': facts.observed_at, 'date_origin': facts.date_origin, 'source_sha256': facts.source_sha256,
            'status': status, 'reason': reason, 'evidence_count': len(entries), 'movement_id': row[4] or ''})
    return result
