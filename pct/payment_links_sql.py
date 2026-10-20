"""Scritture puntuali dei link: nessuna sostituzione dell'archivio concorrente."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation


COLUMNS = ('id', 'token', 'id_parcella', 'id_cliente', 'importo', 'valuta', 'stato',
           'provider_usato', 'provider_tx_id', 'creato_il', 'scade_il', 'pagato_il', 'dati_json')


class PaymentLinkConflict(ValueError):
    pass


def _encoded(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _read_source_row(conn, key, *, lock=False, by_token=False):
    field = 'token' if by_token else 'id'
    return conn.execute('SELECT ' + ','.join(COLUMNS) + ' FROM payment_links WHERE ' + field + '=?'
                       + (' FOR UPDATE' if lock else ''), (key,)).fetchone()


def _source(conn, key, *, lock=False, by_token=False):
    row = _read_source_row(conn, key, lock=lock, by_token=by_token)
    if row is None:
        return None, None
    return _validated_source(row), row[len(COLUMNS) - 1]


def _validated_source(row):
    payload = json.loads(row[len(COLUMNS) - 1])
    if not isinstance(payload, dict):
        raise PaymentLinkConflict('Fonte del collegamento non valida.')
    for index, column in enumerate(COLUMNS[:-1]):
        if column == 'importo':
            try:
                value, actual = Decimal(str(payload.get(column))), Decimal(str(row[index]))
                equal = value.is_finite() and actual.is_finite() and value == actual
            except (InvalidOperation, ValueError):
                equal = False
        else:
            equal = (payload.get(column) or '') == (row[index] or '')
        if not equal:
            raise PaymentLinkConflict('Collegamento discordante dalla fonte SQL: verifica necessaria.')
    return payload


def read_link(database, *, key=None, token=None):
    if (key is None) == (token is None):
        raise ValueError('Indicare un solo riferimento del collegamento.')
    return _source(database.conn, key if key is not None else token, by_token=token is not None)[0]


def read_links(database, *, client_id=None, invoice_id=None, pending=False, limit=None):
    clauses, values = [], []
    for column, value in (('id_cliente', client_id), ('id_parcella', invoice_id)):
        if value is not None:
            clauses.append(column + '=?')
            values.append(value)
    if pending:
        clauses.append('stato=?')
        values.append('ATTESO')
    sql = 'SELECT ' + ','.join(COLUMNS) + ' FROM payment_links'
    if clauses:
        sql += ' WHERE ' + ' AND '.join(clauses)
    sql += " ORDER BY CASE WHEN COALESCE(creato_il,'')='' THEN 1 ELSE 0 END,creato_il DESC,id"
    if limit is not None:
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError('Lotto dei collegamenti non valido.')
        sql += ' LIMIT ?'
        values.append(limit)
    return [_validated_source(row) for row in database.conn.execute(sql, values).fetchall()]


def save_links(database, links, originals, saved, *, before_write=None, after_write=None):
    desired = {key: {**originals.get(key, {}), **link.to_dict()} for key, link in links.items()}
    changes = {key: payload for key, payload in desired.items() if links[key].to_dict() != saved.get(key)}
    if not changes and before_write is None and after_write is None:
        return dict(originals)
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'

    def write(conn, entry):
        key, payload = entry
        row = _read_source_row(conn, key, lock=postgres)
        source = _validated_source(row) if row is not None else None
        raw = row[len(COLUMNS) - 1] if row is not None else None
        expected = originals.get(key)
        if (source is None) != (expected is None):
            raise PaymentLinkConflict('Collegamento di pagamento cambiato: rileggi il documento.')
        if source is not None and source != expected:
            raise PaymentLinkConflict('Collegamento aggiornato da un altro processo: nessuna sovrascrittura.')
        if source is None:
            invoice = conn.execute('SELECT id_cliente FROM parcelle WHERE id=?'
                + (' FOR UPDATE' if postgres else ''), (payload['id_parcella'],)).fetchone()
            if invoice is None or invoice[0] != payload['id_cliente']:
                raise PaymentLinkConflict('Documento o cliente del collegamento non riscontrato nell’archivio SQL.')
        columns = COLUMNS
        values = tuple(row[index] if row is not None and payload.get(column) == expected.get(column)
                       else float(payload.get(column) or 0) if column == 'importo'
                       else payload.get(column) or '' for index, column in enumerate(columns[:-1]))
        values += (_encoded(payload),)
        if source is None:
            written = conn.execute('INSERT INTO payment_links (' + ','.join(columns) + ') VALUES ('
                                   + ','.join('?' for _ in columns) + ') ON CONFLICT(id) DO NOTHING RETURNING id',
                                   values).fetchone()
        else:
            if expected.get('stato') == 'PAGATO' and any(payload.get(field) != expected.get(field)
                    for field in ('stato', 'importo', 'valuta', 'id_parcella', 'id_cliente',
                                  'provider_usato', 'provider_tx_id', 'pagato_il')):
                raise PaymentLinkConflict('La conferma di pagamento esistente non può essere riscritta.')
            written = conn.execute('UPDATE payment_links SET ' + ','.join(column + '=?' for column in columns[1:])
                                   + ' WHERE id=? AND dati_json=? RETURNING id',
                                   (*values[1:], key, raw)).fetchone()
        if written is None:
            raise PaymentLinkConflict('Collegamento cambiato durante il salvataggio.')

    writable = getattr(database, '_conn_per_scrittura', None)
    conn = writable() if callable(writable) else database.conn
    target = database.raw_conn if postgres else conn
    # Una transazione del chiamante non appartiene a questo comando:
    # rifiutarla prima del blocco che esegue rollback sui soli effetti propri.
    if not postgres and conn.in_transaction:
        raise RuntimeError('Transazione estranea al collegamento: nessuna scrittura eseguita.')
    try:
        if not postgres:
            conn.execute('PRAGMA foreign_keys=ON')
            if conn.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
                raise RuntimeError('Vincoli del collegamento non attivi.')
            conn.execute('BEGIN IMMEDIATE')
        if before_write is not None:
            before_write(conn)
        for entry in changes.items():
            write(conn, entry)
        if after_write is not None:
            after_write(conn)
        target.commit()
    except Exception:
        target.rollback()
        raise
    return {**originals, **changes}


def confirmed_link(database, link_id, provider, transaction_id):
    """Un replay conserva data e identità della conferma già archiviata."""
    payload, _ = _source(database.conn, link_id)
    if payload is None:
        raise PaymentLinkConflict('Collegamento di pagamento non presente nel repository.')
    if payload['stato'] != 'PAGATO':
        return None
    if payload.get('provider_usato') != provider or (payload.get('provider_tx_id') or '') != transaction_id:
        raise PaymentLinkConflict('Il collegamento contiene già una transazione differente: verifica necessaria.')
    return payload
