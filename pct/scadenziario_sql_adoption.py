"""Passaggio esplicito al repository nativo, con backup e produttori drenati."""
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pct.scadenziario import Scadenza, TipoTermine, StatoTermine, PrioritaTermine
from pct.scadenziario_sql_owner import backend_identity, owner_path, read_owner, resolve_owner
from pct.scadenziario_sql_writer import encode_model, write_changes


def read_source(source):
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
        if not isinstance(payload, dict) or set(payload) - Scadenza.__dataclass_fields__.keys():
            raise ValueError('Campi storici non riconosciuti: conservare e riconciliare la fonte.')
        payload = dict(payload)
        identity = payload.get('id') or key
        if not isinstance(identity, str) or not identity.strip() or (key is not None and key != identity) or identity in records:
            raise ValueError('Identità storica mancante, duplicata o discordante.')
        payload['id'] = identity
        for field, enum in (('tipo', TipoTermine), ('stato', StatoTermine), ('priorita', PrioritaTermine)):
            if field in payload:
                enum(payload[field])
        value = Scadenza.from_dict(payload)
        # Non convertire silenziosamente valori non rappresentabili dal modello.
        rendered = value.to_dict()
        if any(rendered[key] != entry for key, entry in payload.items()):
            raise ValueError('Scadenza storica alterata dalla normalizzazione: riconciliazione necessaria.')
        records[identity] = value
    digest = hashlib.sha256(content if content is not None else b'__absent_scadenziario__').hexdigest()
    return records, digest, content


def adopt(database, source, *, tenant, registry='', destination, data_root, writers_drained=False):
    from pct.prima_nota_transition import prima_nota_source_lock
    from pct.calendar_sql_records import deadline_from_row
    from scripts.query_index_backup import verified_backup

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
                resolve_owner(source, database)
            except RuntimeError:
                pass  # Fence preparato: solo la stessa fonte e lo stesso backup possono riprendere.
            else:
                if previous['tenant'] != tenant:
                    raise RuntimeError('Studio discordante dal proprietario.')
                return {'changed': False, 'tenant': tenant}
        records, digest, content = read_source(source)
        owner = {'version': 1, 'source': str(source), 'tenant': tenant, 'backend': backend_identity(database),
                 'studio_db': str(Path(database.db_path).resolve()), 'registry': str(registry), 'sha256': digest,
                 'backup': str(root)}
        if previous is not None and previous != owner:
            raise RuntimeError('Ripresa su fonte o archivio diverso: nessuna modifica.')
        root.mkdir(parents=True, exist_ok=True)
        original = root / 'scadenze-original.json'
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
        if read_source(source)[1:] != (digest, content):
            raise RuntimeError('Fonte cambiata durante il backup: migrazione sospesa.')
        if previous is None:
            with owner_path(source).open('x', encoding='utf-8') as output:
                json.dump(owner, output, sort_keys=True)
                output.flush()
                os.fsync(output.fileno())

        def write(conn, _):
            conn.execute('CREATE TABLE IF NOT EXISTS scadenziario_sql_state (tenant TEXT NOT NULL, source TEXT NOT NULL, '
                         'source_sha256 TEXT NOT NULL, backup_reference TEXT NOT NULL, backup_sha256 TEXT NOT NULL, '
                         'PRIMARY KEY(tenant,source))')
            if getattr(database, 'backend_kind', '') == 'postgresql':
                conn.execute('LOCK TABLE scadenziario_sql_state IN SHARE ROW EXCLUSIVE MODE')
            owners = conn.execute('SELECT tenant,source FROM scadenziario_sql_state').fetchall()
            if any((row[0], row[1]) != (tenant, str(source)) for row in owners):
                raise RuntimeError('Scadenziario SQL già appartenente a un altro studio o a una diversa fonte.')
            existing, models = {}, {}
            for row in conn.execute('SELECT * FROM scadenze').fetchall():
                payload = dict(row)
                value = deadline_from_row(payload)
                existing[value.id], models[value.id] = payload, encode_model(value)
            for key, value in records.items():
                if key in models and models[key] != encode_model(value):
                    raise RuntimeError('Scadenza SQL e JSON discordante: nessuna versione sovrascritta. ID=' + key)
            current = {key: deadline_from_row(row) for key, row in existing.items()}
            current.update(records)
            added = write_changes(conn, original_rows=existing, original_models=models, current=current)
            conn.execute('INSERT INTO scadenziario_sql_state VALUES (?,?,?,?,?)',
                         (tenant, str(source), digest, str(snapshot), snapshot_sha))
            details = json.dumps({'tenant': tenant, 'source_sha256': digest, 'source_records': len(records),
                                  'sql_records': len(current), 'added': added, 'backup_reference': str(snapshot),
                                  'backup_sha256': snapshot_sha}, sort_keys=True)
            conn.execute('INSERT INTO audit_log (id,timestamp,id_utente,azione,risorsa_tipo,risorsa_id,dettagli,esito) '
                         'VALUES (?,?,?,?,?,?,?,?)', (uuid4().hex, datetime.now(UTC).isoformat(), 'migrazione-scadenziario',
                         'scadenziario.adozione_sql', 'scadenze', tenant, details, 'OK'))
        database.salva_tabella('scadenze', [None], write, delete_all=False)
        resolve_owner(source, database)
        return {'changed': True, 'tenant': tenant, 'source_records': len(records), 'sha256': digest}
