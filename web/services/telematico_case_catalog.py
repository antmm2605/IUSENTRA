"""Consultazione paginata SQL delle pratiche telematiche, senza procedure operative."""
from __future__ import annotations
import unicodedata
from datetime import datetime, timezone
from typing import Any
from web.services.react_telematico_bridge import _case_row
from web.services.telematico_control_tower import BLOCKED_STATUSES, PENDING_STATUSES, WARNING_STATUSES

PORTAL_SQL = """CASE
 WHEN lower(service_code) LIKE '%pst%' OR lower(service_code) LIKE '%polis%' THEN 'pst'
 WHEN lower(service_code) LIKE '%pdp%' OR lower(service_code) LIKE '%penale%' THEN 'pdp'
 WHEN lower(service_code) LIKE '%pat%' OR lower(service_code) LIKE '%siga%' OR lower(service_code) LIKE '%amministr%' THEN 'pat'
 WHEN lower(service_code) LIKE '%ptt%' OR lower(service_code) LIKE '%sigit%' OR lower(service_code) LIKE '%tribut%' THEN 'ptt'
 ELSE 'altro' END"""


def _normalise(value: Any) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', str(value or '').casefold()) if not unicodedata.combining(c))


def _search_sql(expression: str) -> str:
    for letters, base in [('àÀ','a'),('èÈéÉ','e'),('ìÌ','i'),('òÒ','o'),('ùÙ','u')]:
        for letter in letters:
            expression = f"replace({expression}, '{letter}', '{base}')"
    return f'lower({expression})'


def build_telematico_case_catalog(*, repository: Any, fascicoli: list[Any], portal: str = '', query: str = '', page: int = 1, page_size: int = 25, presidi: bool = False) -> dict[str, Any]:
    if portal not in ('', 'pst-pdp', 'pst', 'pdp', 'pat', 'ptt', 'altro'):
        raise ValueError('Seleziona un canale telematico valido.')
    if repository is None:
        raise RuntimeError('Archivio telematico non disponibile.')
    page = max(1, int(page)); page_size = max(1, min(100, int(page_size)))
    index = {str(getattr(f, 'id', '')): f for f in fascicoli if getattr(f, 'id', '')}
    ids = sorted(index)
    if not ids:
        return {'items': [], 'total': 0, 'page': 1, 'pageSize': page_size, 'pages': 1, 'sourceOfTruth': 'sql'}
    source = 'v_telematic_case_overview'
    params: list[Any] = []
    if presidi:
        groups = [('Blocco', BLOCKED_STATUSES), ('Esito in attesa', PENDING_STATUSES), ('Import incompleto', {'draft', 'opened_official_portal', 'manual_review_required'}), ('Avviso', WARNING_STATUSES)]
        parts = []
        for category, statuses in groups:
            parts.append("SELECT *, ? AS control_category FROM v_telematic_case_overview WHERE internal_status IN (" + ','.join('?' for _ in statuses) + ')')
            params.extend([category, *sorted(statuses)])
        source = '(' + ' UNION ALL '.join(parts) + ') AS catalog'
    conditions = ['practice_id IN (' + ','.join('?' for _ in ids) + ')']
    params.extend(ids)
    if portal:
        portals = ['pst', 'pdp'] if portal == 'pst-pdp' else [portal]
        conditions.append(f'({PORTAL_SQL}) IN (' + ','.join('?' for _ in portals) + ')')
        params.extend(portals)
    needle = _normalise(query.strip()[:160])
    if needle:
        fields = ('office_name', 'subject_name', 'register_number', 'register_year', 'internal_status', 'native_status', 'service_code') + (('control_category',) if presidi else ())
        joined = " || ' ' || ".join(f"COALESCE(CAST({field} AS TEXT), '')" for field in fields)
        # Stesse diciture italiane già visibili nella superficie React.
        joined += " || ' ' || CASE internal_status WHEN 'import_completed' THEN 'Import completato' WHEN 'manual_review_required' THEN 'Verifica manuale richiesta' ELSE replace(COALESCE(internal_status,''),'_',' ') END"
        matched = []
        for fid in ids:
            display = _case_row({'practice_id': fid}, 0, index)
            if needle in _normalise(' '.join(str(display.get(key) or '') for key in ('title', 'subtitle', 'subject'))):
                matched.append(fid)
        escaped = needle.replace('~','~~').replace('%','~%').replace('_','~_')
        condition = f"{_search_sql(joined)} LIKE ? ESCAPE '~'"
        params.append('%' + escaped + '%')
        if matched:
            condition += ' OR practice_id IN (' + ','.join('?' for _ in matched) + ')'
            params.extend(matched)
        conditions.append('(' + condition + ')')
    where = ' WHERE ' + ' AND '.join(conditions)
    count = repository._fetchone('SELECT count(*) AS total FROM ' + source + where, params)
    total = int(count['total'])
    pages = max(1, (total + page_size - 1) // page_size); page = min(page, pages)
    rows = repository._fetchall('SELECT *, register_number AS registry_number, open_tasks_count AS open_tasks FROM ' + source + where + ' ORDER BY COALESCE(last_sync_at,updated_at,created_at) DESC,id' + (',control_category' if presidi else '') + ' LIMIT ? OFFSET ?', [*params, page_size, (page - 1) * page_size])
    items = []
    for offset, raw in enumerate(rows):
        row = dict(raw)
        number = str(row.get('register_number') or '').strip()
        year = str(row.get('register_year') or '').strip()
        if number:
            registry = number if '/' in number or not year else f'{number}/{year}'
            row['registry_number'] = registry if registry.upper().startswith('RG ') else f'RG {registry}'
        item = _case_row(row, offset, index)
        # updated_at del repository usa datetime('now'), quindi UTC anche senza suffisso.
        if row.get('updated_at'):
            try:
                stamp = datetime.fromisoformat(str(row['updated_at']).replace('Z', '+00:00'))
                item['syncedAt'] = (stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)).isoformat()
            except ValueError:
                pass  # La UI conserva il valore non valido e mostra lo stato data da verificare.
        if presidi:
            item['controlCategory'] = row['control_category']
            item['id'] = item['id'] + ':' + row['control_category']
        items.append(item)
    return {'items': items, 'total': total, 'page': page, 'pageSize': page_size, 'pages': pages, 'sourceOfTruth': 'sql'}


