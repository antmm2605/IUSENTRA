"""Catalogo consultivo dell'elenco: SQL seleziona prima di trasferire le righe.

La proiezione riceve le righe già prodotte dalle regole native. Non legge
documenti, non decide importi e non modifica il fascicolo proprietario.
Preparazione e consegna degli eventi appartengono ai comandi/worker; nessun
DDL, popolamento o recupero dell'intero archivio nelle consultazioni.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta


VERSION = 1
EVENT_TYPE = 'fascicoli_list.refresh_requested'
AGGREGATE = 'fascicoli_list_query'
PAYMENT_FIELDS = {'contributo_unificato', 'fondo_spese', 'spese_esborsi', 'liquidazione_giudice', 'parcella'}
SORTS = ('rg', 'cliente', 'scadenza', 'documenti', 'titolo', 'ufficio', 'apertura',
         'stato', 'gruppo', 'responsabile', 'valore', 'updated')
GROUPS = {'gruppo', 'stato', 'tipo', 'ufficio', 'anno', 'responsabile'}
SEARCH_FIELDS = (
    'ref', 'internalRef', 'title', 'subtitle', 'client', 'court', 'rg', 'rgStatusLabel',
    'rgSourceLabel', 'object', 'procedureType', 'register', 'section', 'sectionRole', 'judge',
    'opposingLawyer', 'holder', 'responsible', 'counterparty', 'claimant', 'clerk', 'ctu', 'ctp',
    'notes', 'operationalStatus', 'customText1', 'customText2', 'groupName',
)
FIELD_KEYS = {
    'register': 'register', 'value': 'value', 'holder': 'holder', 'responsible': 'responsible',
    'object': 'object', 'denomination': 'title', 'internal_ref': 'internalRef', 'rg_year': 'rgYear',
    'court': 'court', 'rg': 'rg', 'section': 'section', 'section_role': 'sectionRole',
    'judge': 'judge', 'opposing_lawyer': 'opposingLawyer', 'notes': 'notes', 'clerk': 'clerk',
    'ctu': 'ctu', 'ctp': 'ctp', 'operational_status': 'operationalStatus',
    'claimant': 'claimant', 'respondent': 'counterparty', 'custom_1': 'customText1',
    'custom_2': 'customText2', 'group': 'groupName',
    'opened_year': 'openedAt', 'archived_year': 'closedAt',
}


def text(value):
    return str(value if value is not None else '').strip()


def contains_pattern(value):
    # LIKE deve cercare anche percentuali/underscore letterali, come Python.
    return '%' + text(value).replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'


def install_schema(conn, *, postgres=False):
    """Solo preparazione esplicita, sul database proprietario già verificato."""
    from pct.transactional_outbox import POSTGRES_SCHEMA
    from pct.operational_live import ensure_domain_signal_schema
    from pct.fascicoli_list_clock import install_clock_schema
    install_clock_schema(conn)
    ensure_domain_signal_schema(conn, 'fascicoli')
    for statement in POSTGRES_SCHEMA.split(';'):
        if statement.strip():
            conn.execute(statement)
    collation = ' COLLATE "C"' if postgres else ' COLLATE BINARY'
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_owner ('
                 'singleton INTEGER PRIMARY KEY,tenant_key TEXT NOT NULL,version INTEGER NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_rows ('
                 'tenant_key TEXT NOT NULL,record_key TEXT NOT NULL,source_revision TEXT NOT NULL,'
                 'source_order TEXT' + collation + ' NOT NULL,payload_json TEXT NOT NULL,search_text TEXT NOT NULL,'
                 'client_text TEXT NOT NULL,rg_text TEXT NOT NULL,court_text TEXT NOT NULL,'
                 'type_key TEXT NOT NULL,status_key TEXT NOT NULL,archived INTEGER NOT NULL,'
                 'alerts INTEGER NOT NULL,communications INTEGER NOT NULL,payments_pending INTEGER NOT NULL,'
                 'missing_rg INTEGER NOT NULL,duplicate_count INTEGER NOT NULL,duplicate_key TEXT NOT NULL,'
                 'next_deadline_day TEXT NOT NULL,'
                 'PRIMARY KEY(tenant_key,record_key))')
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_identity ('
                 'tenant_key TEXT NOT NULL,record_key TEXT NOT NULL,client_key TEXT NOT NULL,'
                 'duplicate_key TEXT NOT NULL,rg_key TEXT NOT NULL,parties_json TEXT NOT NULL,native_json TEXT NOT NULL,'
                 'archived INTEGER NOT NULL,PRIMARY KEY(tenant_key,record_key))')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fascicoli_list_duplicate '
                 'ON fascicoli_list_identity(tenant_key,archived,duplicate_key,record_key)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fascicoli_list_rg '
                 'ON fascicoli_list_identity(tenant_key,archived,rg_key,record_key)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fascicoli_list_client '
                 'ON fascicoli_list_identity(tenant_key,client_key,record_key)')
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_aliases ('
                 'tenant_key TEXT NOT NULL,alias_key TEXT NOT NULL,record_key TEXT NOT NULL,'
                 'PRIMARY KEY(tenant_key,alias_key,record_key))')
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_deadlines ('
                 'tenant_key TEXT NOT NULL,record_key TEXT NOT NULL,matter_key TEXT NOT NULL,'
                 'event_day TEXT NOT NULL,source_revision TEXT NOT NULL,payload_json TEXT NOT NULL,'
                 'PRIMARY KEY(tenant_key,record_key))')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fascicoli_list_deadline_day '
                 'ON fascicoli_list_deadlines(tenant_key,event_day,record_key)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fascicoli_list_deadline_case '
                 'ON fascicoli_list_deadlines(tenant_key,matter_key,record_key)')
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_deadline_links ('
                 'tenant_key TEXT NOT NULL,record_key TEXT NOT NULL,matter_key TEXT NOT NULL,'
                 'PRIMARY KEY(tenant_key,record_key,matter_key))')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fascicoli_list_deadline_link_case '
                 'ON fascicoli_list_deadline_links(tenant_key,matter_key,record_key)')
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_deadline_refs ('
                 'tenant_key TEXT NOT NULL,reference_kind TEXT NOT NULL,reference_key TEXT NOT NULL,record_key TEXT NOT NULL,'
                 'PRIMARY KEY(tenant_key,reference_kind,reference_key,record_key))')
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_fields ('
                 'tenant_key TEXT NOT NULL,record_key TEXT NOT NULL,field_key TEXT NOT NULL,'
                 'field_value TEXT NOT NULL,PRIMARY KEY(tenant_key,record_key,field_key))')
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_metrics ('
                 'tenant_key TEXT NOT NULL,record_key TEXT NOT NULL,metric_key TEXT NOT NULL,'
                 'metric_value DOUBLE PRECISION NOT NULL,PRIMARY KEY(tenant_key,record_key,metric_key))')
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_order ('
                 'tenant_key TEXT NOT NULL,record_key TEXT NOT NULL,sort_key TEXT NOT NULL,'
                 'number_a DOUBLE PRECISION NOT NULL,number_b DOUBLE PRECISION NOT NULL,'
                 'number_c DOUBLE PRECISION NOT NULL,text_a TEXT' + collation + ' NOT NULL,text_b TEXT'
                 + collation + ' NOT NULL,text_c TEXT' + collation + ' NOT NULL,'
                 'PRIMARY KEY(tenant_key,record_key,sort_key))')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fascicoli_list_status '
                 'ON fascicoli_list_rows(tenant_key,archived,status_key,type_key,record_key)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fascicoli_list_order '
                 'ON fascicoli_list_order(tenant_key,sort_key,number_a,number_b,number_c,text_a,text_b,text_c,record_key)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_fascicoli_list_fields '
                 'ON fascicoli_list_fields(tenant_key,field_key,field_value,record_key)')


def install_source_events(conn, *, postgres=False):
    """Stessa outbox nativa; chiavi puntuali, mai una richiesta di scansione."""
    from pct.query_projection_outbox import install_source_trigger
    from pct.transactional_outbox import POSTGRES_SCHEMA
    for statement in POSTGRES_SCHEMA.split(';'):
        if statement.strip():
            conn.execute(statement)
    conn.execute('CREATE INDEX IF NOT EXISTS idx_outbox_fascicoli_list '
                 'ON transactional_outbox(tenant_id,aggregate_type,event_type,status,aggregate_id)')
    owner = '(SELECT tenant_key FROM fascicoli_list_owner WHERE singleton=1)'
    for table, key in (
        ('fascicoli', "'case:' || {row}.id"),
        ('scadenze', "'deadline:' || {row}.id"),
        ('parcelle', "'case:' || {row}.id_fascicolo"),
        ('clienti', "'client:' || {row}.id"),
    ):
        relevant = "TRIM(COALESCE({row}.id_fascicolo,''))<>''" if table == 'parcelle' else 'TRUE'
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            install_source_trigger(conn, table=table, action=action,
                name=f'iusentra_fascicoli_list_{table}_{action.lower()}', tenant_sql=owner,
                aggregate_sql="'" + AGGREGATE + "'", key_sql=key, event_type=EVENT_TYPE,
                predicate=f'{owner} IS NOT NULL AND ({key}) IS NOT NULL AND {relevant}', postgres=postgres)
        old_key, new_key = key.replace('{row}', 'OLD'), key.replace('{row}', 'NEW')
        install_source_trigger(conn, table=table, action='UPDATE',
            name=f'iusentra_fascicoli_list_{table}_old_owner', tenant_sql=owner,
            aggregate_sql="'" + AGGREGATE + "'", key_sql=old_key, event_type=EVENT_TYPE,
            predicate=f'{owner} IS NOT NULL AND ({old_key}) IS NOT NULL '
                      f"AND {relevant.replace('{row}', 'OLD')} "
                      f'AND NOT COALESCE(({old_key})=({new_key}),FALSE)', postgres=postgres)


def install_registry_events(conn, *, tenant, postgres=False):
    """Pubblicazione delle sole fonti del registro che alimentano l'elenco."""
    from pct.query_projection_outbox import install_source_trigger
    from pct.transactional_outbox import POSTGRES_SCHEMA
    for statement in POSTGRES_SCHEMA.split(';'):
        if statement.strip():
            conn.execute(statement)
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_registry_owner ('
                 'tenant_key TEXT PRIMARY KEY,version INTEGER NOT NULL)')
    conn.execute('INSERT INTO fascicoli_list_registry_owner VALUES (?,?) ON CONFLICT(tenant_key) DO NOTHING', (tenant, VERSION))
    conn.execute('CREATE INDEX IF NOT EXISTS idx_outbox_fascicoli_list_registry '
                 'ON transactional_outbox(tenant_id,aggregate_type,event_type,status,aggregate_id)')
    owner_sql = f'EXISTS (SELECT 1 FROM fascicoli_list_registry_owner WHERE tenant_key={{row}}.tenant_id AND version={VERSION})'
    for table in ('letture_fatti', 'letture_oggetti'):
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            install_source_trigger(conn, table=table, action=action,
                name=f'iusentra_fascicoli_list_{table}_{action.lower()}', tenant_sql='{row}.tenant_id',
                aggregate_sql="'" + AGGREGATE + "'", key_sql="'case:' || {row}.fascicolo_id",
                event_type=EVENT_TYPE, predicate=owner_sql, postgres=postgres)
        install_source_trigger(conn, table=table, action='UPDATE',
            name=f'iusentra_fascicoli_list_{table}_old_owner', tenant_sql='OLD.tenant_id',
            aggregate_sql="'" + AGGREGATE + "'", key_sql="'case:' || OLD.fascicolo_id", event_type=EVENT_TYPE,
            predicate=owner_sql.replace('{row}', 'OLD') + ' AND NOT COALESCE('
                '(OLD.tenant_id=NEW.tenant_id AND OLD.fascicolo_id=NEW.fascicolo_id),FALSE)', postgres=postgres)


