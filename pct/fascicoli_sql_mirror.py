"""Mirror storico incrementale: SQL rimane la fonte primaria.

Ogni modifica accoda un riferimento nella stessa transazione proprietaria.
Il mirror legge soltanto quelle righe; un errore lascia la consegna pendente,
senza annullare un commit riuscito né rigenerare archivi da cache obsolete.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from pct.prima_nota_transition import prima_nota_source_lock


def _prefix(path):
    canonical = os.path.normcase(str(Path(path).resolve()))
    return 'fascicoli-mirror:' + hashlib.sha256(canonical.encode('utf-8')).hexdigest() + ':'


def enqueue(conn, path, key, revision):
    conn.execute('INSERT INTO _meta(chiave,valore) VALUES (?,?) '
                 'ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore',
                 (_prefix(path) + key, revision))


def delivery_revision():
    return uuid.uuid4().hex


def deliver(database, path):
    from pct import cache
    from pct.fascicoli_sql_writer import COLUMNS, COLLECTIONS

    prefix = _prefix(path)
    with prima_nota_source_lock(path):
        pending = database.fetchall_readonly(
            'SELECT chiave,valore FROM _meta WHERE chiave>=? AND chiave<? ORDER BY chiave',
            (prefix, prefix + '\uffff'))
        if not pending:
            return 0
        identifiers = {str(row[0])[len(prefix):] for row in pending}
        target = Path(path)
        if target.exists():
            # Nessun default vuoto su errori di parsing: conservare l'originale.
            payload = json.loads(target.read_text(encoding='utf-8'))
            if not isinstance(payload, dict):
                raise ValueError('Mirror storico non valido: consegna SQL conservata.')
        else:
            # Un mirror mancante non autorizza una scansione generale né una
            # copia parziale presentata come archivio completo.
            existing = database.fetchall_readonly('SELECT id FROM fascicoli LIMIT ?', (len(identifiers) + 1,))
            if any(row[0] not in identifiers for row in existing):
                raise ValueError('Mirror storico assente: richiede ricostruzione esplicita da SQL.')
            payload = {}
        for key in identifiers:
            rows = database.fetchall_readonly('SELECT * FROM fascicoli WHERE id=?', (key,))
            if not rows:
                payload.pop(key, None)
                continue
            row = dict(rows[0])
            value = json.loads(row['dati_json'] or '{}')
            if not isinstance(value, dict):
                raise ValueError('Metadati SQL non validi: mirror originale conservato.')
            for column in COLUMNS:
                if column not in COLLECTIONS and column != 'dati_json':
                    value[column] = row[column]
            for column, field in COLLECTIONS.items():
                value[field] = json.loads(row[column] or ('{}' if field == 'profilo_deposito' else '[]'))
            payload[key] = value
        cache.save(target, payload)

        def acknowledge(conn, row):
            conn.execute('DELETE FROM _meta WHERE chiave=? AND valore=?', (row[0], row[1]))

        # Una scrittura concorrente successiva ha un token diverso e rimane
        # pendente: non può essere confermata dal salvataggio precedente.
        database.salva_tabella('_meta', list(pending), acknowledge, delete_all=False)
        return len(pending)
