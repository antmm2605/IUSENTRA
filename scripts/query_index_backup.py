"""Backup SQL coerente e verificato, condiviso dalle migrazioni consultive."""
import hashlib
import json
import os
import shutil
from pathlib import Path

from deploy.hetzner.backup_structured import _backup_sqlite, _sha256
from scripts.postgres_backup import backup_postgres


def verified_backup(database, destination):
    destination = Path(destination).resolve()
    manifest_path = destination / 'manifest.json'
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    filename = 'studio.dump' if postgres else 'studio.db'
    if postgres:
        from psycopg2.extensions import parse_dsn

        parameters = parse_dsn(database.dsn)
        identity = {key: parameters.get(key, '') for key in ('host', 'hostaddr', 'port', 'dbname', 'user', 'options')}
        source = 'postgresql:' + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    else:
        source = str(Path(database.db_path).resolve())
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['source'] != source or manifest['postgres'] != postgres:
            raise RuntimeError('Backup riferito a un archivio diverso: nessuna migrazione eseguita.')
        snapshot = destination / filename
        if snapshot.stat().st_size != manifest['backup']['backup_bytes'] or _sha256(snapshot) != manifest['backup']['sha256']:
            raise RuntimeError('Backup non riscontrato: nessuna migrazione eseguita.')
        return snapshot, manifest['backup']['sha256']
    destination.mkdir(parents=True, exist_ok=False)
    snapshot = destination / filename
    if postgres:
        source_bytes = int(database.conn.execute('SELECT pg_database_size(current_database())').fetchone()[0])
    else:
        page_count = int(database.conn.execute('PRAGMA page_count').fetchone()[0])
        page_size = int(database.conn.execute('PRAGMA page_size').fetchone()[0])
        source_bytes = max(Path(database.db_path).stat().st_size, page_count * page_size)
    required = 1024 ** 3 + source_bytes
    if shutil.disk_usage(destination).free < required:
        raise RuntimeError('Spazio insufficiente per il backup SQL coerente.')
    result = backup_postgres(database.dsn, snapshot) if postgres else _backup_sqlite(Path(database.db_path), snapshot)
    manifest = {'source': source, 'postgres': postgres, 'backup': result}
    with manifest_path.open('x', encoding='utf-8') as output:
        json.dump(manifest, output, ensure_ascii=False, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    return snapshot, result['sha256']
