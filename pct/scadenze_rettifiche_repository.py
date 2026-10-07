"""Rettifica una proposta automatica in SQL senza sostituire lo scadenziario.

Il backend è già risolto sul tenant dal runtime. SQLite e PostgreSQL usano
la stessa scrittura condizionata; una modifica concorrente blocca la rettifica.
"""
from __future__ import annotations
import json
from typing import Any

class ScadenzeRettificheRepository:
    def __init__(self, backend: Any):
        if backend is None:
            raise RuntimeError('Database SQL dello studio non disponibile per la rettifica.')
        self.backend = backend

    def annulla_proposta(self, riga: Any, *, nota: str, traccia: list[dict[str, Any]], dati_attesi: str | None = None) -> None:
        conn = self.backend.conn
        current = conn.execute(
            'SELECT id,stato,titolo,data_scadenza,note,id_fascicolo,id_utente,dati_json FROM scadenze WHERE id=? AND id_fascicolo=?',
            (riga.id,riga.id_fascicolo),
        ).fetchone()
        if current is None:
            raise RuntimeError('La proposta non è più presente nello scadenziario dello studio.')
        current = dict(current)
        if dati_attesi is not None and current['dati_json'] != dati_attesi:
            raise RuntimeError('Il contenuto della proposta è cambiato dopo il piano: rettifica interrotta.')
        if (current['stato'] != 'APERTO' or current['note'] != riga.note
                or current['titolo'] != riga.titolo or current['data_scadenza'] != riga.data_scadenza
                or current['id_utente']):
            raise RuntimeError('La proposta è cambiata: rettifica interrotta, occorre una nuova verifica.')
        payload = json.loads(current['dati_json'] or '{}')
        if not isinstance(payload,dict) or not payload or payload.get('id') != riga.id:
            raise RuntimeError('Il record SQL della proposta non contiene un dato strutturato valido.')
        if payload.get('note','') != riga.note or payload.get('stato') != 'APERTO':
            raise RuntimeError('Colonne e contenuto SQL della proposta non coincidono: rettifica interrotta.')
        payload.update(stato='ANNULLATO',note=nota,trace_json=json.dumps(traccia,ensure_ascii=False))
        updated = conn.execute(
            'UPDATE scadenze SET stato=?,note=?,dati_json=? WHERE id=? AND id_fascicolo=? AND stato=? AND note=? AND dati_json=? RETURNING id',
            ('ANNULLATO',nota,json.dumps(payload,ensure_ascii=False),riga.id,riga.id_fascicolo,'APERTO',riga.note,current['dati_json']),
        ).fetchone()
        if updated is None:
            conn.execute('ROLLBACK')
            raise RuntimeError('La proposta è stata modificata durante la rettifica: nessun dato sovrascritto.')
        conn.execute('COMMIT')
