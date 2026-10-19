"""Adozione condivisa del calendario nativo, con backup e produttori drenati.

Scadenziario resta il dominio predefinito per compatibilità dei rilasci già
adottati; Agenda usa i propri modelli, scrittori e conferme persistenti.
"""
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pct.scadenziario import Scadenza, TipoTermine, StatoTermine, PrioritaTermine
from pct.scadenziario_sql_owner import backend_identity, owner_path, read_owner, resolve_owner
from pct.scadenziario_sql_writer import encode_model, write_changes


def _domain(domain):
    if domain == 'scadenziario':
        from pct.calendar_sql_records import deadline_from_row
        return Scadenza, deadline_from_row, encode_model, write_changes, 'scadenze'
    if domain == 'agenda':
        from pct.agenda import Appuntamento
        from pct.agenda_sql_writer import encode_model as encode, write_changes as write
        from pct.calendar_sql_records import appointment_from_row
        return Appuntamento, appointment_from_row, encode, write, 'appuntamenti'
    raise ValueError('Dominio calendario non riconosciuto.')


def read_source(source, *, domain='scadenziario'):
    model, _, _, _, _ = _domain(domain)
    content = Path(source).read_bytes() if Path(source).exists() else None
    raw = json.loads(content) if content is not None else {}
    if isinstance(raw, dict):
        entries = list(raw.items())
    elif isinstance(raw, list):
        entries = [(None, item) for item in raw]
    else:
        raise ValueError('Scadenziario storico non valido: nessuna riga scartata.')
    records = {}
    for key, payload in entries:
        if not isinstance(payload, dict) or set(payload) - model.__dataclass_fields__.keys():
            raise ValueError('Campi storici non riconosciuti: conservare e riconciliare la fonte.')
        payload = dict(payload)
        identity = payload.get('id') or key
        if not isinstance(identity, str) or not identity.strip() or (key is not None and key != identity) or identity in records:
            raise ValueError('Identità storica mancante, duplicata o discordante.')
        payload['id'] = identity
        if domain == 'scadenziario':
            for field, enum in (('tipo', TipoTermine), ('stato', StatoTermine), ('priorita', PrioritaTermine)):
                if field in payload:
                    enum(payload[field])
        value = model.from_dict(payload)
        # Non convertire silenziosamente valori non rappresentabili dal modello.
        rendered = value.to_dict()
        if any(rendered[key] != entry for key, entry in payload.items()):
            raise ValueError('Scadenza storica alterata dalla normalizzazione: riconciliazione necessaria.')
        records[identity] = value
    digest = hashlib.sha256(content if content is not None else ('__absent_' + domain + '__').encode()).hexdigest()
    return records, digest, content


