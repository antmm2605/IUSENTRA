"""Consultazioni indicizzate del calendario sul database proprietario risolto."""
from pct.calendar_query_projection import DOMAINS, projected_fields, source_revision
from pct.calendar_query_schema import EVENT_TYPE


class CalendarQueryNotReady(RuntimeError):
    pass


class CalendarQueryRepository:
    def __init__(self, database, tenant):
        if not tenant:
            raise ValueError('Studio proprietario del calendario non determinato.')
        self.database, self.tenant = database, tenant

    def _ready(self, domain):
        if domain not in DOMAINS:
            raise ValueError('Dominio calendario non valido.')
        conn = self.database.conn
        owner = conn.execute('SELECT tenant_key,version FROM calendar_query_owner WHERE singleton=1').fetchone()
        if owner is None or owner[0] != self.tenant or owner[1] != 1:
            raise CalendarQueryNotReady('Catalogo calendario non attribuito allo studio corrente.')
        marker = conn.execute('SELECT version FROM calendar_query_bootstrap WHERE tenant_key=? AND domain=?',
                              (self.tenant, domain)).fetchone()
        pending = conn.execute('SELECT 1 FROM transactional_outbox WHERE tenant_id=? AND aggregate_type=? '
                                "AND event_type=? AND status IN ('PENDING','FAILED') LIMIT 1",
                                (self.tenant, 'calendar_query:' + domain, EVENT_TYPE)).fetchone()
        if marker is None or marker[0] != 1 or pending is not None:
            raise CalendarQueryNotReady('Aggiornamento del catalogo calendario non ancora confermato.')

    def list_page(self, *, domain, ranges=(), states=(), kinds=(), limit=20, cursor=None):
        self._ready(domain)
        conn = self.database.conn
        where, params = ['tenant_key=?', 'domain=?', "issue<>'native_record_not_readable'"], [self.tenant, domain]
        if states:
            where.append('status IN (' + ','.join('?' for _ in states) + ')')
            params.extend(states)
        if kinds:
            where.append('kind IN (' + ','.join('?' for _ in kinds) + ')')
            params.extend(kinds)
        base = ' FROM calendar_query_index WHERE ' + ' AND '.join(where)
        # Una riga non ricostruibile può avere uno stato non determinabile:
        # non la si esclude dal report solo perché il filtro richiede uno stato.
        unreadable = int(conn.execute("SELECT COUNT(*) FROM calendar_query_index WHERE tenant_key=? AND domain=? "
                                      "AND issue='native_record_not_readable'", (self.tenant, domain)).fetchone()[0])
        unknown = int(conn.execute('SELECT COUNT(*)' + base + " AND event_day='' AND issue<>'native_record_not_readable'",
                                  tuple(params)).fetchone()[0])
        if ranges:
            periods = []
            for start, end in ranges:
                if end < start:
                    raise ValueError('Intervallo calendario invertito.')
                periods.append('(event_day>=? AND event_day<=?)')
                params.extend((start.isoformat(), end.isoformat()))
            base += ' AND (' + ' OR '.join(periods) + ')'
        if cursor:
            base += ' AND (sort_key<? OR (sort_key=? AND record_key<?))'
            params.extend((cursor[0], cursor[0], cursor[1]))
        size = max(1, min(int(limit), 100))
        rows = conn.execute('SELECT record_key,sort_key,source_revision' + base +
                            ' ORDER BY sort_key DESC,record_key DESC LIMIT ?', tuple(params + [size + 1])).fetchall()
        keys = [row[0] for row in rows[:size]]
        sources = {}
        if keys:
            selected = conn.execute('SELECT * FROM ' + DOMAINS[domain] + ' WHERE id IN (' +
                                    ','.join('?' for _ in keys) + ')', tuple(keys)).fetchall()
            sources = {str(row['id']): dict(row) for row in selected}
        values = []
        for row in rows[:size]:
            raw = sources.get(row[0])
            if raw is None or source_revision(raw) != row[2]:
                raise CalendarQueryNotReady('La fonte calendario è cambiata: aggiornamento mirato necessario.')
            values.append(dict(raw))
        self._ready(domain)
        return dict(rows=values, has_more=len(rows) > size,
                    cursor=(rows[size - 1][1], rows[size - 1][0]) if len(rows) > size else None,
                    unknown_date_count=unknown, unreadable_count=unreadable)

    def project_record(self, conn, *, domain, key, row):
        """Solo worker/scrittore nativo, all'interno della propria transazione."""
        if domain not in DOMAINS:
            raise ValueError('Dominio calendario non valido.')
        if row is None:
            conn.execute('DELETE FROM calendar_query_index WHERE tenant_key=? AND domain=? AND record_key=?',
                         (self.tenant, domain, key))
            return
        if str(row['id']) != key:
            raise ValueError('Identità della fonte calendario discordante.')
        values = projected_fields(domain, row)
        fields = ('event_day', 'sort_key', 'status', 'title', 'source_revision', 'issue', 'kind')
        conn.execute('INSERT INTO calendar_query_index(tenant_key,domain,record_key,' + ','.join(fields) + ') '
                     'VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_key,domain,record_key) DO UPDATE SET ' +
                     ','.join(name + '=excluded.' + name for name in fields),
                     (self.tenant, domain, key, *(values[name] for name in fields)))

    def retry_events(self, *, domain, limit=50):
        from pct.query_projection_worker import deliver_pending

        if domain not in DOMAINS:
            raise ValueError('Dominio calendario non valido.')
        writable = getattr(self.database, '_conn_per_scrittura', None)
        conn = writable() if callable(writable) else self.database.conn
        owner = conn.execute('SELECT tenant_key FROM calendar_query_owner WHERE singleton=1').fetchone()
        if owner is None or owner[0] != self.tenant:
            raise CalendarQueryNotReady('Studio proprietario del calendario non riscontrato.')
        marker = conn.execute('SELECT version FROM calendar_query_bootstrap WHERE tenant_key=? AND domain=?',
                              (self.tenant, domain)).fetchone()
        if marker is None or marker[0] != 1:
            raise CalendarQueryNotReady('Migrazione calendario non ancora confermata.')
        def finish(connection, *, rollback=False):
            target = getattr(self.database, 'raw_conn', None) or connection
            target.rollback() if rollback else target.commit()
        def project(connection, key):
            row = connection.execute('UPDATE ' + DOMAINS[domain] + ' SET id=id WHERE id=? RETURNING *', (key,)).fetchone()
            self.project_record(connection, domain=domain, key=key, row=row)
        return deliver_pending(conn=conn, finish=finish, tenant=self.tenant,
                               aggregate='calendar_query:' + domain, event_type=EVENT_TYPE,
                               project=project, limit=limit)
