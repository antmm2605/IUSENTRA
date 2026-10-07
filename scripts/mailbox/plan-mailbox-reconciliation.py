"""Piano di riconciliazione sola lettura: SQL e originali verificati.

Nessuna migrazione o importazione viene eseguita. Il piano completo rimane
nell'area backup dello studio; a video compaiono soltanto conteggi/impronte.
"""
import argparse
import hashlib
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':')).encode()).hexdigest()


def check_original(root, record):
    relative = Path(str(record.get('eml_file') or ''))
    expected = str(record.get('eml_sha256') or '').lower()
    if not str(record.get('eml_file') or '') or relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Originale della nuova acquisizione non collegato in modo sicuro.')
    target = (root / 'email' / relative).resolve()
    target.relative_to((root / 'email').resolve())
    if len(expected) != 64 or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        raise ValueError('Impronta della nuova acquisizione non corrispondente all’originale.')
    # Il parser IMAP nativo conserva il nome della cartella per i messaggi
    # acquisiti da inviate/cestino/bozze (email_client.py, acquisizione IMAP).
    if record.get('origine') not in {'IMAP', 'INVIATA', 'INVIATI', 'CESTINO', 'BOZZE'}:
        raise ValueError('Provenienza della nuova acquisizione da riesaminare.')


