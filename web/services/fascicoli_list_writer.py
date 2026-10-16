"""Proiezione puntuale dell'elenco, eseguita dai comandi/worker nativi."""
import hashlib
import json
import uuid
from datetime import date

from pct.calendar_sql_records import deadline_from_row
from pct.fascicoli_list_query import AGGREGATE, EVENT_TYPE, FascicoliListQuery
from pct.fatturazione import Parcella
from pct.scadenziario import StatoTermine
from pct.transactional_outbox import OutboxEvent, enqueue
from pct.operational_live import signal_domain_changed
from web.services.fascicoli_list_projection import (
    native_identity_values, native_sort_values, native_summary_values, native_deadline_scope,
)
from web.services.react_fascicoli_bridge import (
    _item_light, _annotate_duplicate_items, _righe_elenco_precaricate, _parse_date,
    _deadline_rows_from_scadenze, _deadline_rg_candidates, _identity_key,
)
from web.services.registro_letture_runtime import con_registro_consultivo


class FascicoliListWriter:
    def __init__(self, database, tenant, native_repository):
        owner = database.conn.execute('SELECT tenant_key FROM fascicoli_list_owner WHERE singleton=1').fetchone()
        if owner is None or owner[0] != tenant:
            raise ValueError('Studio proprietario della proiezione non riscontrato.')
        self.database, self.tenant, self.native = database, tenant, native_repository
        self.repository = FascicoliListQuery(database, tenant)

    def enqueue(self, conn, key):
        # Una consegna PENDING può essere già in esecuzione su un altro worker:
        # saltarla perderebbe l'aggiornamento concorrente appena osservato.
        enqueue(conn, OutboxEvent(tenant_id=self.tenant, aggregate_type=AGGREGATE, aggregate_id=key,
            aggregate_version=1, event_type=EVENT_TYPE, idempotency_key='fascicoli-list:' + uuid.uuid4().hex,
            payload={}, actor_id='native-list-projection'))

    def _lock(self, conn, key):
        if getattr(self.database, 'backend_kind', '') == 'postgresql':
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(?),hashtext(?))', (self.tenant, 'list:' + key))
        else:
            # Anche le consegne provenienti dal registro separato devono
            # prendere il lock prima di leggere fonte e proiezione. La stessa
            # riga resta invariata; nessun evento o dato del fascicolo cambia.
            conn.execute('UPDATE fascicoli_list_owner SET version=version WHERE singleton=1 AND tenant_key=?',
                         (self.tenant,))

    def project_identities(self, conn, keys):
        found = {value.id: value for value in self.native.elenco_per_ids(keys)}
        for key in keys:
            if key in found:
                self.repository.project_identity(conn, **native_identity_values(found[key]))
        return found

    def project_batch(self, conn, keys, *, phase):
        if phase not in {'IDENTITIES', 'DEADLINES', 'ROWS'} or len(keys) > 100:
            raise ValueError('Fase o lotto della preparazione non valido.')
        if phase == 'IDENTITIES':
            self.project_identities(conn, keys)
            return
        for key in keys:
            if phase == 'DEADLINES':
                self.project_deadline(conn, key)
            elif phase == 'ROWS':
                # Conferma solo le consegne già osservate PRIMA della lettura.
                # Un evento concorrente successivo conserva il proprio retry.
                observed = [row[0] for row in conn.execute('SELECT id FROM transactional_outbox '
                    'WHERE tenant_id=? AND aggregate_type=? AND event_type=? AND aggregate_id=? '
                    "AND status IN ('PENDING','FAILED') ORDER BY created_at,id LIMIT 100",
                    (self.tenant, AGGREGATE, EVENT_TYPE, 'case:' + key)).fetchall()]
                self.project_case(conn, key)
                if observed:
                    from datetime import UTC, datetime
                    conn.execute("UPDATE transactional_outbox SET status='PROCESSED',processed_at=? WHERE tenant_id=? AND id IN ("
                        + ','.join('?' for _ in observed) + ')', (datetime.now(UTC).isoformat(), self.tenant, *observed))
            else:
                raise ValueError('Fase della preparazione non prevista.')

    def project_deadline(self, conn, key):
        self._lock(conn, 'deadline:' + key)
        previous_payload = conn.execute('SELECT payload_json FROM fascicoli_list_deadlines '
            'WHERE tenant_key=? AND record_key=?', (self.tenant, key)).fetchone()
        previous_payload = json.loads(previous_payload[0]) if previous_payload else None
        previous = {str(row[0]) for row in conn.execute('SELECT matter_key FROM fascicoli_list_deadline_links '
            'WHERE tenant_key=? AND record_key=?', (self.tenant, key)).fetchall()}
        for table in ('fascicoli_list_deadline_links', 'fascicoli_list_deadline_refs', 'fascicoli_list_deadlines'):
            conn.execute('DELETE FROM ' + table + ' WHERE tenant_key=? AND record_key=?', (self.tenant, key))
        row = conn.execute('SELECT * FROM scadenze WHERE id=?', (key,)).fetchone()
        current_ids = set()
        payload = None
        if row is not None:
            source = deadline_from_row(row)
            if source.stato == StatoTermine.APERTO:
                source.aggiorna_priorita()
                current_ids = native_deadline_scope(self.database, self.tenant, source, connection=conn)
                for matter_key in current_ids:
                    conn.execute('INSERT INTO fascicoli_list_deadline_links(tenant_key,record_key,matter_key) '
                                 'VALUES (?,?,?)', (self.tenant, key, matter_key))
                references = {('rg', rg) for rg in _deadline_rg_candidates(source)}
                if source.id_fascicolo:
                    references.add(('alias', _identity_key(source.id_fascicolo)))
                for kind, value in references:
                    conn.execute('INSERT INTO fascicoli_list_deadline_refs(tenant_key,reference_kind,reference_key,record_key) '
                                 'VALUES (?,?,?,?)', (self.tenant, kind, value, key))
                matter_key = min(current_ids) if current_ids else str(source.id_fascicolo or '')
                matter = conn.execute('SELECT payload_json FROM fascicoli_list_rows WHERE tenant_key=? AND record_key=? AND archived=0',
                                      (self.tenant, matter_key)).fetchone()
                day = _parse_date(source.data_scadenza)
                # Un solo termine, con la sua data effettiva; l'intervallo
                # della pagina sarà applicato dalla consultazione SQL.
                displayed = _deadline_rows_from_scadenze([source], {matter_key: json.loads(matter[0])} if matter else {},
                    days=max(0, (day - date.today()).days) if day else 0, resolved_matter_ids={key: matter_key})
                payload = displayed[0] if displayed else {'id': key, 'matterId': matter_key}
                revision = hashlib.sha256(json.dumps(dict(row), sort_keys=True, default=str).encode()).hexdigest()
                conn.execute('INSERT INTO fascicoli_list_deadlines(tenant_key,record_key,matter_key,event_day,source_revision,payload_json) '
                    'VALUES (?,?,?,?,?,?)', (self.tenant, key, matter_key, day.isoformat() if day else '', revision,
                                            json.dumps(payload, ensure_ascii=False)))
        for matter_key in previous | current_ids:
            self.enqueue(conn, 'case:' + matter_key)
        if previous_payload != payload or previous != current_ids:
            signal_domain_changed(conn, 'fascicoli')

    @con_registro_consultivo
    def project_case(self, conn, key):
        self._lock(conn, 'case:' + key)
        previous = conn.execute('SELECT * FROM fascicoli_list_identity WHERE tenant_key=? AND record_key=?',
                                (self.tenant, key)).fetchone()
        previous = dict(previous) if previous else None
        previous_aliases = {str(row[0]) for row in conn.execute('SELECT alias_key FROM fascicoli_list_aliases '
            'WHERE tenant_key=? AND record_key=?', (self.tenant, key)).fetchall()}
        found = {value.id: value for value in self.native.elenco_per_ids([key])}
        identity = native_identity_values(found[key]) if key in found else None
        changed = (previous is None) != (identity is None)
        if previous is not None and identity is not None:
            changed = (json.loads(previous['native_json']) != identity['native']
                or json.loads(previous['parties_json']) != identity['parties']
                or previous['client_key'] != identity['client_key']
                or previous['archived'] != int(identity['archived'])
                or previous_aliases != set(identity['aliases']))
        if changed and identity is not None:
            self.repository.project_identity(conn, **identity)
        if changed:
            duplicate_keys = {value for value in (
                previous['duplicate_key'] if previous else '', identity['duplicate_key'] if identity else '',
            ) if value}
            for duplicate_key in duplicate_keys:
                peers = conn.execute('SELECT record_key FROM fascicoli_list_identity '
                    'WHERE tenant_key=? AND archived=0 AND duplicate_key=?', (self.tenant, duplicate_key)).fetchall()
                for peer in peers:
                    if peer[0] != key:
                        self.enqueue(conn, 'case:' + str(peer[0]))
            references = {('alias', value) for value in previous_aliases}
            if identity:
                references.update(('alias', value) for value in identity['aliases'])
            references.update(('rg', value) for value in (
                previous['rg_key'] if previous else '', identity['rg_key'] if identity else '',
            ) if value)
            for kind, reference in references:
                for row in conn.execute('SELECT record_key FROM fascicoli_list_deadline_refs '
                    'WHERE tenant_key=? AND reference_kind=? AND reference_key=?', (self.tenant, kind, reference)).fetchall():
                    self.enqueue(conn, 'deadline:' + str(row[0]))
        if key not in found:
            present = conn.execute('SELECT 1 FROM fascicoli_list_rows WHERE tenant_key=? AND record_key=?',
                                   (self.tenant, key)).fetchone()
            self.repository.remove(conn, key)
            if present:
                signal_domain_changed(conn, 'fascicoli')
            return
        model = found[key]
        deadlines = [deadline_from_row(row) for row in conn.execute(
            'SELECT s.* FROM scadenze s JOIN fascicoli_list_deadline_links l ON l.record_key=s.id '
            'WHERE l.tenant_key=? AND l.matter_key=?', (self.tenant, key)).fetchall()]
        deadlines = [value for value in deadlines if value.stato == StatoTermine.APERTO]
        for deadline in deadlines:
            deadline.aggiorna_priorita()
        invoices = []
        for row in conn.execute('SELECT id,id_fascicolo,dati_json FROM parcelle WHERE id_fascicolo=?', (key,)).fetchall():
            invoice = Parcella.from_dict(json.loads(row['dati_json']))
            if invoice.id != row['id'] or invoice.id_fascicolo != key:
                raise ValueError('Collegamento SQL della parcella non concordante con la fonte nativa.')
            invoices.append(invoice)
        # Il gruppo serve agli stessi avvisi nativi, senza caricare le pratiche
        # estranee al gruppo del fascicolo interessato.
        from types import SimpleNamespace
        from pct.fascicolo_document_presidio import duplicate_practice_groups
        group_models = [SimpleNamespace(**json.loads(row[0])) for row in conn.execute(
            'SELECT native_json FROM fascicoli_list_identity WHERE tenant_key=? AND archived=0 AND duplicate_key=? '
            "AND duplicate_key<>''", (self.tenant, identity['duplicate_key'])).fetchall()]
        group_models.sort(key=lambda value: value.numero, reverse=True)
        groups = duplicate_practice_groups(group_models)
        groups_by_key = {value['key']: value for value in groups}
        item = _righe_elenco_precaricate([model], lambda: _annotate_duplicate_items([
            _item_light(model, scadenze_by_fasc={key: deadlines}, automatic_evidence=False,
                full_payment_summary=False, parcelle=invoices, duplicate_group=groups_by_key.get(identity['duplicate_key'])),
        ], groups_by_key)[0])
        day = _parse_date(item.get('nextDeadlineIso'))
        revision = hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        current = conn.execute('SELECT source_revision FROM fascicoli_list_rows WHERE tenant_key=? AND record_key=?',
                               (self.tenant, key)).fetchone()
        if current is not None and current[0] == revision:
            return {'state': 'already_present', 'key': key, 'revision': revision}
        self.repository.project(conn, item=item, revision=revision, source_order=model.numero,
            sort_values=native_sort_values(item), summary_values=native_summary_values(item),
            next_deadline_day=day.isoformat() if day else '')
        for row in conn.execute('SELECT record_key,payload_json FROM fascicoli_list_deadlines '
            'WHERE tenant_key=? AND matter_key=?', (self.tenant, key)).fetchall():
            payload = json.loads(row[1])
            payload['matterRef'] = item['ref'] if item.get('status') != 'archiviato' else key
            conn.execute('UPDATE fascicoli_list_deadlines SET payload_json=? WHERE tenant_key=? AND record_key=?',
                         (json.dumps(payload, ensure_ascii=False), self.tenant, row[0]))
        signal_domain_changed(conn, 'fascicoli')
        return {'state': 'updated', 'key': key, 'revision': revision}

    def handle_event(self, conn, key):
        # Solo errori antecedenti alla nuova lettura possono essere confermati
        # dalla stessa proiezione riuscita; eventi successivi restano pendenti.
        failed = [row[0] for row in conn.execute('SELECT id FROM transactional_outbox WHERE tenant_id=? '
            "AND aggregate_type=? AND event_type=? AND aggregate_id=? AND status='FAILED'",
            (self.tenant, AGGREGATE, EVENT_TYPE, key)).fetchall()]
        self._project_event(conn, key)
        confirm_recovered_events(conn, self.tenant, failed)

    def _project_event(self, conn, key):
        kind, separator, identity = key.partition(':')
        if not separator or not identity:
            raise ValueError('Identità dell’evento del catalogo non valida.')
        if kind == 'case':
            self.project_case(conn, identity)
        elif kind == 'deadline':
            self.project_deadline(conn, identity)
        elif kind == 'client':
            for row in conn.execute('SELECT record_key FROM fascicoli_list_identity '
                'WHERE tenant_key=? AND client_key=?', (self.tenant, identity)).fetchall():
                self.enqueue(conn, 'case:' + str(row[0]))
        else:
            raise ValueError('Tipo di evento del catalogo non previsto.')

    def recover(self, *, limit=50):
        from pct.query_projection_worker import deliver_pending
        writable = getattr(self.database, '_conn_per_scrittura', None)
        conn = writable() if callable(writable) else self.database.conn
        owner = conn.execute('SELECT tenant_key FROM fascicoli_list_owner WHERE singleton=1').fetchone()
        if owner is None or owner[0] != self.tenant:
            raise ValueError('Studio proprietario della proiezione non riscontrato.')

        def finish(connection, *, rollback=False):
            target = getattr(self.database, 'raw_conn', None) or connection
            target.rollback() if rollback else target.commit()

        return deliver_pending(conn=conn, finish=finish, tenant=self.tenant, aggregate=AGGREGATE,
                               event_type=EVENT_TYPE, project=self.handle_event, limit=limit)


def confirm_recovered_events(conn, tenant, event_ids):
    from datetime import UTC, datetime
    for event_id in event_ids:
        conn.execute("UPDATE transactional_outbox SET status='PROCESSED',processed_at=?,"
            "last_error=COALESCE(last_error,'') || ' [Recuperato dalla successiva proiezione della stessa fonte.]' "
            "WHERE id=? AND tenant_id=? AND aggregate_type=? AND event_type=? AND status='FAILED'",
            (datetime.now(UTC).isoformat(), event_id, tenant, AGGREGATE, EVENT_TYPE))
