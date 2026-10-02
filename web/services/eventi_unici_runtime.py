"""Collegamenti delle azioni alle proiezioni SQL riunite e verificate."""
from __future__ import annotations
import json
from urllib.parse import quote
from pct.eventi_unici_repository import EventiUniciRepository


def collegamento_scadenza(database, tenant_id, fascicolo_id, azione):
    """La stessa prova canonica, non il solo giorno, individua la scadenza."""
    if database is None or not tenant_id or not fascicolo_id or not azione.get('fattoId'):
        return ''
    repo=EventiUniciRepository(database,tenant_id)
    if not repo.presente():
        return ''
    rows=database.conn.execute('SELECT origine_id,evidenza_json FROM eventi_unici_correlazioni WHERE tenant_id=? AND fascicolo_id=? AND area=?',
                               (tenant_id,fascicolo_id,'scadenze')).fetchall()
    verified=set()
    for row in rows:
        evidence=json.loads(row['evidenza_json'])
        if azione['fattoId'] not in {evidence.get('canonico_fatto_id'),evidence.get('fatto_id')}:
            continue
        _,payload=repo.risolvi_verificato('scadenze',row['origine_id'],fascicolo_id=fascicolo_id)
        verified.add(payload['id'])
    if len(verified)>1:
        raise ValueError('La stessa prova risulta collegata a più scadenze: verifica necessaria.')
    return '/scadenziario?focus='+quote(next(iter(verified)),safe='') if verified else ''