def plan(root, module, filename, tenant_key):
    db_path = root / 'studio.db'
    if not db_path.is_file():
        raise ValueError('Archivio SQL primario non presente.')
    with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as conn:
        primary = {str(key): json.loads(payload) for key, payload in conn.execute(
            'SELECT record_key,payload_json FROM moduli_json_records WHERE modulo=?',
            (module,),
        ).fetchall()}
    mirror_path = root / 'email' / filename
    mirror_bytes = mirror_path.read_bytes() if mirror_path.is_file() else b'{}'
    mirror = json.loads(mirror_bytes)
    if not isinstance(mirror, dict):
        raise ValueError('Catalogo storico della casella non valido.')
    for records in (primary, mirror):
        if any(not isinstance(row, dict) or str(row.get('id')) != key for key, row in records.items()):
            raise ValueError('Identità dei messaggi non coerente.')
    # Il SQL esistente è la base. Le assenze del mirror non sono eliminazioni.
    desired = json.loads(json.dumps(primary))
    acquisitions, acknowledged_reads = [], []
    for key in sorted(mirror.keys() - primary.keys()):
        check_original(root, mirror[key])
        desired[key] = mirror[key]
        acquisitions.append(key)
    for key in sorted(mirror.keys() & primary.keys()):
        before, after = primary[key], mirror[key]
        fields = {name for name in before.keys() | after.keys()
                  if (name in before) != (name in after) or before.get(name) != after.get(name)}
        if not fields:
            continue
        if fields != {'stato', 'letta_il'} or before.get('stato') != 'NON_LETTA' or after.get('stato') != 'LETTA':
            raise ValueError('Differenza tra cataloghi non governata: piano fermato.')
        if before.get('cartella') != 'INBOX' or before.get('letta_il'):
            raise ValueError('Lettura storica non coerente con la cartella primaria.')
        if not after.get('letta_il') or not datetime.fromisoformat(after['letta_il']).tzinfo:
            raise ValueError('Orario della lettura storica non verificabile.')
        # È una sola presa visione di un record già primario: identità e
        # intero contenuto coincidono col SQL (fields contiene solo i due
        # campi di lettura). Gli originali storici possono non essere stati
        # conservati dal vecchio importatore, senza impedire la presa visione.
        if after.get('eml_file'):
            check_original(root, after)
        desired[key] = after
        acknowledged_reads.append(key)
    sql_read_states, overridden_states, orphaned_states = {}, [], []
    read_db = root / 'intelligence' / 'registro_letture.db'
    if module == 'email_casella' and read_db.is_file():
        with sqlite3.connect(read_db.as_uri() + '?mode=ro', uri=True) as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='controllo_pec_letture'").fetchone()
            if exists:
                sql_read_states = {str(key): {'stato': state, 'letta_il': stamp}
                                   for key, state, stamp in conn.execute(
                                       'SELECT email_id,stato,letta_il FROM controllo_pec_letture WHERE tenant_id=?',
                                       (tenant_key,),
                                   ).fetchall()}
        # Questo stato SQL governa già Controllo Studio: conservarlo come
        # stato primario, senza reintrodurre uno stato storico dal mirror.
        for key, state in sql_read_states.items():
            if state['stato'] not in {'LETTA', 'NON_LETTA'}:
                raise ValueError('Stato della presa visione SQL non riconosciuto.')
            if state['stato'] == 'LETTA':
                if not state['letta_il'] or not datetime.fromisoformat(state['letta_il']).tzinfo:
                    raise ValueError('Orario della presa visione SQL non verificabile.')
            elif state['letta_il']:
                raise ValueError('Stato non letto SQL con orario incoerente.')
            if key not in desired:
                orphaned_states.append(key)
                continue
            if desired[key].get('cartella') != 'INBOX':
                continue
            if any(desired[key].get(field) != value for field, value in state.items()):
                desired[key].update(state)
                overridden_states.append(key)
    return {
        'source_of_truth': 'sqlite', 'primary_sha256': fingerprint(primary),
        'mirror_sha256': hashlib.sha256(mirror_bytes).hexdigest(),
        'target_sha256': fingerprint(desired), 'records': desired,
        'acquisitions': acquisitions, 'acknowledged_reads': acknowledged_reads,
        'retained_sql_only': len(primary.keys() - mirror.keys()),
        'sql_read_states_sha256': fingerprint(sql_read_states),
        'sql_read_states': sql_read_states, 'overridden_states': overridden_states,
        'orphaned_read_states': orphaned_states,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--data-root', type=Path)
    args = parser.parse_args()
    registry = (args.registry or Path(os.environ.get('PCT_TENANTS_REGISTRY', '/data/tenants.json'))).resolve()
    entries = json.loads(registry.read_text(encoding='utf-8'))
    if not isinstance(entries, dict):
        raise ValueError('Registro studi non valido.')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    modes = Counter()
    for data in entries.values():
        config = data.get('db_config', data.get('database', {}))
        mode = str(config.get('mode', 'SQLITE') if isinstance(config, dict) else config).upper()
        modes[mode] += 1
        if mode not in {'SQLITE', 'SQLITE3', 'SQLITE_LOCAL'}:
            continue
        storage = str(data.get('storage_key') or data.get('slug') or '')
        if not storage:
            raise ValueError('Studio privo di identità dati.')
        key = Path(storage)
        if not key.is_absolute() and (key.name != storage or storage in {'.', '..'}):
            raise ValueError('Percorso studio non valido.')
        root = key.resolve() if key.is_absolute() else (registry.parent / 'tenants' / key).resolve()
        logical_root = root
        if args.data_root is not None:
            relative = key.relative_to('/data/tenants') if key.is_absolute() else key
            logical_root = Path('/data/tenants') / relative
            root = (args.data_root.resolve() / 'tenants' / relative).resolve()
            root.relative_to((args.data_root.resolve() / 'tenants').resolve())
        for kind, module, filename in [('pec', 'email_casella', 'casella.json'),
                                       ('ordinary', 'email_ordinaria', 'ordinaria.json')]:
            result = plan(root, module, filename, str(data['slug']))
            result.update(tenant_key=str(data['slug']), mailbox_kind=kind, tenant_root=str(logical_root))
            destination = args.output_dir / f'{hashlib.sha256(str(logical_root).encode()).hexdigest()[:16]}-{kind}.json'
            destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            os.chmod(destination, 0o600)
            print(json.dumps({name: result[name] for name in ('source_of_truth', 'primary_sha256', 'mirror_sha256', 'target_sha256', 'retained_sql_only')} | {
                'read_only': True, 'mailbox_kind': kind, 'primary_count': len(result['records']) - len(result['acquisitions']),
                'target_count': len(result['records']), 'acquisitions': len(result['acquisitions']),
                'acknowledged_reads': len(result['acknowledged_reads']),
                'sql_read_states': len(result['sql_read_states']),
                'sql_state_overrides': len(result['overridden_states']),
                'orphaned_read_states': len(result['orphaned_read_states']),
            }))
    print(json.dumps({'configured_modes': dict(modes), 'read_only': True}))


if __name__ == '__main__':
    main()