def adopt(database, source, *, tenant, registry='', destination, data_root, writers_drained=False,
          domain='scadenziario'):
    from pct.prima_nota_transition import prima_nota_source_lock
    from scripts.query_index_backup import verified_backup

    _, from_row, encode, writer, table = _domain(domain)
    state_table = domain + '_sql_state'

    if writers_drained is not True or not tenant:
        raise ValueError('Studio e arresto dei produttori obbligatori.')
    source = Path(source).resolve()
    root = Path(destination).resolve()
    volume = Path(data_root).resolve()
    if root == volume or not root.is_relative_to(volume) or not source.is_relative_to(volume):
        raise ValueError('Il backup deve restare nel volume dati dello studio.')
    source.parent.mkdir(parents=True, exist_ok=True)
    with prima_nota_source_lock(source):
        previous = read_owner(source)
        if previous:
            try:
                resolve_owner(source, database, domain=domain)
            except RuntimeError:
                pass  # Fence preparato: solo la stessa fonte e lo stesso backup possono riprendere.
            else:
                if previous['tenant'] != tenant:
                    raise RuntimeError('Studio discordante dal proprietario.')
                return {'changed': False, 'tenant': tenant}
        records, digest, content = read_source(source, domain=domain)
        owner = {'version': 1, 'source': str(source), 'tenant': tenant, 'backend': backend_identity(database),
                 'studio_db': str(Path(database.db_path).resolve()), 'registry': str(registry), 'sha256': digest,
                 'backup': str(root)}
        if previous is not None and previous != owner:
            raise RuntimeError('Ripresa su fonte o archivio diverso: nessuna modifica.')
        root.mkdir(parents=True, exist_ok=True)
        original = root / (table + '-original.json')
        if content is not None:
            if not original.exists():
                with original.open('xb') as output:
                    output.write(content)
                    output.flush()
                    os.fsync(output.fileno())
            if original.read_bytes() != content:
                raise RuntimeError('Backup storico discordante: migrazione sospesa.')
        elif original.exists():
            raise RuntimeError('Backup storico non coerente con la fonte assente.')
        snapshot, snapshot_sha = verified_backup(database, root / 'sql')
        if read_source(source, domain=domain)[1:] != (digest, content):
            raise RuntimeError('Fonte cambiata durante il backup: migrazione sospesa.')
        if previous is None:
            with owner_path(source).open('x', encoding='utf-8') as output:
                json.dump(owner, output, sort_keys=True)
                output.flush()
                os.fsync(output.fileno())

        def write(conn, _):
            conn.execute(f'CREATE TABLE IF NOT EXISTS {state_table} (tenant TEXT NOT NULL, source TEXT NOT NULL, '
                         'source_sha256 TEXT NOT NULL, backup_reference TEXT NOT NULL, backup_sha256 TEXT NOT NULL, '
                         'PRIMARY KEY(tenant,source))')
            if getattr(database, 'backend_kind', '') == 'postgresql':
                conn.execute('LOCK TABLE audit_log IN SHARE ROW EXCLUSIVE MODE')
                conn.execute(f'LOCK TABLE {state_table} IN SHARE ROW EXCLUSIVE MODE')
            other = 'agenda_sql_state' if domain == 'scadenziario' else 'scadenziario_sql_state'
            exists = conn.execute(f"SELECT to_regclass('{other}')" if
                getattr(database, 'backend_kind', '') == 'postgresql' else
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{other}'").fetchone()
            if exists and exists[0] and conn.execute(f'SELECT tenant FROM {other} WHERE tenant<>?', (tenant,)).fetchone():
                raise RuntimeError('Calendario SQL appartenente a un altro studio.')
            owners = conn.execute(f'SELECT tenant,source FROM {state_table}').fetchall()
            if any((row[0], row[1]) != (tenant, str(source)) for row in owners):
                raise RuntimeError('Scadenziario SQL già appartenente a un altro studio o a una diversa fonte.')
            existing, models = {}, {}
            for row in conn.execute(f'SELECT * FROM {table}').fetchall():
                payload = dict(row)
                value = from_row(payload)
                existing[value.id], models[value.id] = payload, encode(value)
            differences = []
            for key, value in records.items():
                if key in models and models[key] != encode(value):
                    if domain != 'agenda':
                        raise RuntimeError('Scadenza SQL e JSON discordante: nessuna versione sovrascritta. ID=' + key)
                    old, confirmed = value.to_dict(), from_row(existing[key]).to_dict()
                    differences.append({'id': key, 'fields': sorted(k for k in old if old[k] != confirmed[k]),
                                        'historical_sha256': hashlib.sha256(encode(value).encode()).hexdigest(),
                                        'sql_sha256': hashlib.sha256(models[key].encode()).hexdigest()})
            current = dict(records)
            # Agenda conserva la precedenza SQL già prevista dal loader; il backup
            # e l'audit conservano le differenze, senza attestare eventi non provati.
            current.update({key: from_row(row) for key, row in existing.items()})
            added = writer(conn, original_rows=existing, original_models=models, current=current)
            conn.execute(f'INSERT INTO {state_table} VALUES (?,?,?,?,?)',
                         (tenant, str(source), digest, str(snapshot), snapshot_sha))
            details = json.dumps({'tenant': tenant, 'source_sha256': digest, 'source_records': len(records),
                                  'sql_records': len(current), 'added': added, 'backup_reference': str(snapshot),
                                  'backup_sha256': snapshot_sha, 'historical_differences': differences}, sort_keys=True)
            conn.execute('INSERT INTO audit_log (id,timestamp,id_utente,azione,risorsa_tipo,risorsa_id,dettagli,esito) '
                         'VALUES (?,?,?,?,?,?,?,?)', (uuid4().hex, datetime.now(UTC).isoformat(), 'migrazione-' + domain,
                         domain + '.adozione_sql', table, tenant, details, 'OK'))
        database.salva_tabella(table, [None], write, delete_all=False)
        resolve_owner(source, database, domain=domain)
        return {'changed': True, 'tenant': tenant, 'source_records': len(records), 'sha256': digest}
