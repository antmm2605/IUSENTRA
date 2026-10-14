"""Catalogo SQL dei candidati cliente, mantenuto nella transazione del fascicolo.

Il modello storico legge id_cliente dal dati_json quando presente. Conserviamo
tutti i candidati radice (anche chiavi duplicate), poi il modello nativo decide
la corrispondenza: nessun campo anagrafico viene riscritto dalla preparazione.
La preparazione è esplicita; una richiesta consultiva non installa lo schema.
"""

INDEX_VERSION = 'fascicoli-clienti-v2'


def prepare_sqlite_client_index(path, backup_dir=None):
    """Comando esplicito di preparazione, condiviso da rilascio e provisioning."""
    from datetime import datetime, timezone
    from pathlib import Path
    import sqlite3

    path = Path(path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=30)
    try:
        marker = conn.execute('SELECT valore FROM _meta WHERE chiave=?',
                              ('fascicoli_clienti_index',)).fetchone()
        exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                              "AND name='fascicoli_clienti_lookup'").fetchone()
        if marker and marker[0] == INDEX_VERSION and exists:
            with conn:
                return install_client_index(conn)
        if not backup_dir:
            raise ValueError('Preparazione iniziale: indicare la cartella del backup coerente.')
        target = Path(backup_dir)
        target.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = sqlite3.connect(target / f'studio-prima-indice-clienti-{stamp}.db')
        try:
            conn.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup SQL non integro: preparazione interrotta.')
        finally:
            backup.close()
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            return install_client_index(conn)
    finally:
        conn.close()

SQLITE_SCALAR_OWNER = """(NEW.dati_json IS NULL OR NEW.dati_json = ''
    OR CASE WHEN json_valid(NEW.dati_json) THEN json_type(NEW.dati_json) ELSE 'invalid' END <> 'object')
    AND NEW.id_cliente IS NOT NULL"""

SQLITE_CANDIDATES = f"""
SELECT j.value AS id_cliente FROM json_each(
    CASE WHEN json_valid(NEW.dati_json) THEN NEW.dati_json ELSE '{{}}' END
) AS j WHERE j.key = 'id_cliente' AND j.type = 'text'
UNION SELECT NEW.id_cliente WHERE {SQLITE_SCALAR_OWNER}
"""


def install_client_index(conn, *, postgres=False):
    """DDL e popolamento da soli metadati SQL, nel comando di preparazione."""
    marker = conn.execute("SELECT valore FROM _meta WHERE chiave=?",
                          ('fascicoli_clienti_index',)).fetchone()
    exists = conn.execute("SELECT to_regclass('fascicoli_clienti_lookup')" if postgres else
                          "SELECT name FROM sqlite_master WHERE type='table' AND name='fascicoli_clienti_lookup'").fetchone()
    if marker and marker[0] == INDEX_VERSION and exists and exists[0]:
        return False
    conn.execute("CREATE TABLE IF NOT EXISTS fascicoli_clienti_lookup ("
                 "id_cliente TEXT NOT NULL, fascicolo_id TEXT NOT NULL, "
                 "PRIMARY KEY(id_cliente, fascicolo_id))")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fascicoli_clienti_lookup_fascicolo "
                 "ON fascicoli_clienti_lookup(fascicolo_id)")
    if postgres:
        _install_postgres(conn)
    else:
        _install_sqlite(conn)
    conn.execute("INSERT INTO _meta(chiave,valore) VALUES (?,?) "
                 "ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore",
                 ('fascicoli_clienti_index', INDEX_VERSION))
    return True