def export_telematico_case_catalog(*, repository: Any, fascicoli: list[Any], payload: dict[str, Any]) -> tuple[bytes, str, int]:
    """CSV dalla stessa selezione SQL; nessuna modifica di pratiche o controlli."""
    import csv
    import io
    from pct.formatting import format_datetime_it, parse_datetime_rome
    if not isinstance(payload, dict) or type(payload.get('all')) is not bool:
        raise ValueError('Selezione non valida. Seleziona nuovamente gli elementi.')
    for key in ('total', 'count'):
        if type(payload.get(key)) is not int or payload[key] < 0:
            raise ValueError('Conteggio della selezione non valido.')
    for key in ('selected', 'excluded'):
        values = payload.get(key)
        if not isinstance(values, list) or any(not isinstance(v,str) or not v or len(v)>256 for v in values):
            raise ValueError('Identificativi della selezione non validi.')
        if len(values) != len(set(values)):
            raise ValueError('La selezione contiene elementi ripetuti.')
    portal, query, scope = payload.get('portal',''), payload.get('query',''), payload.get('scope','')
    if not isinstance(portal,str) or not isinstance(query,str) or scope not in ('','presidi'):
        raise ValueError('Filtri della selezione non validi.')
    selected,excluded = set(payload['selected']),set(payload['excluded'])
    if not payload['count']:
        raise ValueError('Seleziona almeno un elemento da esportare.')
    output = io.StringIO(newline='')
    writer = csv.writer(output,delimiter=';',lineterminator='\r\n',quoting=csv.QUOTE_ALL)
    writer.writerow(['Titolo','Contesto','Canale','Stato','Dettaglio','Ultimo aggiornamento'])
    included=set(); current=1
    while True:
        part=build_telematico_case_catalog(repository=repository,fascicoli=fascicoli,portal=portal,query=query,page=current,page_size=100,presidi=scope=='presidi')
        if part['total'] != payload['total']:
            raise ValueError('L’archivio è cambiato. Riprova dopo aver aggiornato il riepilogo.')
        for row in part['items']:
            ident=row['id']
            if ident in included or (ident in excluded if payload['all'] else ident not in selected):
                continue
            included.add(ident)
            detail=(row.get('controlCategory','')+' · ' if row.get('controlCategory') else '')
            detail+=f"{row['documentsCount']} {'documento' if row['documentsCount']==1 else 'documenti'} · {row['openTasks']} {'attività aperta' if row['openTasks']==1 else 'attività aperte'}"
            status={'import completed':'Import completato','manual review required':'Verifica manuale richiesta'}.get(row['statusText'].casefold(),row['statusText'])
            stamp=format_datetime_it(row.get('syncedAt')) if row.get('syncedAt') else ''
            if row.get('syncedAt') and parse_datetime_rome(row['syncedAt']) is None: stamp='Data da verificare'
            values=[row['title'],row['subtitle'],row['portalLabel'],status,detail,stamp]
            writer.writerow(["'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value for value in values])
        if current>=part['pages']:break
        current+=1
    if len(included)!=payload['count']:
        raise ValueError('La selezione è cambiata. Seleziona nuovamente gli elementi disponibili.')
    return ('\ufeff'+output.getvalue()).encode('utf-8'), ('presidi-telematici-selezionati.csv' if scope=='presidi' else 'pratiche-telematiche-selezionate.csv'),len(included)