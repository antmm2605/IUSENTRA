"""Catalogo derivato delle ricevute già lette nel repository PEC proprietario."""
from datetime import UTC, datetime, time, timedelta

from pct.formatting import DISPLAY_TIMEZONE
from pct.pec_deposit_query_projection import projected_receipt
from pct.query_projection_outbox import install_source_trigger
from pct.transactional_outbox import POSTGRES_SCHEMA

DDL = (
    '''CREATE TABLE IF NOT EXISTS pec_deposit_query_index (
        tenant_id TEXT NOT NULL,message_id TEXT NOT NULL,report_id TEXT NOT NULL,
        source_revision TEXT NOT NULL,mime_sha256 TEXT NOT NULL,state TEXT NOT NULL,
        event_at TEXT NOT NULL,correlation_key TEXT NOT NULL,case_id TEXT NOT NULL,
        candidate_case_id TEXT NOT NULL,title TEXT NOT NULL,issue TEXT NOT NULL,
        PRIMARY KEY(tenant_id,message_id))''',
    '''CREATE INDEX IF NOT EXISTS idx_pec_deposit_query_period
        ON pec_deposit_query_index(tenant_id,state,event_at,message_id)''',
    '''CREATE INDEX IF NOT EXISTS idx_pec_deposit_query_case
        ON pec_deposit_query_index(tenant_id,case_id,state,event_at,message_id)''',
    '''CREATE INDEX IF NOT EXISTS idx_pec_deposit_query_issue
        ON pec_deposit_query_index(tenant_id,state,issue,message_id)''',
    '''CREATE TABLE IF NOT EXISTS pec_deposit_query_bootstrap (
        tenant_id TEXT PRIMARY KEY,version INTEGER NOT NULL)''',
)

EVENT_TYPE = 'pec_deposit_query.refresh_requested'
AGGREGATE = 'pec_deposit_query'


def install_deposit_query_events(conn, *, postgres=False):
    for statement in DDL:
        conn.execute(statement)
    for statement in POSTGRES_SCHEMA.split(';'):
        if statement.strip():
            conn.execute(statement)
    conn.execute('CREATE INDEX IF NOT EXISTS idx_outbox_deposit_query_pending '
                 'ON transactional_outbox(tenant_id,aggregate_type,event_type,status,aggregate_id)')
    for table in ('pec_validation_reports', 'pec_messages', 'pec_fascicolo_links', 'pec_parsed_versions'):
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            direct = table == 'pec_messages'
            tenant = '{row}.tenant_id' if direct else '(SELECT tenant_id FROM pec_messages WHERE id={row}.message_id)'
            key = '{row}.id' if direct else '{row}.message_id'
            predicate = tenant + ' IS NOT NULL'
            if action == 'UPDATE':
                fields = ('mime_sha256', 'linked_fascicolo_id') if direct else (
                    ('report_json', 'report_sha256', 'parsed_version_id', 'event_type', 'created_at')
                    if table == 'pec_validation_reports' else
                    ('version',) if table == 'pec_parsed_versions' else ('fascicolo_id', 'status', 'created_at'))
                equal = ' AND '.join(f'(OLD.{field}=NEW.{field} OR (OLD.{field} IS NULL AND NEW.{field} IS NULL))' for field in fields)
                predicate += f' AND NOT COALESCE(({equal}),FALSE)'
            install_source_trigger(conn, table=table, action=action,
                name=f'iusentra_deposit_query_{table}_{action.lower()}', tenant_sql=tenant,
                aggregate_sql="'pec_deposit_query'", key_sql=key, event_type=EVENT_TYPE,
                predicate=predicate, postgres=postgres)
    install_source_trigger(conn, table='pec_deposit_query_index', action='DELETE',
        name='iusentra_deposit_query_index_delete', tenant_sql='{row}.tenant_id',
        aggregate_sql="'pec_deposit_query'", key_sql='{row}.message_id', event_type=EVENT_TYPE,
        predicate="EXISTS (SELECT 1 FROM pec_validation_reports r WHERE r.message_id={row}.message_id AND r.event_type='pct_deposito')",
        postgres=postgres)


