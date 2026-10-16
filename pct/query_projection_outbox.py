"""Trigger privati di invalidazione: stessa outbox, nessun secondo dispatcher.

Gli argomenti SQL sono definizioni del codice, mai filtri o nomi ricevuti
dall'utente. Le identità testuali devono essere passate come valori SQL o
lette da metadati proprietari già verificati.
"""
import re


def install_source_trigger(conn, *, table, action, name, tenant_sql, aggregate_sql,
                           key_sql, event_type, predicate='1=1', postgres=False):
    if action not in {'INSERT', 'UPDATE', 'DELETE'}:
        raise ValueError('Operazione della fonte non valida.')
    if any(not re.fullmatch(r'[a-z_][a-z0-9_]*', value) for value in (table, name)):
        raise ValueError('Definizione della fonte non valida.')
    if not re.fullmatch(r'[a-z_.]+', event_type):
        raise ValueError('Tipo di evento non valido.')
    row = 'OLD' if action == 'DELETE' else 'NEW'
    tenant_sql, aggregate_sql, key_sql = (value.replace('{row}', row) for value in (tenant_sql, aggregate_sql, key_sql))
    predicate = predicate.replace('{row}', row)
    identifier = "md5(random()::text || clock_timestamp()::text)" if postgres else 'lower(hex(randomblob(16)))'
    now = "to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US') || '+00:00'" if postgres else "strftime('%Y-%m-%dT%H:%M:%f+00:00','now')"
    insert = (
        'INSERT INTO transactional_outbox '
        '(id,tenant_id,aggregate_type,aggregate_id,aggregate_version,event_type,'
        'idempotency_key,actor_id,correlation_id,payload_json,available_at,created_at) '
        f"VALUES ({identifier},{tenant_sql},{aggregate_sql},{key_sql},1,'{event_type}',"
        f"{identifier},'sql-source-change','query-projection','{{}}',{now},{now});"
    )
    if postgres:
        schema = str(conn.execute('SELECT current_schema()').fetchone()[0])
        quoted = '"' + schema.replace('"', '""') + '"'
        function = quoted + '."' + name + '"'
        conn.execute(f'CREATE OR REPLACE FUNCTION {function}() RETURNS trigger '
                     f'LANGUAGE plpgsql SET search_path = {quoted}, pg_temp AS $$ '
                     f'BEGIN IF NOT ({predicate}) THEN RETURN NULL; END IF; {insert} RETURN NULL; END $$')
        conn.execute(f'DROP TRIGGER IF EXISTS {name} ON {table}')
        conn.execute(f'CREATE TRIGGER {name} AFTER {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {function}()')
    else:
        conn.execute(f'CREATE TRIGGER IF NOT EXISTS {name} AFTER {action} ON {table} '
                     f'WHEN {predicate} BEGIN {insert} END')