def assert_registry_ready(conn, tenant):
    owner = conn.execute('SELECT tenant_key,version FROM fascicoli_list_registry_owner WHERE tenant_key=?', (tenant,)).fetchone()
    if owner is None or owner[0] != tenant or owner[1] != VERSION:
        raise FascicoliListNotReady('Registro delle fonti non preparato per il catalogo dello studio.')
    pending = conn.execute('SELECT 1 FROM transactional_outbox WHERE tenant_id=? AND aggregate_type=? '
        "AND event_type=? AND status IN ('PENDING','FAILED') LIMIT 1", (tenant, AGGREGATE, EVENT_TYPE)).fetchone()
    if pending is not None:
        raise FascicoliListNotReady('Nuove fonti del fascicolo: aggiornamento puntuale non ancora confermato.')


class FascicoliListNotReady(RuntimeError):
    pass


class FascicoliListQuery:
    def __init__(self, database, tenant):
        if not tenant:
            raise ValueError('Studio proprietario non determinato.')
        self.database, self.tenant = database, tenant

    def project_identity(self, conn, *, key, client_key, duplicate_key, rg_key, parties, aliases, native, archived):
        if not key or str(native.get('id') or '') != key:
            raise ValueError('Identità del catalogo discordante dalla fonte.')
        conn.execute('INSERT INTO fascicoli_list_identity(tenant_key,record_key,client_key,duplicate_key,rg_key,'
            'parties_json,native_json,archived) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(tenant_key,record_key) DO UPDATE SET '
            'client_key=excluded.client_key,duplicate_key=excluded.duplicate_key,rg_key=excluded.rg_key,'
            'parties_json=excluded.parties_json,native_json=excluded.native_json,archived=excluded.archived',
            (self.tenant, key, client_key, duplicate_key, rg_key, json.dumps(parties, ensure_ascii=False),
             json.dumps(native, ensure_ascii=False), int(archived)))
        conn.execute('DELETE FROM fascicoli_list_aliases WHERE tenant_key=? AND record_key=?', (self.tenant, key))
        for alias in set(aliases):
            conn.execute('INSERT INTO fascicoli_list_aliases(tenant_key,alias_key,record_key) VALUES (?,?,?)',
                         (self.tenant, alias, key))

    def remove(self, conn, key):
        """Rimuove solo una proiezione di una fonte cancellata, mai i dati proprietari."""
        for table in ('fascicoli_list_aliases', 'fascicoli_list_identity', 'fascicoli_list_metrics',
                      'fascicoli_list_fields', 'fascicoli_list_order', 'fascicoli_list_rows'):
            conn.execute('DELETE FROM ' + table + ' WHERE tenant_key=? AND record_key=?', (self.tenant, key))

    def project(self, conn, *, item, revision, source_order, sort_values, summary_values=None, next_deadline_day=''):
        """Scrittore della proiezione, nella transazione della consegna nativa."""
        key = text(item.get('id'))
        if not key or not revision:
            raise ValueError('Identità o revisione della fonte assente.')
        values = dict(
            source_revision=revision, source_order=str(source_order),
            payload_json=json.dumps(item, ensure_ascii=False, separators=(',', ':')),
            search_text=' '.join(text(item.get(name)).lower() for name in SEARCH_FIELDS),
            client_text=text(item.get('client')).lower(), court_text=text(item.get('court')).lower(),
            rg_text=' '.join(text(item.get(name)).lower() for name in ('rg', 'ref', 'rgNumber', 'rgYear', 'rgStatusLabel')),
            type_key=text(item.get('type')).lower(), status_key=text(item.get('status')).lower(),
            archived=int(item.get('status') == 'archiviato'), alerts=int(item.get('alerts') or 0),
            communications=int(item.get('unreadCommunications') or 0),
            payments_pending=int((item.get('paymentSummary') or {}).get('stato') in {'da_presidiare', 'parziale'}),
            missing_rg=int(bool(item.get('rgMissing'))), duplicate_count=int(item.get('duplicateCount') or 0),
            duplicate_key=text(item.get('duplicateKey')), next_deadline_day=next_deadline_day,
        )
        columns = tuple(values)
        conn.execute('INSERT INTO fascicoli_list_rows(tenant_key,record_key,' + ','.join(columns) + ') VALUES ('
                     + ','.join('?' for _ in range(len(columns) + 2)) + ') '
                     'ON CONFLICT(tenant_key,record_key) DO UPDATE SET '
                     + ','.join(name + '=excluded.' + name for name in columns),
                     (self.tenant, key, *values.values()))
        fields = {}
        for name, field in FIELD_KEYS.items():
            value = item.get(field)
            if name == 'object':
                value = value or item.get('subtitle')
            elif name == 'operational_status':
                value = value or item.get('status')
            value = text(value)
            fields[name] = (value[:4] if name in {'opened_year', 'archived_year'} else value).casefold()
        payment_summary = item.get('paymentSummary') or {}
        for kind in PAYMENT_FIELDS:
            fields['payment:' + kind] = text(((payment_summary.get('items') or {}).get(kind) or {}).get('status')).lower()
        fields['payment:parcella_da_emettere'] = str(int(
            int(payment_summary.get('parcelleDaEmettere') or 0) > 0
            or int((payment_summary.get('proformaPresidio') or {}).get('existingDraftCount') or 0) > 0))
        conn.execute('DELETE FROM fascicoli_list_fields WHERE tenant_key=? AND record_key=?', (self.tenant, key))
        for name, value in fields.items():
            conn.execute('INSERT INTO fascicoli_list_fields(tenant_key,record_key,field_key,field_value) '
                         'VALUES (?,?,?,?)', (self.tenant, key, name, value))
        conn.execute('DELETE FROM fascicoli_list_order WHERE tenant_key=? AND record_key=?', (self.tenant, key))
        for name, values in sort_values.items():
            if len(values) != 6:
                raise ValueError('Chiave di ordinamento incompleta.')
            conn.execute('INSERT INTO fascicoli_list_order(tenant_key,record_key,sort_key,'
                         'number_a,number_b,number_c,text_a,text_b,text_c) VALUES (?,?,?,?,?,?,?,?,?)',
                         (self.tenant, key, name, *values))
        conn.execute('DELETE FROM fascicoli_list_metrics WHERE tenant_key=? AND record_key=?', (self.tenant, key))
        for name, value in (summary_values or {}).items():
            if not re.fullmatch('[a-zA-Z][a-zA-Z0-9]*', name) or type(value) not in {int, float}:
                raise ValueError('Metrica consultiva non valida.')
            conn.execute('INSERT INTO fascicoli_list_metrics(tenant_key,record_key,metric_key,metric_value) '
                         'VALUES (?,?,?,?)', (self.tenant, key, name, value))

    def _ready(self):
        from pct.fascicoli_list_clock import clock_ready
        if not clock_ready(self.database.conn, self.tenant):
            raise FascicoliListNotReady('Cambio del giorno: aggiornamento dei soli termini interessati in corso.')
        owner = self.database.conn.execute('SELECT tenant_key,version FROM fascicoli_list_owner WHERE singleton=1').fetchone()
        if owner is None or owner[0] != self.tenant or owner[1] != VERSION:
            raise FascicoliListNotReady('Catalogo fascicoli non attribuito allo studio corrente.')
        pending = self.database.conn.execute('SELECT 1 FROM transactional_outbox WHERE tenant_id=? '
            "AND aggregate_type=? AND event_type=? AND status IN ('PENDING','FAILED') LIMIT 1",
            (self.tenant, AGGREGATE, EVENT_TYPE)).fetchone()
        if pending is not None:
            raise FascicoliListNotReady('Aggiornamento mirato del catalogo fascicoli non ancora confermato.')

    def aggregates(self, **filters):
        """Metriche dell'intera selezione, senza leggere i payload delle pratiche."""
        self._ready()
        where, params = self._selection(**filters)
        conn = self.database.conn
        metrics = conn.execute('SELECT m.metric_key,SUM(m.metric_value) FROM fascicoli_list_metrics m '
            'JOIN fascicoli_list_rows r ON r.tenant_key=m.tenant_key AND r.record_key=m.record_key'
            + where + ' GROUP BY m.metric_key', tuple(params)).fetchall()
        result = {str(row[0]): float(row[1]) for row in metrics}
        duplicate_groups = conn.execute("SELECT COUNT(DISTINCT NULLIF(r.duplicate_key,'')) "
            'FROM fascicoli_list_rows r' + where, tuple(params)).fetchone()[0]
        result['duplicatePractices'] = int(duplicate_groups)
        today = date.today().isoformat()
        week = (date.today() + timedelta(days=7)).isoformat()
        dates = conn.execute('SELECT '
            "SUM(CASE WHEN r.next_deadline_day>=? AND r.next_deadline_day<=? THEN 1 ELSE 0 END) AS next_seven,"
            "SUM(CASE WHEN r.next_deadline_day<>'' AND r.next_deadline_day<? THEN 1 ELSE 0 END) AS overdue "
            'FROM fascicoli_list_rows r' + where, (today, week, today, *params)).fetchone()
        result['deadlines7'], result['overdueDeadlines'] = int(dates[0] or 0), int(dates[1] or 0)
        result['urgentDeadlines'] = result['deadlines7'] + result['overdueDeadlines']
        return result

    def archived_count(self):
        self._ready()
        return int(self.database.conn.execute('SELECT COUNT(*) FROM fascicoli_list_rows WHERE tenant_key=? AND archived=1',
                                             (self.tenant,)).fetchone()[0])

    def deadline_overview(self):
        self._ready()
        today = date.today()
        week, month = today + timedelta(days=7), today + timedelta(days=30)
        conn = self.database.conn
        counts = conn.execute('SELECT '
            'SUM(CASE WHEN event_day>=? AND event_day<=? THEN 1 ELSE 0 END) AS next_seven,'
            'SUM(CASE WHEN event_day>=? AND event_day<=? THEN 1 ELSE 0 END) AS next_thirty,'
            'SUM(CASE WHEN event_day<? THEN 1 ELSE 0 END) AS overdue '
            "FROM fascicoli_list_deadlines WHERE tenant_key=? AND event_day<>''",
            (today.isoformat(), week.isoformat(), today.isoformat(), month.isoformat(), today.isoformat(), self.tenant)).fetchone()
        rows = conn.execute("SELECT payload_json FROM fascicoli_list_deadlines WHERE tenant_key=? AND event_day<>'' "
            'AND event_day<=? ORDER BY event_day,record_key', (self.tenant, week.isoformat())).fetchall()
        return dict(deadlines=[json.loads(row[0]) for row in rows], deadlines7=int(counts[0] or 0),
                    deadlines30=int(counts[1] or 0), overdueDeadlines=int(counts[2] or 0),
                    urgentDeadlines=int(counts[0] or 0) + int(counts[2] or 0))

    def facets(self):
        self._ready()
        rows = self.database.conn.execute('SELECT type_key,status_key,COUNT(*) FROM fascicoli_list_rows '
            'WHERE tenant_key=? AND archived=0 GROUP BY type_key,status_key', (self.tenant,)).fetchall()
        return [dict(type=row[0], status=row[1], count=int(row[2])) for row in rows]

    def _selection(self, *, query='', client='', rg='', court='', type_filter='', status='',
                   field_filters=None, alerts_only=False, communications_only=False,
                   payments_only=False, missing_rg_only=False, duplicates_only=False, payment_filters=None):
        clauses, params = ['r.tenant_key=?', 'r.archived=0'], [self.tenant]
        for column, value in (('search_text', query), ('client_text', client), ('rg_text', rg), ('court_text', court)):
            if text(value):
                clauses.append('r.' + column + " LIKE ? ESCAPE '!'")
                params.append(contains_pattern(text(value).lower()))
        type_filter, status = text(type_filter).lower(), text(status).lower()
        if type_filter not in {'', 'tutti'}:
            clauses.append('r.type_key=?')
            params.append(text(type_filter).lower())
        if status not in {'', 'tutti'}:
            if status == 'definito':
                clauses.append("r.status_key IN ('definito','da_archiviare')")
            else:
                clauses.append('r.status_key=?')
                params.append(text(status).lower())
        for enabled, condition in (
            (alerts_only, '(r.alerts>0 OR r.communications>0)'), (communications_only, 'r.communications>0'),
            (payments_only, 'r.payments_pending=1'), (missing_rg_only, 'r.missing_rg=1'),
            (duplicates_only, 'r.duplicate_count>1'),
        ):
            if enabled:
                clauses.append(condition)
        for name, value in (field_filters or {}).items():
            if name not in FIELD_KEYS:
                raise ValueError('Campo di ricerca non previsto.')
            if text(value):
                clauses.append('EXISTS (SELECT 1 FROM fascicoli_list_fields f WHERE f.tenant_key=r.tenant_key '
                               "AND f.record_key=r.record_key AND f.field_key=? AND f.field_value LIKE ? ESCAPE '!')")
                params.extend((name, contains_pattern(text(value).casefold())))
        for kind, wanted in (payment_filters or {}).items():
            wanted = text(wanted).lower()
            if not wanted or wanted == 'tutti':
                continue
            if kind not in PAYMENT_FIELDS:
                raise ValueError('Filtro economico non previsto.')
            field = 'payment:' + kind
            if kind == 'parcella' and wanted == 'da_emettere':
                field, wanted = 'payment:parcella_da_emettere', '1'
            clauses.append('EXISTS (SELECT 1 FROM fascicoli_list_fields f WHERE f.tenant_key=r.tenant_key '
                           'AND f.record_key=r.record_key AND f.field_key=? AND f.field_value=?)')
            params.extend((field, wanted))
        where = ' WHERE ' + ' AND '.join(clauses)
        return where, params

    def list_page(self, *, page=1, page_size=25, sort='cliente', query='', client='', rg='', court='',
                  type_filter='', status='', field_filters=None, alerts_only=False,
                  communications_only=False, payments_only=False, missing_rg_only=False, duplicates_only=False,
                  payment_filters=None, secondary_sort='', group_by=''):
        """COUNT e LIMIT SQL: soltanto i payload della pagina vengono deserializzati."""
        self._ready()
        if type(page) is not int or type(page_size) is not int or page < 1 or not 1 <= page_size <= 100:
            raise ValueError('Pagina o dimensione non valida.')
        where, params = self._selection(query=query, client=client, rg=rg, court=court,
            type_filter=type_filter, status=status, field_filters=field_filters, alerts_only=alerts_only,
            communications_only=communications_only, payments_only=payments_only,
            missing_rg_only=missing_rg_only, duplicates_only=duplicates_only, payment_filters=payment_filters)
        conn = self.database.conn
        total = int(conn.execute('SELECT COUNT(*) FROM fascicoli_list_rows r' + where, tuple(params)).fetchone()[0])
        pages = (total + page_size - 1) // page_size
        current = min(page, max(1, pages))
        # Il nome dell'ordinamento è un valore, mai SQL ricevuto dall'interfaccia.
        primary = text(sort).lower() or 'rg'
        primary = primary if primary in SORTS else 'updated'
        secondary = text(secondary_sort).lower()
        secondary = secondary if secondary in SORTS else ('updated' if secondary else '')
        group = text(group_by).lower()
        orders = ([('g', 'group:' + group)] if group in GROUPS else []) + [('p', primary)]
        if secondary and secondary != primary:
            orders.append(('s', secondary))
        joins, order_terms, order_params = [], [], []
        for alias, name in orders:
            joins.append('JOIN fascicoli_list_order ' + alias + ' ON ' + alias + '.tenant_key=r.tenant_key '
                         'AND ' + alias + '.record_key=r.record_key AND ' + alias + '.sort_key=?')
            order_params.append(name)
            direction = ' DESC' if name == 'updated' else ' ASC'
            for column in ('number_a', 'number_b', 'number_c', 'text_a', 'text_b', 'text_c'):
                order_terms.append(alias + '.' + column + direction)
        rows = conn.execute('SELECT r.record_key,r.payload_json FROM fascicoli_list_rows r ' + ' '.join(joins)
                            + where + ' ORDER BY ' + ','.join(order_terms) + ',r.source_order DESC LIMIT ? OFFSET ?',
                            (*order_params, *params, page_size, (current - 1) * page_size)).fetchall()
        if len(rows) != min(page_size, max(0, total - (current - 1) * page_size)):
            raise FascicoliListNotReady('Ordinamento del catalogo non confermato.')
        values = []
        for row in rows:
            item = json.loads(row[1])
            if not isinstance(item, dict) or item.get('id') != row[0]:
                raise FascicoliListNotReady('Identità della riga del catalogo non concordante.')
            values.append(item)
        self._ready()
        return dict(items=values, pagination=dict(
            page=current, pageSize=page_size, total=total, pages=pages))
