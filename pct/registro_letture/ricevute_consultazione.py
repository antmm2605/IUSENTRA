"""Ricevute nei fascicoli e nelle PEC: riuso delle letture, nessuna nuova OCR."""
import re
from contextlib import nullcontext
from datetime import UTC, date, datetime, time, timedelta

from pct.formatting import DISPLAY_TIMEZONE


def _receipt_date(candidates):
    """Una data giornaliera non contraddice un'ora nello stesso giorno.

    Si confrontano gli intervalli dimostrati dalla precisione effettiva:
    giorno, minuto, secondo o frazione. Nessuna data di importazione e
    nessuna preferenza arbitraria fra istanti incompatibili.
    """
    if not candidates:
        return '', 'event_date_not_available', ''
    values = []
    try:
        for raw in sorted(candidates):
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
                day = date.fromisoformat(raw)
                start = datetime.combine(day, time.min, DISPLAY_TIMEZONE).astimezone(UTC)
                end = datetime.combine(day + timedelta(days=1), time.min, DISPLAY_TIMEZONE).astimezone(UTC)
                values.append((start, end, day.isoformat(), 'day'))
                continue
            match = re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.(\d{1,6}))?)?(?:Z|[+-]\d{2}:\d{2})?', raw)
            if match is None:
                raise ValueError('Data probatoria non ISO.')
            stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=DISPLAY_TIMEZONE)
                if stamp.astimezone(UTC).astimezone(DISPLAY_TIMEZONE).replace(tzinfo=None) != stamp.replace(tzinfo=None):
                    raise ValueError('Ora locale non esistente.')
                if stamp.replace(fold=1).utcoffset() != stamp.utcoffset():
                    return '', 'source_time_zone_ambiguous', ''
            start = stamp.astimezone(UTC)
            fraction = match.group(1)
            if fraction:
                step, precision = timedelta(microseconds=10 ** (6 - len(fraction))), 'fraction'
            elif re.search(r'T\d{2}:\d{2}:\d{2}', raw):
                step, precision = timedelta(seconds=1), 'second'
            else:
                step, precision = timedelta(minutes=1), 'minute'
            values.append((start, start + step, stamp.isoformat(), precision))
    except (ValueError, OverflowError):
        return '', 'source_date_invalid', ''
    if max(item[0] for item in values) >= min(item[1] for item in values):
        return '', 'source_dates_discordant', ''
    chosen = min(values, key=lambda item: item[1] - item[0])
    return chosen[2], '', chosen[3]


def _engine_version_current(row):
    """La versione è valutata dal preparatore, mai da una rilettura OCR.

    La correzione manuale appartiene alla fonte con la medesima impronta e
    non è invalidata soltanto perché è cambiata la versione del lettore.
    """
    if row['verifica'] == 'corretta':
        return True
    from pct.registro_letture.lettori import versione_compatibile_lettore

    reader = {'documenti': 'motore_documenti', 'pec': 'motore_pec'}.get(row['motore'])
    return bool(reader and versione_compatibile_lettore(reader, row['versione_motore']))


def _source_dates(conn, tenant, sources):
    """Date già collaudate della stessa fonte; mai date di importazione."""
    found = {}
    for offset in range(0, len(sources), 100):
        batch = sources[offset:offset + 100]
        keys = list(dict.fromkeys(tuple(row[field] for field in
                    ('fascicolo_id', 'tipo', 'oggetto_id', 'sha256', 'motore', 'versione_motore')) for row in batch))
        if not keys:
            continue
        condition = ' OR '.join("(fascicolo_id=? AND tipo=? AND oggetto_id=? AND sha256=? AND ((motore=? AND versione_motore=?) OR verifica='corretta'))" for _ in keys)
        rows = conn.execute('SELECT fascicolo_id,tipo,oggetto_id,sha256,motore,versione_motore,campo,valore,verifica FROM letture_fatti '
            "WHERE tenant_id=? AND categoria='data' AND campo IN ('accettazione','consegna') "
            "AND verifica IN ('verificata','corretta') AND (" + condition + ') LIMIT 10001',
            (tenant, *(value for key in keys for value in key))).fetchall()
        if len(rows) > 10000:
            for key in keys:
                found[key] = {'overflow': True}
            continue
        for value in rows:
            row = dict(value)
            key = tuple(row[field] for field in ('fascicolo_id', 'tipo', 'oggetto_id', 'sha256', 'motore', 'versione_motore'))
            applicable = [item for item in keys if item[:4] == key[:4]] if row['verifica'] == 'corretta' else [key]
            for item in applicable:
                found.setdefault(item, {}).setdefault(row['campo'], set()).add(str(row['valore'] or ''))
    return found


