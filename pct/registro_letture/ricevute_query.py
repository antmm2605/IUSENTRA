"""Catalogo SQL delle prove di trasporto già lette, distinto dai presìdi legali."""
import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta

from pct.formatting import DISPLAY_TIMEZONE
from pct.query_projection_outbox import install_source_trigger
from pct.registro_letture.ricevute_consultazione import _receipt_date, group_exact_receipt_copies, receipt_sources
from pct.transactional_outbox import POSTGRES_SCHEMA

AGGREGATE = 'receipt_archive_query'
EVENT = 'receipt_archive.refresh_requested'


def reader_signature():
    from pct.registro_letture.lettori import versioni_compatibili_lettore

    versions = {key: versioni_compatibili_lettore(key) for key in ('motore_documenti', 'motore_pec')}
    return hashlib.sha256(json.dumps(versions, sort_keys=True).encode()).hexdigest()


def install(conn, tenant, *, postgres=False):
    for statement in POSTGRES_SCHEMA.split(';'):
        if statement.strip():
            conn.execute(statement)
    conn.execute("CREATE TABLE IF NOT EXISTS receipt_archive_query_owner "
                 "(tenant_id TEXT PRIMARY KEY,ready INTEGER NOT NULL DEFAULT 0,after_case TEXT NOT NULL DEFAULT '',"
                 "backup_reference TEXT NOT NULL,reader_signature TEXT NOT NULL)")
    conn.execute('CREATE TABLE IF NOT EXISTS receipt_archive_query_rows '
                 '(tenant_id TEXT NOT NULL,id TEXT NOT NULL,case_id TEXT NOT NULL,kind TEXT NOT NULL,'
                 'event_at TEXT NOT NULL,source_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(tenant_id,id))')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_receipt_archive_period ON receipt_archive_query_rows(tenant_id,kind,event_at,id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_receipt_archive_case ON receipt_archive_query_rows(tenant_id,case_id,id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_receipt_archive_outbox '
                 'ON transactional_outbox(tenant_id,aggregate_type,event_type,status,aggregate_id)')
    signature = reader_signature()
    conn.execute('INSERT INTO receipt_archive_query_owner(tenant_id,backup_reference,reader_signature) VALUES (?,?,?) '
                 'ON CONFLICT(tenant_id) DO NOTHING', (tenant, '', signature))
    conn.execute("UPDATE receipt_archive_query_owner SET ready=0,after_case='',reader_signature=? "
                 'WHERE tenant_id=? AND reader_signature<>?', (signature, tenant, signature))
    owner = 'EXISTS (SELECT 1 FROM receipt_archive_query_owner WHERE tenant_id={row}.tenant_id)'
    for table in ('letture_fatti', 'letture_oggetti'):
        if table == 'letture_fatti':
            relevant = "(({row}.categoria='prova_notifica' AND {row}.campo IN ('rac','rdac','deposito_prova')) OR " \
                       "({row}.categoria='data' AND {row}.campo IN ('accettazione','consegna')))"
        else:
            relevant = "EXISTS (SELECT 1 FROM letture_fatti f WHERE f.tenant_id={row}.tenant_id AND " \
                       "f.fascicolo_id={row}.fascicolo_id AND f.tipo={row}.tipo AND f.oggetto_id={row}.oggetto_id " \
                       "AND f.categoria='prova_notifica' AND f.campo IN ('rac','rdac','deposito_prova'))"
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            condition = relevant if action != 'UPDATE' else '(' + relevant.replace('{row}', 'OLD') + ' OR ' + relevant.replace('{row}', 'NEW') + ')'
            if action == 'UPDATE':
                fields = ('tenant_id', 'fascicolo_id', 'tipo', 'oggetto_id', 'sha256') + (
                    ('categoria', 'campo', 'valore', 'verifica', 'motore', 'versione_motore', 'prove_json')
                    if table == 'letture_fatti' else ('nome', 'presente'))
                same = ' AND '.join(f'(OLD.{field}=NEW.{field} OR (OLD.{field} IS NULL AND NEW.{field} IS NULL))' for field in fields)
                condition += ' AND NOT COALESCE((' + same + '),FALSE)'
            install_source_trigger(conn, table=table, action=action,
                name=f'iusentra_receipt_archive_{table}_{action.lower()}', tenant_sql='{row}.tenant_id',
                aggregate_sql="'receipt_archive_query'", key_sql='{row}.fascicolo_id', event_type=EVENT,
                predicate=owner + ' AND ' + condition, postgres=postgres)
        install_source_trigger(conn, table=table, action='UPDATE',
            name=f'iusentra_receipt_archive_{table}_old_owner', tenant_sql='OLD.tenant_id',
            aggregate_sql="'receipt_archive_query'", key_sql='OLD.fascicolo_id', event_type=EVENT,
            predicate=owner.replace('{row}', 'OLD') + ' AND ' + relevant.replace('{row}', 'OLD') +
                      ' AND (OLD.tenant_id<>NEW.tenant_id OR OLD.fascicolo_id<>NEW.fascicolo_id)', postgres=postgres)


class ReceiptArchiveQuery:
    def __init__(self, conn, tenant):
        if not tenant:
            raise ValueError('Studio delle prove archiviate non determinato.')
        self.conn, self.tenant = conn, tenant

    def project_case(self, registry, case_id):
        recovered = [row[0] for row in self.conn.execute('SELECT id FROM transactional_outbox WHERE tenant_id=? '
            "AND aggregate_type=? AND event_type=? AND aggregate_id=? AND status='FAILED'",
            (self.tenant, AGGREGATE, EVENT, case_id)).fetchall()]
        sources, cursor = [], ''
        for _ in range(20):
            page = receipt_sources(registry, tenant=self.tenant, case_ids=[case_id], cursor=cursor, limit=500)
            sources.extend(page['rows'])
            if not page['has_more']:
                break
            cursor = page['cursor']
        else:
            raise RuntimeError('Budget delle prove del fascicolo superato: nessun catalogo parziale confermato.')
        groups = group_exact_receipt_copies(sources)
        self.conn.execute('DELETE FROM receipt_archive_query_rows WHERE tenant_id=? AND case_id=?', (self.tenant, case_id))
        for group in groups:
            evidence = group['sources']
            dates = {row['event_date'] for row in evidence if row['event_date']}
            stamp, date_issue, precision = _receipt_date(dates)
            event_at = ''
            if stamp:
                parsed = datetime.combine(date.fromisoformat(stamp), time.min, DISPLAY_TIMEZONE) if precision == 'day' else datetime.fromisoformat(stamp)
                event_at = parsed.astimezone(UTC).isoformat(timespec='microseconds')
            payload = dict(group, date_issue=date_issue, date_precision=precision, event_at=event_at,
                           title=evidence[0]['nome'], source_type='archived_transport_receipt',
                           legal_notification_confirmed=False)
            identity = [case_id, group['campo'], evidence[0]['sha256']] if group['verified'] else ['unconfirmed', evidence[0]['id']]
            key = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
            self.conn.execute('INSERT INTO receipt_archive_query_rows VALUES (?,?,?,?,?,?,?)',
                (self.tenant, key, case_id, group['campo'], event_at, evidence[0]['sha256'], json.dumps(payload, ensure_ascii=False)))
        for event_id in recovered:
            self.conn.execute("UPDATE transactional_outbox SET status='PROCESSED',processed_at=?,"
                "last_error=COALESCE(last_error,'') || ' [Recuperato da proiezione successiva della stessa fonte.]' "
                "WHERE id=? AND tenant_id=? AND status='FAILED'", (datetime.now(UTC).isoformat(), event_id, self.tenant))

    def ready(self):
        owner = self.conn.execute('SELECT ready,reader_signature FROM receipt_archive_query_owner WHERE tenant_id=?', (self.tenant,)).fetchone()
        pending = self.conn.execute('SELECT 1 FROM transactional_outbox WHERE tenant_id=? AND aggregate_type=? '
                                    "AND event_type=? AND status IN ('PENDING','FAILED') LIMIT 1",
                                    (self.tenant, AGGREGATE, EVENT)).fetchone()
        if not owner or owner[0] != 1 or owner[1] != reader_signature() or pending:
            raise RuntimeError('Catalogo delle prove archiviate non ancora confermato.')

    def list_page(self, *, ranges=(), kind='', limit=20, cursor=None):
        self.ready()
        if kind not in {'', 'rac', 'rdac', 'deposito_prova'}:
            raise ValueError('Tipo di prova non supportato.')
        where, params = ['tenant_id=?'], [self.tenant]
        if kind:
            where.append('kind=?')
            params.append(kind)
        base, base_params = ' AND '.join(where), tuple(params)
        unknown = self.conn.execute('SELECT COUNT(*) FROM receipt_archive_query_rows WHERE ' + base + " AND event_at=''", base_params).fetchone()[0]
        periods = []
        for start, end in ranges:
            if end < start:
                raise ValueError('Intervallo delle prove invertito.')
            lower = datetime.combine(start, time.min, DISPLAY_TIMEZONE).astimezone(UTC)
            upper = datetime.combine(end + timedelta(days=1), time.min, DISPLAY_TIMEZONE).astimezone(UTC)
            periods.append('(event_at>=? AND event_at<?)')
            params.extend((lower.isoformat(timespec='microseconds'), upper.isoformat(timespec='microseconds')))
        if periods:
            where.append('(' + ' OR '.join(periods) + ')')
        if cursor:
            where.append('(event_at<? OR (event_at=? AND id<?))')
            params.extend((cursor[0], cursor[0], cursor[1]))
        size = max(1, min(int(limit), 100))
        rows = self.conn.execute('SELECT id,payload_json FROM receipt_archive_query_rows WHERE ' + ' AND '.join(where) +
                                 ' ORDER BY event_at DESC,id DESC LIMIT ?', (*params, size + 1)).fetchall()
        self.ready()
        result = [dict(json.loads(row[1]), id=row[0]) for row in rows[:size]]
        return dict(rows=result, unknown_date_count=int(unknown), has_more=len(rows) > size,
                    cursor=(result[-1]['event_at'], result[-1]['id']) if len(rows) > size else None)
