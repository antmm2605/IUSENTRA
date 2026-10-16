"""Metadati consultivi ricavati dai modelli nativi, senza aprire gestori."""
import hashlib
import json
from datetime import UTC, datetime, time

from pct.calendar_sql_records import appointment_from_row, deadline_from_row
from pct.formatting import DISPLAY_TIMEZONE

DOMAINS = {'agenda': 'appuntamenti', 'deadlines': 'scadenze'}


def source_revision(row):
    return hashlib.sha256(json.dumps(dict(row), ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


def projected_fields(domain, row):
    if domain not in DOMAINS:
        raise ValueError('Dominio calendario non valido.')
    revision = source_revision(row)
    try:
        model = appointment_from_row(row) if domain == 'agenda' else deadline_from_row(row)
        if domain == 'agenda':
            local = model.data_ora_dt
            value = local.replace(tzinfo=DISPLAY_TIMEZONE)
        else:
            due = model.data_scadenza_obj
            value = datetime.combine(due, time.min, DISPLAY_TIMEZONE) if due else None
        return dict(event_day=value.date().isoformat() if value else '',
                    sort_key=value.astimezone(UTC).isoformat(timespec='microseconds') if value else '',
                    status=model.stato.value, title=model.titolo, kind=model.tipo.value,
                    source_revision=revision, issue='' if value else 'date_not_available')
    except (ValueError, TypeError, KeyError, RuntimeError, AttributeError):
        # Non fabbrica uno stato o una data per rendere interrogabile una fonte
        # non ricostruibile. La discordanza resta distinguibile dall'assenza.
        return dict(event_day='', sort_key='', status='', title='', kind='', source_revision=revision,
                    issue='native_record_not_readable')
