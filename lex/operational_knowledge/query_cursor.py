"""Continuazione firmata della consultazione, vincolata a studio e utente."""
from datetime import date

from flask import current_app
from itsdangerous import BadData, URLSafeTimedSerializer

from .query_dates import QueryDates
from .query_selection import QuerySelection


def _serializer():
    secret = current_app.secret_key
    if not secret:
        raise ValueError('Sessione di consultazione non disponibile.')
    return URLSafeTimedSerializer(secret, salt='lex-operational-query-v1')


def encode_query_cursor(context, selection, cursor):
    return _serializer().dumps({
        'v': 1, 'tenant': context.tenant_id, 'user': context.user_id,
        'domain': selection.domain, 'direction': selection.direction,
        'folder': selection.folder,
        'states': list(selection.states), 'date_axis': selection.date_axis, 'kinds': list(selection.kinds),
        'ranges': [[start.isoformat(), end.isoformat()] for start, end in selection.dates.ranges],
        'cursor': list(cursor),
    })


def decode_query_cursor(token, context, *, max_age=1800):
    try:
        if not isinstance(token, str) or len(token) > 8192:
            raise ValueError('Formato non valido.')
        value = _serializer().loads(token, max_age=max_age)
        domain = value.get('domain')
        if value.get('v') != 1 or domain not in {'pec', 'legal_notifications', 'agenda', 'deadlines', 'deposits', 'archived_receipts'}:
            raise ValueError('Dominio non valido.')
        if value.get('tenant') != context.tenant_id or value.get('user') != context.user_id:
            raise ValueError('Sessione diversa.')
        ranges = tuple((date.fromisoformat(start), date.fromisoformat(end)) for start, end in value['ranges'])
        if len(ranges) > 32 or any(end < start for start, end in ranges):
            raise ValueError('Periodo non valido.')
        cursor = value['cursor']
        if not isinstance(cursor, list) or len(cursor) != 2 or any(not isinstance(item, str) or len(item) > 1024 for item in cursor):
            raise ValueError('Cursore non valido.')
        direction, folder = value.get('direction', ''), value.get('folder', '')
        if direction not in {'', 'received', 'sent'} or folder not in {'', 'trash'}:
            raise ValueError('Filtri non validi.')
        if domain == 'archived_receipts':
            states = tuple(value.get('states') or ())
            if len(states) != 1 or states[0] not in {'rac', 'rdac'} or direction or folder or value.get('date_axis') != 'receipt_at' or value.get('kinds'):
                raise ValueError('Filtri delle prove archiviate non validi.')
            return QuerySelection(domain, QueryDates(ranges), states=states, date_axis='receipt_at'), tuple(cursor)
        if domain == 'deposits':
            states = tuple(value.get('states') or ())
            axis = {'ACCETTATO_PEC': 'pec_acceptance_at', 'ACCETTATO_CANCELLERIA': 'registry_acceptance_at'}.get(
                states[0] if len(states) == 1 else '')
            if not axis or direction or folder or value.get('date_axis') != axis or value.get('kinds'):
                raise ValueError('Filtri delle ricevute di deposito non validi.')
            return QuerySelection(domain, QueryDates(ranges), states=states, date_axis=axis), tuple(cursor)
        if domain in {'agenda', 'deadlines'}:
            states, kinds = tuple(value.get('states') or ()), tuple(value.get('kinds') or ())
            allowed = {'PROGRAMMATO', 'CONFERMATO', 'COMPLETATO', 'ANNULLATO', 'RINVIATO'} if domain == 'agenda' else {'APERTO', 'COMPLETATO', 'ANNULLATO', 'BOZZA', 'SCADUTO'}
            axis = 'appointment_at' if domain == 'agenda' else 'due_on'
            if not set(states).issubset(allowed) or kinds not in {(), ('UDIENZA',)} or direction or folder or value.get('date_axis') != axis:
                raise ValueError('Filtri calendario non validi.')
            return QuerySelection(domain, QueryDates(ranges), states=states, kinds=kinds, date_axis=axis), tuple(cursor)
        if domain == 'legal_notifications':
            states = tuple(value.get('states') or ())
            axis = {'rac_received': 'rac_at', 'pending': 'due_on'}.get(states[0] if len(states) == 1 else '')
            if not axis or direction or folder or value.get('date_axis') != axis:
                raise ValueError('Filtri delle notificazioni non validi.')
            return QuerySelection(domain, QueryDates(ranges), states=states, date_axis=axis), tuple(cursor)
        return QuerySelection('pec', QueryDates(ranges), direction=direction, folder=folder, date_axis='message_at'), tuple(cursor)
    except (BadData, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError('La ricerca è scaduta o non appartiene alla sessione corrente. Ripeti la domanda con i filtri desiderati.') from exc
