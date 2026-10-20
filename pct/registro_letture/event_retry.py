"""Politica persistente della coda esistente, senza un secondo scheduler."""
from datetime import datetime, timedelta

MAX_ATTEMPTS = 3
FIELDS = {
    'attempts': 'INTEGER NOT NULL DEFAULT 0',
    'available_at': "TEXT NOT NULL DEFAULT ''",
    'last_error': "TEXT NOT NULL DEFAULT ''",
    'last_error_code': "TEXT NOT NULL DEFAULT ''",
}
INDEX_SQL = ('CREATE INDEX IF NOT EXISTS idx_letture_eventi_retry '
             'ON letture_eventi(tenant_id,stato,available_at,lease_until)')
HISTORY_SQL = """CREATE TABLE IF NOT EXISTS letture_eventi_esiti (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, fascicolo_id TEXT NOT NULL,
    generation BIGINT NOT NULL, attempt INTEGER NOT NULL, worker_id TEXT NOT NULL,
    stato TEXT NOT NULL, error_code TEXT NOT NULL DEFAULT '', errore TEXT NOT NULL DEFAULT '',
    iniziato_il TEXT NOT NULL, concluso_il TEXT NOT NULL DEFAULT '',
    UNIQUE(tenant_id,fascicolo_id,generation,attempt))"""
HISTORY_INDEX_SQL = ('CREATE INDEX IF NOT EXISTS idx_letture_eventi_esiti_worker '
                     'ON letture_eventi_esiti(tenant_id,fascicolo_id,worker_id,generation)')


class ReadingEventSchemaNotPrepared(RuntimeError):
    pass


def columns(conn, *, postgres=False):
    if postgres:
        return {row[0] for row in conn.execute('SELECT column_name FROM information_schema.columns '
                "WHERE table_schema=current_schema() AND table_name='letture_eventi'").fetchall()}
    return {row[1] for row in conn.execute('PRAGMA table_info(letture_eventi)').fetchall()}


def require_prepared(conn, *, postgres=False):
    history = conn.execute("SELECT to_regclass('letture_eventi_esiti')" if postgres else
                           "SELECT name FROM sqlite_master WHERE type='table' AND name='letture_eventi_esiti'").fetchone()
    if not set(FIELDS).issubset(columns(conn, postgres=postgres)) or not history or not history[0]:
        raise ReadingEventSchemaNotPrepared('Coda letture non preparata: eseguire la preparazione SQL governata.')


def install(conn, *, postgres=False):
    """Solo preparazione esplicita dopo backup; commit del chiamante."""
    present = columns(conn, postgres=postgres)
    if not present:
        raise ReadingEventSchemaNotPrepared('Registro letture non provisionato.')
    history = conn.execute("SELECT to_regclass('letture_eventi_esiti')" if postgres else
        "SELECT name FROM sqlite_master WHERE type='table' AND name='letture_eventi_esiti'").fetchone()
    changed = not history or not history[0]
    for field, definition in FIELDS.items():
        if field not in present:
            conn.execute(f'ALTER TABLE letture_eventi ADD COLUMN {field} {definition}')
            changed = True
    conn.execute(HISTORY_SQL)
    conn.execute(HISTORY_INDEX_SQL)
    conn.execute(INDEX_SQL)
    return changed


def deadline(now, seconds):
    value = datetime.fromisoformat(now.replace('Z', '+00:00')) + timedelta(seconds=seconds)
    return value.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def retry_deadline(now, attempts):
    return deadline(now, 30 * 2 ** max(0, min(int(attempts) - 1, 3)))


def recover_prepared_schema_failures(conn, tenant, now):
    """Chiamare solo dopo il riscontro dello schema documentale proprietario.

    Risveglia soltanto errori pertinenti; conserva tutti gli esiti precedenti.
    Il reset del codice rende la ripetizione idempotente.
    """
    return conn.execute(
        "UPDATE letture_eventi SET generation=generation+1, attempts=0, available_at='', "
        "last_error='',last_error_code='',aggiornato_il=?, "
        "stato=CASE WHEN stato='running' THEN 'running' ELSE 'pending' END "
        "WHERE tenant_id=? AND last_error_code='DocumentAISchemaNotPrepared' "
        "RETURNING fascicolo_id", (now,tenant)).fetchall()
