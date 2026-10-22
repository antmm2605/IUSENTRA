"""Scritture puntuali dei fascicoli sul repository proprietario.

Le regole di stato, documenti e deposito appartengono a GestioneFascicoli.
Questo writer conserva i campi storici e confronta la riga letta prima di
scrivere: nessuna sostituzione globale dell'archivio e nessun commit implicito
quando il chiamante fornisce una transazione condivisa.
"""
from __future__ import annotations

import json

from pct.json_snapshot_delta import merge_delta as _merge_delta

COLUMNS = ('id', 'numero', 'titolo', 'tipo', 'stato', 'id_cliente', 'nome_cliente',
           'tribunale', 'sezione', 'giudice', 'numero_rg', 'anno_rg', 'controparte',
           'avvocato_referente', 'avvocato_dominus', 'data_apertura', 'data_chiusura',
           'oggetto', 'note', 'creato_il', 'modificato_il', 'attivita_json',
           'documenti_json', 'scadenze_json', 'profilo_deposito_json', 'dati_json')
COLLECTIONS = {'attivita_json': 'attivita', 'documenti_json': 'documenti',
               'scadenze_json': 'depositi_pct', 'profilo_deposito_json': 'profilo_deposito'}


class FascicoloConcurrentUpdate(RuntimeError):
    """Lo snapshot non può cancellare il lavoro già confermato da altri."""


def encode_model(model):
    return json.dumps(model.to_dict(), sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def _values(model, before_row=None, before_model=None):
    after = model.to_dict()
    values = {}
    for column in COLUMNS:
        if column in COLLECTIONS or column == 'dati_json':
            continue
        field = column
        value = after.get(field, '')
        if column == 'id_cliente':
            value = value or None
        elif column == 'anno_rg':
            value = str(value) if value else ''
        if before_row is not None and before_model.get(field) == after.get(field):
            value = before_row[column]
        values[column] = value
    for column, field in COLLECTIONS.items():
        value = after.get(field, {} if field == 'profilo_deposito' else [])
        if before_row is not None:
            if before_model.get(field) == value:
                values[column] = before_row[column]
                continue
            source = json.loads(before_row[column] or ('{}' if field == 'profilo_deposito' else '[]'))
            value = _merge_delta(source, before_model.get(field), value)
        values[column] = json.dumps(value, ensure_ascii=False, allow_nan=False)
    slim = {key: value for key, value in after.items() if key not in {'attivita', 'documenti', 'depositi_pct'}}
    if before_row is not None and before_row['dati_json']:
        source = json.loads(before_row['dati_json'])
        if not isinstance(source, dict):
            raise ValueError('Metadati del fascicolo non validi: nessun dato ignorato.')
        previous = {key: value for key, value in before_model.items()
                    if key not in {'attivita', 'documenti', 'depositi_pct'}}
        slim = _merge_delta(source, previous, slim)
    values['dati_json'] = json.dumps(slim, ensure_ascii=False, allow_nan=False)
    return tuple(values[column] for column in COLUMNS)


def save_changes(database, *, original_rows, original_models, current, identifiers=None, connection=None, mirror_path=None):
    """Conferma solo le righe cambiate; uno scontro annulla l'intero comando."""
    encoded = {key: encode_model(value) for key, value in current.items()
               if identifiers is None or key in identifiers}
    candidates = set(identifiers) if identifiers is not None else original_models.keys() | encoded.keys()
    changed = sorted(key for key in candidates
                     if original_models.get(key) != encoded.get(key)
                     or (key in original_rows and not original_rows[key].get('dati_json')))
    if not changed:
        return {}
    for key in changed:
        if key in current and (current[key].id != key or getattr(current[key], 'documenti_non_caricati', False)):
            raise ValueError('Caricare il fascicolo completo prima di salvarne le modifiche.')
        if key in original_rows and key not in original_models:
            raise ValueError('Snapshot del fascicolo non disponibile: nessuna modifica registrata.')
    before_models = {key: json.loads(original_models[key]) if key in original_models else None for key in changed}
    from pct.offline_capture import capture_callback
    capture = capture_callback('fascicoli', lambda: {
        key: (before_models[key], json.loads(encoded[key]) if key in encoded else None) for key in changed
    })
    confirmed = {}
    from pct.fascicoli_sql_mirror import delivery_revision, enqueue
    mirror_revision = delivery_revision() if mirror_path is not None else None

    def write(conn, key):
        before, after = original_rows.get(key), current.get(key)
        if before is None and after is None:
            return
        if before is None:
            updated = conn.execute(
                f"INSERT INTO fascicoli ({','.join(COLUMNS)}) VALUES ({','.join('?' for _ in COLUMNS)}) "
                'ON CONFLICT(id) DO NOTHING RETURNING id', _values(after)).fetchone()
        else:
            condition = ' AND '.join(f'({name}=? OR ({name} IS NULL AND ? IS NULL))' for name in COLUMNS)
            expected = tuple(value for name in COLUMNS for value in (before[name], before[name]))
            if after is None:
                updated = conn.execute(f'DELETE FROM fascicoli WHERE {condition} RETURNING id', expected).fetchone()
            else:
                updated = conn.execute(
                    f"UPDATE fascicoli SET {','.join(name+'=?' for name in COLUMNS[1:])} "
                    f'WHERE {condition} RETURNING id',
                    _values(after, before, before_models[key])[1:] + expected).fetchone()
        if updated is None:
            raise FascicoloConcurrentUpdate(
                'Fascicolo aggiornato da un altro processo. La modifica non è stata registrata: '
                'ricarica i dati prima di riprovare.')
        if mirror_path is not None:
            enqueue(conn, mirror_path, key, mirror_revision)
        confirmed[key] = (dict(conn.execute('SELECT * FROM fascicoli WHERE id=?', (key,)).fetchone())
                          if after is not None else None)

    if connection is None:
        options = {'before_commit': capture} if capture is not None else {}
        database.salva_tabella('fascicoli', changed, write, delete_all=False, **options)
    else:
        for key in changed:
            write(connection, key)
        if capture is not None:
            capture(connection)
    return confirmed
