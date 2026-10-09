"""Backup PostgreSQL nativo: credenziali fuori dagli argomenti e controllo archivio."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path


def backup_postgres(dsn: str, destination: Path) -> dict[str, object]:
    # Il profilo database usa PostgreSQL16. Non scegliere il client più nuovo per caso:
    # un dump17 può risultare leggibile ma non ripristinabile sul server16.
    search_path = '/usr/lib/postgresql/16/bin' if os.name == 'posix' else os.environ.get('PATH')
    dump = shutil.which('pg_dump', path=search_path)
    restore = shutil.which('pg_restore', path=search_path)
    if not dump or not restore:
        raise RuntimeError('Strumenti PostgreSQL nativi non disponibili: nessun backup confermato.')
    from psycopg2.extensions import parse_dsn
    # Libpq governa il parsing. Non ricostruire né stampare URI contenenti segreti.
    try:
        parameters = parse_dsn(dsn)
    except Exception:
        raise ValueError('Profilo PostgreSQL non valido: nessun backup avviato.') from None
    mapping = {
        'host': 'PGHOST', 'hostaddr': 'PGHOSTADDR', 'port': 'PGPORT', 'dbname': 'PGDATABASE',
        'user': 'PGUSER', 'password': 'PGPASSWORD', 'passfile': 'PGPASSFILE',
        'sslmode': 'PGSSLMODE', 'sslcert': 'PGSSLCERT', 'sslkey': 'PGSSLKEY',
        'sslrootcert': 'PGSSLROOTCERT', 'sslcrl': 'PGSSLCRL', 'sslcrldir': 'PGSSLCRLDIR',
        'connect_timeout': 'PGCONNECT_TIMEOUT', 'options': 'PGOPTIONS',
        'application_name': 'PGAPPNAME', 'target_session_attrs': 'PGTARGETSESSIONATTRS',
    }
    if set(parameters) - mapping.keys() or not parameters.get('dbname'):
        raise ValueError('Profilo PostgreSQL non supportato per il backup nativo.')
    environment = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
    environment.update({mapping[key]: value for key, value in parameters.items()})
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Non sovrascrivere un backup precedente; gli errori preservano il parziale per diagnosi.
    with destination.open('xb') as output:
        os.chmod(destination, 0o600)
        result = subprocess.run([dump, '--format=custom', '--no-password'],
                                env=environment, stdout=output, stderr=subprocess.PIPE, check=False)
        output.flush()
        os.fsync(output.fileno())
    if result.returncode or not destination.stat().st_size:
        raise RuntimeError('Backup PostgreSQL fallito: archivio non confermato, parziale preservato.')
    # Nessuna connessione al DB o ripristino durante il controllo dell'indice dell'archivio.
    verified = subprocess.run([restore, '--list', str(destination)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
    if verified.returncode:
        raise RuntimeError('Archivio PostgreSQL non leggibile: nessun backup confermato.')
    digest = hashlib.sha256()
    with destination.open('rb') as content:
        for chunk in iter(lambda: content.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'destination': destination.name, 'backup_bytes': destination.stat().st_size,
            'sha256': digest.hexdigest(), 'format': 'postgresql-custom', 'archive_index_verified': True,
            'restore_verified': False}
