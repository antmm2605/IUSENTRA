"""Preparazione esplicita del repository documentale; nessuna lettura di documenti."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time

from .repository import DocumentAIRepository, DocumentAISchemaNotPrepared


def prepare_document_ai_schema(backend, fascicoli_db_path, *, backup_dir=None):
    """Riusa le migrazioni native e marca la revisione solo dopo il loro esito."""
    if backend is None:
        raise ValueError("La preparazione documentale richiede il backend SQL proprietario.")
    try:
        DocumentAIRepository.from_fascicoli_db(fascicoli_db_path, structured_db=backend, initialize_schema=False)
        return False
    except DocumentAISchemaNotPrepared:
        pass
    if str(getattr(backend, 'backend_kind', '')).lower() != 'postgresql':
        if not backup_dir:
            raise ValueError('Preparazione documentale SQLite: indicare il backup coerente.')
        target = Path(backup_dir)
        target.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        destination = target / f'studio-prima-schema-documentale-{stamp}.db'
        pending = destination.with_suffix('.pending.db')
        deadline = time.monotonic() + 1800
        def progress(status, remaining, total):
            if time.monotonic() >= deadline:
                raise TimeoutError('Backup SQL non concluso entro 30 minuti: preparazione interrotta.')
        with sqlite3.connect(pending) as backup:
            backend.conn.backup(backup, pages=256, progress=progress)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup SQL non integro: preparazione documentale interrotta.')
        pending.rename(destination)
    DocumentAIRepository.from_fascicoli_db(fascicoli_db_path, structured_db=backend)
    return True
