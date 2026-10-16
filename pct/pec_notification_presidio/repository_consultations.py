"""Consultazioni datate dei presìdi, senza riconciliazione o nuove decisioni."""
from datetime import UTC, datetime, time, timedelta

from pct.formatting import DISPLAY_TIMEZONE

from .models import TERMINAL_STATUSES


def timestamp_key_sql(field, *, postgres=False):
    """Chiave UTC dei timestamp già canonici del repository.

    Conserva anche i microsecondi: ordinare direttamente una stringa con Z
    mescolata a una con frazione invertirebbe i valori dello stesso secondo.
    ``field`` è una definizione SQL interna, mai un parametro della domanda.
    """
    if postgres:
        return f"COALESCE(to_char({field} AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US'),'')"
    value = f"rtrim({field},'Z')"
    return (f"CASE WHEN {field} IS NULL OR {field}='' THEN '' "
            f"WHEN substr({value},20,1)='.' THEN substr({value} || '000000',1,26) "
            f"ELSE substr({value},1,19) || '.000000' END")


CONSULTATION_INDEXES = (
    'CREATE INDEX IF NOT EXISTS idx_pec_notification_query_due '
    'ON pec_legal_notification_presidia(tenant_id,status,explicit_due_at,id)',
    'CREATE INDEX IF NOT EXISTS idx_pec_notification_query_rac '
    'ON pec_legal_notification_transitions(tenant_id,next_status,presidio_id,occurred_at)',
)


class NotificationPresidioConsultationMixin:
    def list_operational_page(self, *, mode, ranges=(), limit=20, cursor=None):
        if mode not in {'accepted', 'pending'}:
            raise ValueError('Indica notificazioni accettate oppure con attività da completare.')
        size = max(1, min(int(limit), 100))
        params = [self.tenant_id]
        where = ['p.tenant_id=?']
        joins = ''
        postgres = self.backend_kind == 'postgresql'
        if mode == 'accepted':
            joins = ("LEFT JOIN (SELECT presidio_id,MAX(" + timestamp_key_sql('occurred_at', postgres=postgres) + ") AS rac_at "
                     "FROM pec_legal_notification_transitions WHERE tenant_id=? AND next_status='RAC_RECEIVED' "
                     'GROUP BY presidio_id) a ON a.presidio_id=p.id')
            params.insert(0, self.tenant_id)
            stamp = "COALESCE(a.rac_at,'')"
            where.extend([
                'EXISTS (SELECT 1 FROM pec_legal_notification_recipients r WHERE r.tenant_id=p.tenant_id '
                'AND r.presidio_id=p.id AND r.required=TRUE)',
                'NOT EXISTS (SELECT 1 FROM pec_legal_notification_recipients r WHERE r.tenant_id=p.tenant_id '
                "AND r.presidio_id=p.id AND r.required=TRUE AND (r.rac_status<>'received' OR r.rac_message_id=''))",
            ])
        else:
            states = sorted(str(value) for value in TERMINAL_STATUSES)
            where.append('p.status NOT IN (' + ','.join('?' for _ in states) + ')')
            params.extend(states)
            stamp = timestamp_key_sql('p.explicit_due_at', postgres=postgres)
        base = ' FROM pec_legal_notification_presidia p ' + joins + ' WHERE ' + ' AND '.join(where)
        with self.connection() as conn:
            unknown = int(conn.execute('SELECT COUNT(*)' + base + f" AND ({stamp})=''", tuple(params)).fetchone()[0])
            periods = []
            for start, end in ranges:
                if end < start:
                    raise ValueError('Intervallo della consultazione invertito.')
                lower = datetime.combine(start, time.min, DISPLAY_TIMEZONE).astimezone(UTC).replace(tzinfo=None)
                upper = datetime.combine(end + timedelta(days=1), time.min, DISPLAY_TIMEZONE).astimezone(UTC).replace(tzinfo=None)
                periods.append(f'(({stamp})>=? AND ({stamp})<?)')
                params.extend((lower.isoformat(timespec='microseconds'), upper.isoformat(timespec='microseconds')))
            if periods:
                base += ' AND (' + ' OR '.join(periods) + ')'
            if cursor:
                base += f' AND (({stamp})<? OR (({stamp})=? AND p.id<?))'
                params.extend((cursor[0], cursor[0], cursor[1]))
            rows = conn.execute('SELECT p.id,p.fascicolo_id,p.status,p.source_message_id,'
                                f'p.explicit_due_at,p.notification_case,({stamp}) AS query_event_key' + base +
                                ' ORDER BY query_event_key DESC,p.id DESC LIMIT ?', tuple(params + [size + 1])).fetchall()
            selected = [self._row(row) for row in rows[:size]]
        for row in selected:
            row['event_at'] = row['query_event_key'] + 'Z' if row['query_event_key'] else ''
            row['date_axis'] = 'rac_at' if mode == 'accepted' else 'due_on'
        has_more = len(rows) > size
        return {'rows': selected, 'has_more': has_more, 'unknown_date_count': unknown,
                'cursor': (selected[-1]['query_event_key'], selected[-1]['id']) if has_more else None}