def _install_sqlite(conn):
    candidates = SQLITE_CANDIDATES.strip()
    scalar_owner = SQLITE_SCALAR_OWNER.replace('NEW.', 'f.')
    for action in ('insert', 'update', 'delete'):
        conn.execute(f'DROP TRIGGER IF EXISTS iusentra_fascicoli_clienti_{action}')
    conn.execute("CREATE TRIGGER iusentra_fascicoli_clienti_insert AFTER INSERT ON fascicoli BEGIN "
                 f"INSERT INTO fascicoli_clienti_lookup SELECT id_cliente, NEW.id FROM ({candidates}) "
                 "WHERE id_cliente IS NOT NULL ON CONFLICT DO NOTHING; END")
    conn.execute("CREATE TRIGGER iusentra_fascicoli_clienti_update AFTER UPDATE OF id,dati_json,id_cliente "
                 "ON fascicoli BEGIN "
                 "DELETE FROM fascicoli_clienti_lookup WHERE fascicolo_id=OLD.id AND "
                 f"(OLD.id <> NEW.id OR id_cliente NOT IN ({candidates})); "
                 f"INSERT INTO fascicoli_clienti_lookup SELECT id_cliente, NEW.id FROM ({candidates}) "
                 "WHERE id_cliente IS NOT NULL ON CONFLICT DO NOTHING; END")
    conn.execute("CREATE TRIGGER iusentra_fascicoli_clienti_delete AFTER DELETE ON fascicoli BEGIN "
                 "DELETE FROM fascicoli_clienti_lookup WHERE fascicolo_id=OLD.id; END")
    conn.execute("DELETE FROM fascicoli_clienti_lookup")
    # Correlated subqueries in FROM are not lateral in SQLite: expand the
    # two native candidate branches directly for the one-time population.
    conn.execute("INSERT INTO fascicoli_clienti_lookup "
                 "SELECT DISTINCT j.value, f.id FROM fascicoli f, json_each("
                 "CASE WHEN json_valid(f.dati_json) THEN f.dati_json ELSE '{}' END) j "
                 "WHERE j.key='id_cliente' AND j.type='text' "
                 "UNION SELECT f.id_cliente,f.id FROM fascicoli f "
                 f"WHERE {scalar_owner}")


def _install_postgres(conn):
    conn.execute("""
CREATE OR REPLACE FUNCTION iusentra_fascicoli_clienti_candidates(raw TEXT, scalar_owner TEXT)
RETURNS SETOF TEXT LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE body JSON;
BEGIN
    IF raw IS NULL OR raw = '' THEN
        IF scalar_owner IS NOT NULL THEN RETURN NEXT scalar_owner; END IF;
        RETURN;
    END IF;
    BEGIN
        body := raw::JSON;
    EXCEPTION WHEN invalid_text_representation THEN
        IF scalar_owner IS NOT NULL THEN RETURN NEXT scalar_owner; END IF;
        RETURN;
    END;
    IF json_typeof(body) <> 'object' THEN
        IF scalar_owner IS NOT NULL THEN RETURN NEXT scalar_owner; END IF;
        RETURN;
    END IF;
    RETURN QUERY SELECT DISTINCT value #>> '{}' FROM json_each(body)
        WHERE key='id_cliente' AND json_typeof(value)='string';
END $$
""")
    conn.execute("""
CREATE OR REPLACE FUNCTION iusentra_fascicoli_clienti_sync()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE desired TEXT[];
BEGIN
    IF TG_OP='DELETE' THEN
        DELETE FROM fascicoli_clienti_lookup WHERE fascicolo_id=OLD.id;
        RETURN OLD;
    END IF;
    desired := ARRAY(SELECT iusentra_fascicoli_clienti_candidates(NEW.dati_json,NEW.id_cliente));
    IF TG_OP='UPDATE' THEN
        DELETE FROM fascicoli_clienti_lookup WHERE fascicolo_id=OLD.id
            AND (OLD.id <> NEW.id OR NOT (id_cliente=ANY(desired)));
    END IF;
    INSERT INTO fascicoli_clienti_lookup(id_cliente,fascicolo_id)
        SELECT value,NEW.id FROM unnest(desired) value ON CONFLICT DO NOTHING;
    RETURN NEW;
END $$
""")
    conn.execute("DROP TRIGGER IF EXISTS iusentra_fascicoli_clienti_sync ON fascicoli")
    conn.execute("CREATE TRIGGER iusentra_fascicoli_clienti_sync AFTER INSERT OR UPDATE OR DELETE "
                 "ON fascicoli FOR EACH ROW EXECUTE FUNCTION iusentra_fascicoli_clienti_sync()")
    conn.execute("DELETE FROM fascicoli_clienti_lookup")
    conn.execute("INSERT INTO fascicoli_clienti_lookup(id_cliente,fascicolo_id) "
                 "SELECT DISTINCT c.value,f.id FROM fascicoli f CROSS JOIN LATERAL "
                 "iusentra_fascicoli_clienti_candidates(f.dati_json,f.id_cliente) c(value) "
                 "ON CONFLICT DO NOTHING")


def indexed_client_rows(backend, cliente_id):
    marker = backend.conn.execute("SELECT valore FROM _meta WHERE chiave=?",
                                  ('fascicoli_clienti_index',)).fetchone()
    if not marker or marker[0] != INDEX_VERSION:
        raise RuntimeError('Indice dei fascicoli cliente non preparato: eseguire la preparazione SQL governata.')
    return backend.fetchall_readonly(
        "SELECT f.* FROM fascicoli_clienti_lookup l JOIN fascicoli f ON f.id=l.fascicolo_id "
        "WHERE l.id_cliente=?", (cliente_id,))
