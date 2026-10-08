"""Build an offline SQLite repair candidate without overwriting any source.

Intact tables, rowids, schema objects and SQLite sequence values come from the
current snapshot. Only the damaged module table comes from a separately
verified SQL recovery candidate. Invalid JSON is preserved and reported, never
silently dropped. This tool deliberately cannot install the candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def build_candidate(source: Path, records: Path, output: Path, report: Path) -> dict:
    source, records, output, report = [p.resolve() for p in (source, records, output, report)]
    if not source.is_file() or not records.is_file():
        raise ValueError('Both SQL sources must exist.')
    if output.exists() or report.exists() or len({source, records, output, report}) != 4:
        raise ValueError('The candidate and report must be new, distinct files.')
    evidence = {'source_of_truth': 'sqlite', 'source_sha256': fingerprint(source),
                'records_sha256': fingerprint(records), 'intact_tables': [],
                'invalid_json': [], 'incomplete_modules': [], 'live_writes': 0}
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original, \
            sqlite3.connect(records.as_uri() + '?mode=ro', uri=True) as recovered, \
            sqlite3.connect(output) as target:
        schema = original.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY rowid"
        ).fetchall()
        shadows = {row[1] for row in original.execute('PRAGMA table_list') if row[2] == 'shadow'}
        virtual = {row[1] for row in schema if row[0] == 'table' and row[3].upper().startswith('CREATE VIRTUAL')}
        target.execute('PRAGMA foreign_keys=OFF')
        target.execute('BEGIN IMMEDIATE')
        for kind, name, _table, ddl in schema:
            if kind == 'table' and not name.startswith('sqlite_') and name not in shadows:
                target.execute(ddl)
        for kind, name, _table, _ddl in schema:
            if kind != 'table' or name.startswith('sqlite_') or name in virtual:
                continue
            if name in shadows:
                target.execute(f'DELETE FROM {quote(name)}')
            current = recovered if name == 'moduli_json_records' else original
            ddl = next(r[3] for r in schema if r[1] == name)
            prefix = '' if 'WITHOUT ROWID' in ddl.upper() else 'rowid,'
            rows = current.execute(f'SELECT {prefix}* FROM {quote(name)}').fetchall()
            if rows:
                columns = [r[1] for r in original.execute(f'PRAGMA table_info({quote(name)})')]
                names = prefix + ','.join(quote(column) for column in columns)
                placeholders = ','.join('?' for _ in rows[0])
                target.executemany(f'INSERT INTO {quote(name)} ({names}) VALUES ({placeholders})', rows)
            copied = target.execute(f'SELECT {prefix}* FROM {quote(name)}').fetchall()
            if sorted(rows, key=repr) != sorted(copied, key=repr):
                raise RuntimeError('Table copy mismatch: ' + name)
            if name != 'moduli_json_records':
                evidence['intact_tables'].append({'table': name, 'rows': len(rows), 'equal': True})
        for name in virtual:
            if original.execute(f'SELECT rowid,* FROM {quote(name)} ORDER BY rowid').fetchall() != target.execute(
                    f'SELECT rowid,* FROM {quote(name)} ORDER BY rowid').fetchall():
                raise RuntimeError('Virtual table copy mismatch: ' + name)
            evidence['intact_tables'].append({'table': name, 'equal': True})
        sequences = original.execute("SELECT name FROM sqlite_master WHERE name='sqlite_sequence'").fetchone()
        if sequences:
            target.execute('DELETE FROM sqlite_sequence')
            target.executemany('INSERT INTO sqlite_sequence VALUES (?,?)',
                               original.execute('SELECT * FROM sqlite_sequence').fetchall())
        for kind, name, _table, ddl in schema:
            if kind in {'index', 'trigger', 'view'}:
                target.execute(ddl)
        for pragma in ('user_version', 'application_id'):
            target.execute(f'PRAGMA {pragma}={original.execute("PRAGMA " + pragma).fetchone()[0]}')
        target.commit()
        if target.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise RuntimeError('The repaired candidate failed SQLite integrity validation.')
        original_fk = []
        for kind, name, _table, _ddl in schema:
            if kind == 'table' and name != 'moduli_json_records' and not name.startswith('sqlite_'):
                original_fk.extend(original.execute(f'PRAGMA foreign_key_check({quote(name)})').fetchall())
        target_fk = target.execute('PRAGMA foreign_key_check').fetchall()
        if sorted(original_fk) != sorted(target_fk):
            raise RuntimeError('Foreign-key violations changed during repair.')
        evidence['existing_fk_violations'] = original_fk
        for module, key, payload in target.execute('SELECT modulo,record_key,payload_json FROM moduli_json_records'):
            try:
                json.loads(payload)
            except (ValueError, TypeError):
                evidence['invalid_json'].append({'module': module, 'key': key, 'preserved': True})
        for module, metadata in target.execute('SELECT nome,payload_json FROM moduli_dati'):
            expected = json.loads(metadata).get('record_entries', 0)
            actual = target.execute('SELECT count(*) FROM moduli_json_records WHERE modulo=?', (module,)).fetchone()[0]
            if actual != expected:
                evidence['incomplete_modules'].append({'module': module, 'expected': expected, 'actual': actual})
        evidence['integrity_check'] = 'ok'
        evidence['module_records'] = target.execute('SELECT count(*) FROM moduli_json_records').fetchone()[0]
    evidence['output_sha256'] = fingerprint(output)
    report.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'records', 'output', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = build_candidate(args.source, args.records, args.output, args.report)
    print(json.dumps({key: len(value) if isinstance(value, list) else value
                      for key, value in result.items()}))
