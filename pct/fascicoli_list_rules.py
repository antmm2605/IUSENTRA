"""Versione delle regole con cui sono proiettate le righe dell'elenco dei fascicoli.

Quando cambia una regola della riga (per esempio la «prossima scadenza», unica dal 10/11/2026 per vista
operativa ed economica, o il riepilogo economico che considera i doppioni) le righe già salvate vanno
riproiettate: la preparazione governata accoda un aggiornamento puntuale per ogni fascicolo nella stessa
outbox degli altri eventi e registra la versione. Nessuna richiesta web lo fa.
"""
import uuid

from pct.transactional_outbox import OutboxEvent, enqueue

RULES_VERSION = 2


def install_rules_schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_rules ('
                 'tenant_key TEXT PRIMARY KEY,rules_version INTEGER NOT NULL)')


def rules_version(conn, tenant):
    install_rules_schema(conn)
    row = conn.execute('SELECT rules_version FROM fascicoli_list_rules WHERE tenant_key=?', (tenant,)).fetchone()
    return int(row[0]) if row else 1


def reproject_for_rules(conn, tenant):
    """Accoda la riproiezione di tutte le righe se le regole sono cambiate; restituisce quante."""
    from pct.fascicoli_list_query import AGGREGATE, EVENT_TYPE
    if rules_version(conn, tenant) >= RULES_VERSION:
        return 0
    keys = [str(row[0]) for row in conn.execute(
        'SELECT record_key FROM fascicoli_list_rows WHERE tenant_key=? ORDER BY record_key', (tenant,)).fetchall()]
    for key in keys:
        enqueue(conn, OutboxEvent(tenant_id=tenant, aggregate_type=AGGREGATE, aggregate_id='case:' + key,
            aggregate_version=1, event_type=EVENT_TYPE, idempotency_key='fascicoli-rules:' + uuid.uuid4().hex,
            payload={}, actor_id='fascicoli-list-rules'))
    conn.execute('INSERT INTO fascicoli_list_rules(tenant_key,rules_version) VALUES (?,?) '
                 'ON CONFLICT(tenant_key) DO UPDATE SET rules_version=excluded.rules_version', (tenant, RULES_VERSION))
    return len(keys)