class PecDepositQueryRepository:
    def __init__(self, conn, tenant):
        if not tenant:
            raise ValueError('Studio delle ricevute non determinato.')
        self.conn, self.tenant = conn, tenant

    def _ready(self):
        marker = self.conn.execute('SELECT version FROM pec_deposit_query_bootstrap WHERE tenant_id=?', (self.tenant,)).fetchone()
        pending = self.conn.execute('SELECT 1 FROM transactional_outbox WHERE tenant_id=? AND aggregate_type=? AND event_type=? '
                                    "AND status IN ('PENDING','FAILED') LIMIT 1", (self.tenant, AGGREGATE, EVENT_TYPE)).fetchone()
        if marker is None or marker[0] != 1 or pending is not None:
            raise RuntimeError('Catalogo delle ricevute di deposito non ancora confermato.')

    def list_page(self, *, state, ranges=(), limit=20, cursor=None):
        if state not in {'ACCETTATO_PEC', 'ACCETTATO_CANCELLERIA'}:
            raise ValueError('Indica accettazione PEC oppure accettazione della cancelleria.')
        self._ready()
        conn = self.conn
        where, params = ['q.tenant_id=?', 'q.state=?'], [self.tenant, state]
        unknown = int(conn.execute("SELECT COUNT(*) FROM pec_deposit_query_index q WHERE q.tenant_id=? AND q.state=? AND q.event_at=''",
                                   tuple(params)).fetchone()[0])
        unconfirmed = int(conn.execute("SELECT COUNT(*) FROM pec_deposit_query_index WHERE tenant_id=? AND state='' AND issue<>''",
                                       (self.tenant,)).fetchone()[0])
        issues = [dict(row) for row in conn.execute(
            "SELECT message_id,report_id,title,issue FROM pec_deposit_query_index WHERE tenant_id=? AND state='' AND issue<>'' ORDER BY message_id LIMIT 20",
            (self.tenant,)).fetchall()]
        periods = []
        for start, end in ranges:
            if end < start:
                raise ValueError('Intervallo delle ricevute invertito.')
            lower = datetime.combine(start, time.min, DISPLAY_TIMEZONE).astimezone(UTC)
            upper = datetime.combine(end + timedelta(days=1), time.min, DISPLAY_TIMEZONE).astimezone(UTC)
            periods.append('(q.event_at>=? AND q.event_at<?)')
            params.extend((lower.isoformat(timespec='microseconds'), upper.isoformat(timespec='microseconds')))
        if periods:
            where.append('(' + ' OR '.join(periods) + ')')
        if cursor:
            where.append('(q.event_at<? OR (q.event_at=? AND q.message_id<?))')
            params.extend((cursor[0], cursor[0], cursor[1]))
        size = max(1, min(int(limit), 100))
        rows = conn.execute('SELECT q.*,r.report_sha256 AS current_report_sha256,m.mime_sha256 AS current_mime_sha256 '
            'FROM pec_deposit_query_index q JOIN pec_validation_reports r ON r.id=q.report_id '
            'JOIN pec_messages m ON m.id=q.message_id AND m.tenant_id=q.tenant_id WHERE ' + ' AND '.join(where) +
            ' ORDER BY q.event_at DESC,q.message_id DESC LIMIT ?', tuple(params + [size + 1])).fetchall()
        values = [dict(row) for row in rows[:size]]
        if any(row['source_revision'] != row['current_report_sha256'] or row['mime_sha256'] != row['current_mime_sha256'] for row in values):
            raise RuntimeError('Fonte della ricevuta modificata: aggiornamento mirato necessario.')
        self._ready()
        return dict(rows=values, unknown_date_count=unknown, unconfirmed_source_count=unconfirmed,
                    unconfirmed_sources=issues, has_more=len(rows) > size,
                    cursor=(values[-1]['event_at'], values[-1]['message_id']) if len(rows) > size else None)

    def retry_events(self, *, finish, limit=50):
        from pct.query_projection_worker import deliver_pending

        return deliver_pending(conn=self.conn, finish=finish, tenant=self.tenant, aggregate=AGGREGATE,
                               event_type=EVENT_TYPE, project=self.project_message, limit=limit)

    def project_message(self, conn, message_id):
        # Serializza due consegne dello stesso messaggio senza cambiare la
        # fonte; i trigger ignorano questo aggiornamento identico.
        present = conn.execute('UPDATE pec_messages SET id=id WHERE tenant_id=? AND id=? RETURNING id',
                               (self.tenant, message_id)).fetchone()
        if present is None:
            conn.execute('DELETE FROM pec_deposit_query_index WHERE tenant_id=? AND message_id=?', (self.tenant, message_id))
            return
        row = conn.execute(
            'SELECT r.id,r.message_id,r.event_type,r.report_json,r.report_sha256,m.mime_sha256,m.linked_fascicolo_id,'
            '(SELECT l.status FROM pec_fascicolo_links l WHERE l.message_id=m.id AND l.fascicolo_id=m.linked_fascicolo_id '
            'ORDER BY l.created_at DESC,l.id DESC LIMIT 1) AS case_link_status '
            'FROM pec_validation_reports r JOIN pec_messages m ON m.id=r.message_id '
            'JOIN pec_parsed_versions p ON p.id=r.parsed_version_id '
            'WHERE m.tenant_id=? AND m.id=? '
            'ORDER BY p.version DESC,r.created_at DESC,r.id DESC LIMIT 1', (self.tenant, message_id)).fetchone()
        if row is None or row['event_type'] != 'pct_deposito':
            conn.execute('DELETE FROM pec_deposit_query_index WHERE tenant_id=? AND message_id=?', (self.tenant, message_id))
            return
        previous = conn.execute('SELECT mime_sha256,source_revision FROM pec_deposit_query_index '
                                'WHERE tenant_id=? AND message_id=?', (self.tenant, message_id)).fetchone()
        bound_hash = str(previous[0]) if previous else str(row['mime_sha256'] or '')
        source_changed = bool(previous and bound_hash != str(row['mime_sha256'] or ''))
        try:
            # Un nuovo hash del messaggio non rende attuale il vecchio report.
            # Conservare il vincolo precedente anche nei retry, senza leggere
            # il MIME o avviare il motore PEC da questa proiezione consultiva.
            if source_changed:
                raise ValueError('Fonte MIME sostituita: analisi originaria non applicabile.')
            value = projected_receipt(row)
        except (ValueError, TypeError, KeyError):
            # Una fonte malformata non diventa un esito certo e non impedisce
            # di consultare gli altri esiti. L'indice conserva un esito
            # negativo esplicito, con i puntatori alla fonte originale.
            value = dict(report_id=str(row['id']), source_revision=str(row['report_sha256']),
                         source_mime_sha256=bound_hash, state='', event_at='',
                         correlation_key='', case_id='', candidate_case_id=str(row['linked_fascicolo_id'] or ''),
                         title='Ricevuta di deposito da verificare',
                         issue='receipt_source_revision_changed' if source_changed else 'receipt_report_not_confirmed')
        fields = ('report_id', 'source_revision', 'mime_sha256', 'state', 'event_at', 'correlation_key', 'case_id', 'candidate_case_id', 'title', 'issue')
        values = (value['report_id'], value['source_revision'], value['source_mime_sha256'], value['state'], value['event_at'],
                  value['correlation_key'], value['case_id'], value['candidate_case_id'], value['title'], value['issue'])
        conn.execute('INSERT INTO pec_deposit_query_index(tenant_id,message_id,' + ','.join(fields) + ') '
                     'VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,message_id) DO UPDATE SET ' +
                     ','.join(field + '=excluded.' + field for field in fields), (self.tenant, message_id, *values))
