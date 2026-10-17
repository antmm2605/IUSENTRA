"""Sessioni private sull'archivio PEC proprietario, senza avviare la pipeline."""
import sqlite3
from contextlib import contextmanager

from flask import has_request_context


@contextmanager
def pec_audit_query_connection(*, tenant, writable=False):
    from web.services.notification_presidia_runtime import _presidio_db_path, _tenant_id

    if not has_request_context() or _tenant_id() != tenant:
        raise PermissionError('Contesto studio discordante per la consultazione PEC.')
    path = _presidio_db_path()
    if not path.is_file():
        raise RuntimeError('Archivio delle analisi PEC non disponibile: nessuna inizializzazione eseguita.')
    # mode=rw non crea un file assente; le scritture sono riservate ai worker
    # della proiezione e non cambiano messaggi, analisi o collegamenti.
    conn = sqlite3.connect(path.resolve().as_uri() + ('?mode=rw' if writable else '?mode=ro'), uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    if not writable:
        conn.execute('PRAGMA query_only=ON')
    try:
        yield conn
    finally:
        conn.close()
