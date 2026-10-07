"""Proiezione consultiva delle sole PEC collegate alla cartella cliente.

Il registro PEC SQL esistente resta la fonte: niente MIME, classificazione,
correlazione, aggiornamenti o invii durante questa lettura.
"""
from __future__ import annotations

import json
from typing import Any


def clean(value: Any) -> str:
    return ' '.join(str(value or '').split()).strip()

def pec_collegate_cartella(fascicolo_ids: list[str], *, repository: Any = None) -> list[dict[str, str]]:
    ids = list(dict.fromkeys(str(value).strip() for value in fascicolo_ids if str(value).strip()))
    if not ids:
        return []
    if repository is None:
        from web.services.pec_pipeline_runtime import repository_for_current_request
        repository = repository_for_current_request()
    grouped: dict[str, list[dict[str, str]]] = {value: [] for value in ids}
    with repository.connect() as conn:
        for offset in range(0, len(ids), 250):
            batch = ids[offset:offset + 250]
            placeholders = ','.join('?' for _ in batch)
            rows = conn.execute(
                'SELECT id, received_at, linked_fascicolo_id, metadata_json FROM pec_messages '
                f'WHERE tenant_id=? AND linked_fascicolo_id IN ({placeholders}) ORDER BY received_at DESC',
                (repository.tenant_id, *batch),
            ).fetchall()
            for row in rows:
                metadata = json.loads(row['metadata_json'] or '{}')
                headers = metadata.get('headers') or {}
                grouped[row['linked_fascicolo_id']].append({
                    'id': str(row['id']), 'fascicolo_id': str(row['linked_fascicolo_id']),
                    'received_at': clean(row['received_at']),
                    'subject': clean(headers.get('subject')), 'from': clean(headers.get('from')),
                })
    return [item for fid in ids for item in grouped[fid]]
