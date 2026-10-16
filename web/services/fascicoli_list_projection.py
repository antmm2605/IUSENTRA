"""Adattamento delle chiavi native alla proiezione consultiva SQL."""
import json
from types import SimpleNamespace

from web.services.react_fascicoli_bridge import (
    _list_sort_key, _summary, _fascicolo_alias_index, _fascicolo_party_values, _fascicolo_rg_key, _text,
    _identity_key, _deadline_rg_candidates, _resolve_scadenza_fascicolo_ids,
)
from pct.fascicoli_list_query import SORTS
from pct.fascicolo_document_presidio import normalise_practice_duplicate_key


def native_sort_values(item):
    result = {}
    for name in SORTS:
        values = _list_sort_key(item, name)
        numbers = [value for value in values if type(value) in {int, float}]
        strings = [value for value in values if isinstance(value, str)]
        if len(numbers) > 3 or len(strings) > 3 or len(numbers) + len(strings) != len(values):
            raise ValueError('Chiave nativa non rappresentabile nel catalogo fascicoli.')
        if tuple(values) != tuple(numbers + strings):
            raise ValueError('Ordine dei componenti della chiave nativa non previsto.')
        result[name] = (*numbers, *([0] * (3 - len(numbers))), *strings, *([''] * (3 - len(strings))))
    for name, field, default in (
        ('gruppo', 'groupName', 'Senza gruppo'), ('stato', 'status', 'Stato non indicato'),
        ('tipo', 'type', 'Tipo non indicato'), ('ufficio', 'court', 'Ufficio non impostato'),
        ('anno', 'rgYear', 'Anno RG non indicato'), ('responsabile', 'responsible', 'Responsabile non indicato'),
    ):
        value = _text(item.get(field), default)
        result['group:' + name] = (0, 0, 0, value.casefold(), '', '')
    return result


def native_summary_values(item):
    return _summary([item])


def native_identity_values(fascicolo):
    aliases, _by_rg, _ids = _fascicolo_alias_index([fascicolo])
    native = {field: getattr(fascicolo, field, '') for field in (
        'id', 'numero', 'nome_cliente', 'titolo', 'numero_rg', 'anno_rg', 'tribunale',
    )}
    status = getattr(fascicolo, 'stato', '')
    return dict(key=str(fascicolo.id), client_key=str(getattr(fascicolo, 'id_cliente', '') or ''),
                duplicate_key=normalise_practice_duplicate_key(fascicolo), rg_key=_fascicolo_rg_key(fascicolo),
                parties=sorted(_fascicolo_party_values(fascicolo)), aliases=sorted(aliases), native=native,
                archived=str(getattr(status, 'value', status)) == 'ARCHIVIATO')


def native_deadline_scope(database, tenant, scadenza, *, connection=None):
    """Il resolver già esistente riceve solo i candidati selezionati dagli indici."""
    conn = connection if connection is not None else database.conn
    fid = str(getattr(scadenza, 'id_fascicolo', '') or '').strip()
    known = conn.execute('SELECT 1 FROM fascicoli_list_identity WHERE tenant_key=? AND record_key=? AND archived=0',
                        (tenant, fid)).fetchone() if fid else None
    aliases = conn.execute('SELECT a.record_key FROM fascicoli_list_aliases a JOIN fascicoli_list_identity i '
        'ON i.tenant_key=a.tenant_key AND i.record_key=a.record_key '
        'WHERE a.tenant_key=? AND a.alias_key=? AND i.archived=0', (tenant, _identity_key(fid))).fetchall() if fid else []
    by_rg = {}
    for rg in _deadline_rg_candidates(scadenza):
        rows = conn.execute('SELECT native_json,parties_json FROM fascicoli_list_identity '
            'WHERE tenant_key=? AND archived=0 AND rg_key=?', (tenant, rg)).fetchall()
        by_rg[rg] = [SimpleNamespace(**json.loads(row[0]), source_snapshot={'parti': json.loads(row[1])}) for row in rows]
    return _resolve_scadenza_fascicolo_ids(scadenza,
        alias_index={_identity_key(fid): {str(row[0]) for row in aliases}}, by_rg=by_rg, known_ids={fid} if known else set())