def receipt_sources(registry, *, tenant, case_ids, limit=100, cursor='', connection=None):
    """Una pagina di fonti, non una nuova attribuzione o conferma del deposito.

    Anche le prove non confermate restano visibili con motivo; una copia con
    impronta superata non può diventare una ricevuta verificata. I documenti
    presenti nel fascicolo non sono esclusi a favore delle sole PEC.
    Se fornita, la connessione appartiene alla transazione del chiamante:
    la lettura non la chiude e non ne conferma o annulla le scritture.
    """
    cases = list(dict.fromkeys(str(value).strip() for value in case_ids if str(value).strip()))
    if not tenant or not cases or len(cases) > 100:
        raise ValueError('Servono studio e fascicoli espliciti, entro il lotto autorizzato.')
    size = max(1, min(int(limit), 500))
    sql = (
        'SELECT f.id,f.fascicolo_id,f.tipo,f.oggetto_id,f.sha256,f.motore,f.versione_motore,f.campo,f.verifica,f.prove_json,'
        'o.nome,o.sha256 AS current_sha256,o.presente '
        'FROM letture_fatti f LEFT JOIN letture_oggetti o ON '
        'o.tenant_id=f.tenant_id AND o.fascicolo_id=f.fascicolo_id AND o.tipo=f.tipo AND o.oggetto_id=f.oggetto_id '
        "WHERE f.tenant_id=? AND f.categoria='prova_notifica' AND f.campo IN ('rac','rdac','deposito_prova') "
        "AND f.verifica<>'ignorata' AND f.fascicolo_id IN (" + ','.join('?' for _ in cases) + ') '
        'AND f.id>? AND (o.presente IS NULL OR o.presente=1) ORDER BY f.id LIMIT ?'
    )
    owns_connection = connection is None
    opened = None
    try:
        with (registry.connection() if owns_connection else nullcontext(connection)) as conn:
            opened = conn
            rows = conn.execute(sql, (tenant, *cases, cursor, size + 1)).fetchall()
            dates = _source_dates(conn, tenant, rows[:size])
    finally:
        if owns_connection and opened is not None and registry.backend_kind == 'sqlite':
            opened.close()
    result = []
    for source in rows[:size]:
        row = dict(source)
        sha = str(row['sha256'] or '').lower()
        issue = ''
        if row['presente'] is None:
            issue = 'catalog_source_missing'
        elif len(sha) != 64 or any(ch not in '0123456789abcdef' for ch in sha):
            issue = 'source_fingerprint_not_available'
        elif sha != str(row['current_sha256'] or '').lower():
            issue = 'source_revision_changed'
        elif row['verifica'] not in {'verificata', 'corretta'}:
            issue = 'proof_not_confirmed'
        elif not _engine_version_current(row):
            issue = 'reader_version_not_current'
        row['verified'] = not issue
        row['classification_verified'] = not issue
        row['issue'] = issue
        values = dates.get(tuple(row[field] for field in ('fascicolo_id', 'tipo', 'oggetto_id', 'sha256', 'motore', 'versione_motore')), {})
        candidates = values.get('accettazione' if row['campo'] == 'rac' else 'consegna' if row['campo'] == 'rdac' else '', set())
        row['event_date'], row['date_issue'], row['date_precision'] = '', 'event_date_not_available', ''
        row['date_evidence'] = sorted(candidates)
        if values.get('overflow'):
            row['date_issue'] = 'source_dates_budget_exceeded'
        else:
            row['event_date'], row['date_issue'], row['date_precision'] = _receipt_date(candidates)
        # Questa chiave identifica soltanto copie byte-per-byte dello stesso
        # contenuto e tipo di prova nello stesso fascicolo, non tutti i depositi.
        row['exact_copy_key'] = (row['fascicolo_id'], row['campo'], sha) if not issue else None
        result.append(row)
    return dict(rows=result, has_more=len(rows) > size,
                cursor=result[-1]['id'] if len(rows) > size else None)


def group_exact_receipt_copies(rows):
    """Unisce soltanto copie dimostrate, conservando ogni puntatore alla fonte.

    Il chiamante passa le pagine del lotto completo: il gruppo non trasforma
    il limite di una pagina nel conteggio totale delle ricevute del fascicolo.
    """
    groups = {}
    for row in rows:
        key = row.get('exact_copy_key')
        key = ('exact', *key) if key else ('unconfirmed', row['id'])
        if key not in groups:
            groups[key] = dict(campo=row['campo'], fascicolo_id=row['fascicolo_id'],
                               verified=row['verified'], issue=row['issue'], sources=[])
        sources = groups[key]['sources']
        if not any(source['id'] == row['id'] for source in sources):
            sources.append(dict(row))
    return list(groups.values())
