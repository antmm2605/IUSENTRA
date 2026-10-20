"""Preparazione esplicita dei collegamenti, con backup e conservazione dei dati."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone


class InvoiceReceiptsNotPrepared(RuntimeError):
    pass


def marker_key(tenant):
    return 'invoice_receipts_v1:' + tenant


def require_receipt_indexes(db):
    names = ('idx_parcella_incassi_balance', 'idx_parcella_incassi_period')
    if getattr(db, 'backend_kind', '') == 'postgresql':
        rows = db.conn.execute('SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() '
            'AND tablename=? AND indexname IN (?,?) UNION ALL '
            'SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid '
            'JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=current_schema() '
            'AND c.relname=? AND t.tgname=? AND NOT t.tgisinternal',
            ('parcella_incassi_proofs', *names, 'parcella_incassi_proofs', 'iusentra_receipt_proofs_immutable')).fetchall()
        names = (*names, 'iusentra_receipt_proofs_immutable')
    else:
        names = (*names, 'iusentra_receipt_proofs_no_update', 'iusentra_receipt_proofs_no_delete')
        rows = db.conn.execute("SELECT name FROM sqlite_master WHERE type IN ('index','trigger') AND tbl_name=? "
            'AND name IN (?,?,?,?)', ('parcella_incassi_proofs', *names)).fetchall()
    if {row[0] for row in rows} != set(names):
        raise InvoiceReceiptsNotPrepared('Indici o protezioni degli incassi non preparati: nessuna ricostruzione nella consultazione.')


def require_preparation_record(db, tenant):
    row = db.conn.execute('SELECT valore FROM _meta WHERE chiave=?', (marker_key(tenant),)).fetchone()
    if row is None:
        raise InvoiceReceiptsNotPrepared('Collegamenti degli incassi non preparati.')
    record = json.loads(row[0])
    if (not isinstance(record, dict) or type(record.get('version')) is not int or record.get('version') != 1 or record.get('tenant') != tenant
            or not isinstance(record.get('backup_reference'), str) or not record['backup_reference']
            or not isinstance(record.get('backup_sha256'), str) or not re.fullmatch('[a-f0-9]{64}', record['backup_sha256'])):
        raise ValueError('Preparazione degli incassi discordante: nessuna ricostruzione automatica.')
    return record


def require_live_signals(db):
    from pct.operational_live import TABLE_DOMAINS
    row = db.conn.execute("SELECT valore FROM _meta WHERE chiave='operational_live_v3'").fetchone()
    expected = {table + ':' + ','.join(TABLE_DOMAINS[table]) for table in ('parcelle', 'prima_nota_state')}
    if row is None or not expected.issubset(set(str(row[0]).split('|'))):
        raise InvoiceReceiptsNotPrepared('Sincronizzazione degli incassi non preparata.')
    if getattr(db, 'backend_kind', '') == 'postgresql':
        triggers = {row[0] for row in db.conn.execute(
            "SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=current_schema() "
            "AND c.relname IN ('parcelle','prima_nota_state') AND NOT t.tgisinternal").fetchall()}
        names = {'iusentra_live_parcelle', 'iusentra_live_prima_nota_state'}
    else:
        triggers = {row[0] for row in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name IN ('parcelle','prima_nota_state')").fetchall()}
        names = {'iusentra_live_' + table + '_' + action for table in ('parcelle', 'prima_nota_state')
                 for action in ('insert', 'update', 'delete')}
    if not names.issubset(triggers):
        raise InvoiceReceiptsNotPrepared('Produttori della sincronizzazione mancanti: preparazione necessaria.')


def financial_snapshot(db):
    result = {}
    for table, keys in (('parcelle', ('id',)), ('prima_nota_records', ('tenant_key', 'record_key'))):
        digest, count = hashlib.sha256(), 0
        last = None
        while True:
            where = '' if last is None else ' WHERE (' + ','.join(keys) + ') > (' + ','.join('?' for _ in keys) + ')'
            rows = db.conn.execute('SELECT * FROM ' + table + where + ' ORDER BY ' + ','.join(keys) + ' LIMIT 400', last or ()).fetchall()
            if not rows:
                break
            for row in rows:
                encoded = json.dumps(tuple(row[index] for index in range(len(row))), ensure_ascii=False,
                                     default=str, separators=(',', ':')).encode()
                digest.update(str(len(encoded)).encode() + b':' + encoded)
                count += 1
            cursor = tuple(rows[-1][key] for key in keys)
            if any(not isinstance(key, str) for key in cursor) or cursor == last:
                raise ValueError('Chiavi dei dati economici non riscontrate: preparazione sospesa.')
            last = cursor
        result[table] = {'records': count, 'sha256': digest.hexdigest()}
    return result


def prepare_invoice_receipts(db, tenant, destination):
    from pct.parcella_incassi_repository import ParcellaIncassiRepository
    from pct.operational_live import ensure_live_schema
    from scripts.query_index_backup import verified_backup
    repo = ParcellaIncassiRepository(db, tenant, actor_key='preparazione-incassi')
    try:
        repo.require_prepared()
        return {'changed': False}
    except InvoiceReceiptsNotPrepared:
        pass
    snapshot, digest = verified_backup(db, destination)
    before = financial_snapshot(db)
    repo.ensure_schema()
    conn = repo.cash._write_conn()
    try:
        require_live_signals(db)
    except InvoiceReceiptsNotPrepared:
        # Il marcatore tecnico viene invalidato solo dopo il backup: la
        # procedura condivisa ricrea i trigger e conserva tutti i contatori.
        conn.execute("UPDATE _meta SET valore='' WHERE chiave='operational_live_v3'")
        ensure_live_schema(conn, postgres=repo.postgres)
        repo.cash._finish(conn)
    after = financial_snapshot(db)
    if before != after:
        raise RuntimeError('Dati economici cambiati durante la preparazione: avvio sospeso.')
    record = {'version': 1, 'tenant': tenant, 'backup_reference': str(snapshot), 'backup_sha256': digest,
              'financial_snapshot': before, 'prepared_at': datetime.now(timezone.utc).isoformat()}
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True)
    conn = repo.cash._write_conn()
    try:
        if not repo.postgres:
            if conn.in_transaction:
                raise RuntimeError('Transazione estranea alla preparazione degli incassi.')
            conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT INTO _meta(chiave,valore) VALUES (?,?) ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore',
                     (marker_key(tenant), encoded))
        event_id = 'invoice-receipts-prepare:' + hashlib.sha256((tenant + str(snapshot) + digest).encode()).hexdigest()
        values = (event_id, record['prepared_at'], 'preparazione-incassi', 'preparazione-incassi',
                  'fatturazione.preparazione_incassi', 'fatturazione', tenant, encoded, '', 'OK')
        conn.execute('INSERT INTO audit_log(id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) '
                     'VALUES (?,?,?,?,?,?,?,?,?,?)', values)
        repo.require_prepared()
        repo.cash._finish(conn)
    except Exception:
        repo.cash._finish(conn, rollback=True)
        raise
    return {'changed': True, 'backup_sha256': digest, 'financial_snapshot': before}
