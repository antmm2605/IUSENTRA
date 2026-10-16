"""Caselle SQL tenant-aware: mutazioni puntuali, audit atomico, JSON solo mirror.

Il repository non importa JSON durante una lettura e non sostituisce le
procedure MIME/IMAP/SMTP del gestore. L'inizializzazione deve essere eseguita
da una migrazione governata prima di attivare il relativo adattatore runtime.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from pct.email_mailbox_query_index import (
    DDL as QUERY_INDEX_DDL,
    delete_projection,
    source_revision,
    upsert_projection,
)
from pct.formatting import DISPLAY_TIMEZONE
from pct.email_mailbox_query_events import (
    acknowledge_projection, install_query_events, mark_bootstrapped, projection_ready,
)

logger = logging.getLogger(__name__)
KINDS = {'pec': 'email_casella', 'ordinary': 'email_ordinaria'}
DDL = (
    """CREATE TABLE IF NOT EXISTS email_mailbox_records (
        tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL,
        message_key TEXT NOT NULL, folder TEXT NOT NULL, read_state TEXT NOT NULL,
        message_date TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_key,mailbox_kind,message_key))""",
    """CREATE INDEX IF NOT EXISTS idx_email_mailbox_folder_state
        ON email_mailbox_records (tenant_key,mailbox_kind,folder,read_state)""",
    """CREATE TABLE IF NOT EXISTS email_mailbox_bootstrap (
        tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL,
        source_of_truth TEXT NOT NULL, initialized_at TEXT NOT NULL,
        PRIMARY KEY (tenant_key,mailbox_kind))""",
    """CREATE TABLE IF NOT EXISTS email_mailbox_audit (
        audit_key TEXT PRIMARY KEY, tenant_key TEXT NOT NULL,
        mailbox_kind TEXT NOT NULL, message_key TEXT NOT NULL,
        action TEXT NOT NULL, actor_key TEXT NOT NULL,
        changed_fields_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
) + QUERY_INDEX_DDL


class MailboxConflict(RuntimeError):
    """La modifica concorrente va riesaminata, mai sovrascritta."""


class MailboxNotInitialized(RuntimeError):
    """La migrazione governata della casella non è ancora registrata."""


class MailboxQueryIndexNotReady(RuntimeError):
    """Proiezione consultiva incompleta: non esporre un elenco parziale."""


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _validate(records):
    if not isinstance(records, dict):
        raise ValueError('Archivio della casella non valido.')
    for key, value in records.items():
        if not isinstance(value, dict) or str(value.get('id', '')) != str(key):
            raise ValueError('Identità del messaggio non coerente con il catalogo.')
    return records


class EmailMailboxRepository:
    def __init__(self, studio_db, tenant_key: str, mailbox_kind: str, mirror_path=None):
        if not str(tenant_key).strip() or mailbox_kind not in KINDS:
            raise ValueError('Contesto studio o casella non valido.')
        self.db, self.tenant, self.kind = studio_db, str(tenant_key), mailbox_kind
        self.mirror_path = Path(mirror_path) if mirror_path is not None else None
        self.original = None

    def _write_conn(self):
        writable = getattr(self.db, '_conn_per_scrittura', None)
        return writable() if callable(writable) else self.db.conn

    def _finish(self, conn, *, rollback=False):
        raw = getattr(self.db, 'raw_conn', None)
        target = raw if raw is not None else conn
        target.rollback() if rollback else target.commit()

    def ensure_schema(self):
        conn = self._write_conn()
        try:
            for statement in DDL:
                conn.execute(statement)
            install_query_events(conn, postgres=hasattr(conn, '_backend'))
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise

    def initialize(self, records, *, source_of_truth: str):
        """Import esplicito dopo backup e verifica della fonte primaria."""
        records = _validate(records)
        if source_of_truth not in {'sqlite', 'postgresql', 'controlled_source_reconciliation'}:
            raise ValueError('Origine della migrazione non verificata.')
        conn = self._write_conn()
        try:
            stamp = datetime.now(timezone.utc).isoformat()
            marker = conn.execute(
                'INSERT INTO email_mailbox_bootstrap (tenant_key,mailbox_kind,source_of_truth,initialized_at) '
                'VALUES (?,?,?,?) ON CONFLICT (tenant_key,mailbox_kind) DO NOTHING RETURNING tenant_key',
                (self.tenant, self.kind, source_of_truth, stamp),
            ).fetchone()
            if marker is None:
                raise MailboxConflict('La casella è già inizializzata; non può essere sostituita da un import.')
            for key, record in records.items():
                self._insert(conn, key, record, stamp)
                self._audit(conn, key, 'initialize', 'migration', list(record), stamp)
            mark_bootstrapped(conn, self.tenant, self.kind)
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise

    def _insert(self, conn, key, record, stamp):
        result = conn.execute(
            'INSERT INTO email_mailbox_records '
            '(tenant_key,mailbox_kind,message_key,folder,read_state,message_date,payload_json,updated_at) '
            'VALUES (?,?,?,?,?,?,?,?) ON CONFLICT (tenant_key,mailbox_kind,message_key) DO NOTHING RETURNING message_key',
            (self.tenant, self.kind, str(key), str(record.get('cartella', 'INBOX')),
             str(record.get('stato', 'NON_LETTA')), str(record.get('data', '')), _encode(record), stamp),
        ).fetchone()
        if result is None:
            raise MailboxConflict('Il messaggio è stato acquisito da un’altra operazione. Ricarica la casella.')
        upsert_projection(conn, self.tenant, self.kind, str(key), record)
        acknowledge_projection(conn, self.tenant, self.kind, str(key))

    def _audit(self, conn, key, action, actor, fields, stamp):
        conn.execute(
            'INSERT INTO email_mailbox_audit '
            '(audit_key,tenant_key,mailbox_kind,message_key,action,actor_key,changed_fields_json,created_at) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (uuid.uuid4().hex, self.tenant, self.kind, str(key), action, actor, _encode(sorted(fields)), stamp),
        )

    def _assert_initialized(self):
        marker = self.db.conn.execute(
            'SELECT source_of_truth FROM email_mailbox_bootstrap WHERE tenant_key=? AND mailbox_kind=?',
            (self.tenant, self.kind),
        ).fetchone()
        if marker is None:
            raise MailboxNotInitialized('Archivio della casella da riallineare: nessuna lettura da copie storiche.')

    def count(self) -> int:
        """Conta il catalogo primario senza corpi, allegati o riparazioni."""
        self._assert_initialized()
        return int(self.db.conn.execute(
            'SELECT COUNT(*) FROM email_mailbox_records WHERE tenant_key=? AND mailbox_kind=?',
            (self.tenant, self.kind),
        ).fetchone()[0])

    def query_records(self, *, ranges=(), direction='', folder='', deposit_status='', limit=50, cursor=None):
        """Pagina SQL consultiva; mai load, deduplicazione, import o salvataggio."""
        self._assert_initialized()
        if direction not in {'', 'received', 'sent', 'draft', 'unknown'}:
            raise ValueError('Direzione della posta non valida.')
        if folder not in {'', 'INBOX', 'INVIATI', 'BOZZE', 'CESTINO', 'ARCHIVIO'}:
            raise ValueError('Cartella della posta non valida.')
        if deposit_status:
            from pct.fascicoli import STATI_DEPOSITO_PCT_CANONICI
            if deposit_status not in STATI_DEPOSITO_PCT_CANONICI:
                raise ValueError('Stato del deposito non valido.')
        page_size = max(1, min(int(limit), 100))
        scope = (self.tenant, self.kind)
        if not projection_ready(self.db.conn, self.tenant, self.kind):
            raise MailboxQueryIndexNotReady('Indice della casella incompleto: serve il riallineamento governato.')
        where, params = ['q.tenant_key=?', 'q.mailbox_kind=?'], list(scope)
        if direction:
            where.append('q.direction=?')
            params.append(direction)
        if deposit_status:
            where.append('q.deposit_status=?')
            params.append(deposit_status)
        if folder:
            where.append('EXISTS (SELECT 1 FROM email_mailbox_records f '
                         'WHERE f.tenant_key=q.tenant_key AND f.mailbox_kind=q.mailbox_kind '
                         'AND f.message_key=q.message_key AND f.folder=?)')
            params.append(folder)
        unknown = self.db.conn.execute(
            'SELECT COUNT(*) FROM email_mailbox_query_index q WHERE ' + ' AND '.join(where)
            + " AND q.event_at_utc=''", tuple(params),
        ).fetchone()[0]
        clauses = []
        for start, end in ranges:
            if end < start:
                raise ValueError('Intervallo della consultazione invertito.')
            lower = datetime.combine(start, time.min, DISPLAY_TIMEZONE).astimezone(timezone.utc)
            upper = datetime.combine(end + timedelta(days=1), time.min, DISPLAY_TIMEZONE).astimezone(timezone.utc)
            clauses.append('(q.event_at_utc>=? AND q.event_at_utc<?)')
            params.extend((lower.isoformat(timespec='microseconds'), upper.isoformat(timespec='microseconds')))
        if clauses:
            where.append('(' + ' OR '.join(clauses) + ')')
        unknown_direction = 0
        if direction in {'received', 'sent'}:
            uncertain_params = list(params)
            uncertain_params[2] = 'unknown'
            unknown_direction = int(self.db.conn.execute(
                'SELECT COUNT(*) FROM email_mailbox_query_index q WHERE ' + ' AND '.join(where),
                tuple(uncertain_params),
            ).fetchone()[0])
        if cursor:
            stamp, key = cursor
            where.append('(q.event_at_utc<? OR (q.event_at_utc=? AND q.message_key<?))')
            params.extend((stamp, stamp, key))
        rows = self.db.conn.execute(
            'SELECT q.event_at_utc,q.message_key,q.source_revision,r.payload_json '
            'FROM email_mailbox_query_index q JOIN email_mailbox_records r '
            'ON r.tenant_key=q.tenant_key AND r.mailbox_kind=q.mailbox_kind AND r.message_key=q.message_key '
            'WHERE ' + ' AND '.join(where) + ' ORDER BY q.event_at_utc DESC,q.message_key DESC LIMIT ?',
            tuple(params + [page_size + 1]),
        ).fetchall()
        payloads = []
        for row in rows[:page_size]:
            payload = json.loads(row[3])
            if source_revision(payload) != row[2]:
                raise MailboxQueryIndexNotReady('Il messaggio è cambiato: indice della casella da riallineare.')
            payloads.append(payload)
        if not projection_ready(self.db.conn, self.tenant, self.kind):
            raise MailboxQueryIndexNotReady('La casella è cambiata durante la consultazione: indice da riallineare.')
        has_more = len(rows) > page_size
        return {'rows': payloads, 'has_more': has_more,
                'cursor': (rows[page_size - 1][0], rows[page_size - 1][1]) if has_more else None,
                'unknown_date_count': int(unknown), 'unknown_direction_count': unknown_direction}

    def begin_query_index_migration(self, *, backup_reference, backup_sha256, actor_key):
        """Registra la prova di backup del chiamante e il cursore SQL persistente."""
        if not actor_key or not str(backup_reference).strip() or not isinstance(backup_sha256, str) or len(backup_sha256) != 64 or any(ch not in '0123456789abcdef' for ch in backup_sha256):
            raise ValueError('Backup e autore verificabili sono obbligatori per la migrazione.')
        self._assert_initialized()
        conn = self._write_conn()
        try:
            previous = conn.execute('SELECT id,backup_sha256,phase,after_key FROM email_mailbox_query_migrations '
                                    'WHERE tenant_key=? AND mailbox_kind=? AND backup_reference=?',
                                    (self.tenant, self.kind, backup_reference)).fetchone()
            if previous is not None:
                if previous[1] != backup_sha256:
                    raise MailboxConflict('Impronta del backup discordante: migrazione sospesa.')
                self._finish(conn)
                return {'id': previous[0], 'phase': previous[2], 'after_key': previous[3]}
            migration_id = uuid.uuid4().hex
            stamp = datetime.now(timezone.utc).isoformat()
            conn.execute('INSERT INTO email_mailbox_query_migrations '
                         '(id,tenant_key,mailbox_kind,backup_reference,backup_sha256,actor_key,phase,created_at,updated_at) '
                         "VALUES (?,?,?,?,?,?,'BACKFILL',?,?)",
                         (migration_id, self.tenant, self.kind, backup_reference, backup_sha256, actor_key, stamp, stamp))
            conn.execute('INSERT INTO email_mailbox_query_bootstrap(tenant_key,mailbox_kind,version) '
                         'VALUES (?,?,0) ON CONFLICT(tenant_key,mailbox_kind) DO UPDATE SET version=0',
                         (self.tenant, self.kind))
            self._finish(conn)
            return {'id': migration_id, 'phase': 'BACKFILL', 'after_key': ''}
        except Exception:
            self._finish(conn, rollback=True)
            raise

    def rebuild_query_index_batch(self, *, migration_id, after_key='', limit=100, actor_key):
        """Migrazione esplicita riprendibile, da eseguire dopo backup coerente."""
        if not actor_key:
            raise ValueError('Autore della migrazione mancante.')
        self._assert_initialized()
        conn = self._write_conn()
        try:
            locked = conn.execute('UPDATE email_mailbox_query_migrations SET updated_at=? '
                                  "WHERE id=? AND tenant_key=? AND mailbox_kind=? AND phase='BACKFILL' "
                                  'AND after_key=? AND actor_key=? RETURNING id',
                                  (datetime.now(timezone.utc).isoformat(), migration_id, self.tenant, self.kind, after_key, actor_key)).fetchone()
            if locked is None:
                raise MailboxConflict('Cursore o autore della migrazione discordante: ripresa non eseguita.')
            rows = conn.execute(
                'SELECT message_key,payload_json FROM email_mailbox_records '
                'WHERE tenant_key=? AND mailbox_kind=? AND message_key>? ORDER BY message_key LIMIT ?',
                (self.tenant, self.kind, after_key, max(1, min(int(limit), 500))),
            ).fetchall()
            stamp = datetime.now(timezone.utc).isoformat()
            for row in rows:
                key, raw = row[0], row[1]
                # Il lock SQL mantiene la proiezione nella stessa revisione
                # anche se un produttore acquisisce una nuova versione.
                current = conn.execute(
                    'UPDATE email_mailbox_records SET updated_at=updated_at '
                    'WHERE tenant_key=? AND mailbox_kind=? AND message_key=? AND payload_json=? '
                    'RETURNING payload_json', (self.tenant, self.kind, key, raw),
                ).fetchone()
                if current is None:
                    raise MailboxConflict('Messaggio cambiato durante il riallineamento: ripetere il lotto.')
                upsert_projection(conn, self.tenant, self.kind, key, json.loads(raw))
                acknowledge_projection(conn, self.tenant, self.kind, key)
            if rows:
                self._audit(conn, rows[-1][0], 'query_index_batch', actor_key, ['query_index'], stamp)
            else:
                mark_bootstrapped(conn, self.tenant, self.kind)
            conn.execute('UPDATE email_mailbox_query_migrations SET after_key=?,processed_count=processed_count+?,phase=?,updated_at=? '
                         'WHERE id=? AND tenant_key=? AND mailbox_kind=?',
                         (rows[-1][0] if rows else after_key, len(rows), 'BACKFILL' if rows else 'COMPLETED', stamp,
                          migration_id, self.tenant, self.kind))
            self._finish(conn)
            return {'processed': len(rows), 'after_key': rows[-1][0] if rows else after_key,
                    'done': not rows}
        except Exception:
            self._finish(conn, rollback=True)
            raise

    def retry_query_index_events(self, *, limit=50):
        """Consegna finita degli eventi SQL pendenti, mai dal percorso consultivo."""
        from pct.email_mailbox_query_events import AGGREGATE_PREFIX, EVENT_TYPE
        from pct.query_projection_worker import deliver_pending

        self._assert_initialized()
        conn = self._write_conn()
        def project(connection, key):
            row = connection.execute('UPDATE email_mailbox_records SET updated_at=updated_at '
                                     'WHERE tenant_key=? AND mailbox_kind=? AND message_key=? RETURNING payload_json',
                                     (self.tenant, self.kind, key)).fetchone()
            if row is None:
                delete_projection(connection, self.tenant, self.kind, key)
            else:
                upsert_projection(connection, self.tenant, self.kind, key, json.loads(row[0]))
        return deliver_pending(conn=conn, finish=self._finish, tenant=self.tenant,
                               aggregate=AGGREGATE_PREFIX + self.kind, event_type=EVENT_TYPE,
                               project=project, limit=limit)

    def load(self, *, update_original=True, message_keys=None):
        self._assert_initialized()
        params = [self.tenant, self.kind]
        restriction = ''
        if message_keys is not None:
            keys = list(dict.fromkeys(str(key) for key in message_keys))
            if len(keys) > 5000:
                raise ValueError('Selezione troppo ampia per la casella.')
            restriction = (' AND message_key IN (' + ','.join('?' for _ in keys) + ')') if keys else ' AND 1=0'
            params.extend(keys)
        records = {
            str(row[0]): json.loads(row[1])
            for row in self.db.conn.execute(
                'SELECT message_key,payload_json FROM email_mailbox_records WHERE tenant_key=? AND mailbox_kind=?' + restriction,
                tuple(params),
            ).fetchall()
        }
        _validate(records)
        if update_original:
            self.original = deepcopy(records)
        return records

    def save(self, records, *, actor_key='system', action='save', reload_records=True, required_folder=None):
        records = _validate(records)
        if self.original is None:
            raise RuntimeError('La modifica deve partire da una lettura SQL della casella.')
        conn = self._write_conn()
        try:
            stamp = datetime.now(timezone.utc).isoformat()
            for key in sorted(self.original.keys() | records.keys()):
                before, after = self.original.get(key), records.get(key)
                if before == after:
                    if required_folder:
                        # Blocca anche una riga già letta fino al commit: la
                        # selezione non può cambiare cartella durante il batch.
                        checked = conn.execute(
                            'UPDATE email_mailbox_records SET updated_at=updated_at '
                            'WHERE tenant_key=? AND mailbox_kind=? AND message_key=? '
                            'AND folder=? AND payload_json=? RETURNING message_key',
                            (self.tenant, self.kind, key, required_folder, _encode(before)),
                        ).fetchone()
                        if checked is None:
                            raise MailboxConflict('La selezione è cambiata. Ricarica la vista prima di riprovare.')
                    continue
                if before is None:
                    self._insert(conn, key, after, stamp)
                    self._audit(conn, key, action, actor_key, list(after), stamp)
                    continue
                row = conn.execute(
                    'SELECT payload_json FROM email_mailbox_records WHERE tenant_key=? AND mailbox_kind=? AND message_key=?',
                    (self.tenant, self.kind, key),
                ).fetchone()
                if row is None:
                    raise MailboxConflict('Il messaggio è stato modificato. Ricarica la casella.')
                current_raw, current = row[0], json.loads(row[0])
                if required_folder and current.get('cartella') != required_folder:
                    raise MailboxConflict('Un messaggio non è più nella posta in arrivo. Ricarica la vista.')
                if after is None:
                    if current != before:
                        raise MailboxConflict('Il messaggio è cambiato dopo la selezione. Nessuna eliminazione eseguita.')
                    changed = list(before)
                    result = conn.execute(
                        'DELETE FROM email_mailbox_records WHERE tenant_key=? AND mailbox_kind=? AND message_key=? '
                        'AND payload_json=? RETURNING message_key', (self.tenant, self.kind, key, current_raw),
                    ).fetchone()
                else:
                    changed = [field for field in before.keys() | after.keys()
                               if (field in before) != (field in after) or before.get(field) != after.get(field)]
                    if any((field in current) != (field in before) or current.get(field) != before.get(field) for field in changed):
                        raise MailboxConflict('Il messaggio è stato aggiornato da un’altra operazione. Ricarica prima di riprovare.')
                    merged = dict(current)
                    for field in changed:
                        if field in after:
                            merged[field] = after[field]
                        else:
                            merged.pop(field, None)
                    result = conn.execute(
                        'UPDATE email_mailbox_records SET folder=?,read_state=?,message_date=?,payload_json=?,updated_at=? '
                        'WHERE tenant_key=? AND mailbox_kind=? AND message_key=? AND payload_json=? RETURNING message_key',
                        (str(merged.get('cartella', 'INBOX')), str(merged.get('stato', 'NON_LETTA')),
                         str(merged.get('data', '')), _encode(merged), stamp, self.tenant, self.kind, key, current_raw),
                    ).fetchone()
                if result is None:
                    raise MailboxConflict('Aggiornamento concorrente della casella. Nessuna modifica parziale salvata.')
                if after is None:
                    delete_projection(conn, self.tenant, self.kind, key)
                else:
                    upsert_projection(conn, self.tenant, self.kind, key, merged)
                acknowledge_projection(conn, self.tenant, self.kind, key)
                self._audit(conn, key, action, actor_key, changed, stamp)
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        if reload_records:
            return self.load()
        self.original = None
        return None

    def mark_read(self, message_keys, *, actor_key, require_inbox=False):
        keys = list(dict.fromkeys(str(key) for key in message_keys))
        if not keys or len(keys) > 5000 or not actor_key:
            raise ValueError('Selezione o utente non validi per la lettura massiva.')
        records = self.load(message_keys=keys)
        if any(key not in records for key in keys):
            raise MailboxConflict('La selezione contiene messaggi non più presenti. Ricarica la vista.')
        if require_inbox and any(records[key].get('cartella') != 'INBOX' for key in keys):
            raise MailboxConflict('La selezione contiene messaggi non più nella posta in arrivo. Ricarica la vista.')
        stamp = datetime.now(timezone.utc).isoformat()
        changed = []
        for key in keys:
            row = records[key]
            if row.get('cartella') == 'INBOX' and row.get('stato') == 'NON_LETTA':
                row.update(stato='LETTA', letta_il=stamp)
                changed.append(key)
        self.save(records, actor_key=actor_key, action='mark_read', reload_records=False,
                  required_folder='INBOX' if require_inbox else None)
        return {'selected': len(keys), 'updated': len(changed), 'message_keys': changed}

    def export_mirror(self):
        if self.mirror_path is None:
            return
        self.mirror_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._write_conn()
        temporary = None
        try:
            # Serializza gli esportatori sulla casella, non sul file sostituito.
            # Un esportatore in attesa legge SQL solo dopo il precedente:
            # non può pubblicare una vecchia fotografia sopra una più recente.
            marker = conn.execute(
                'UPDATE email_mailbox_bootstrap SET initialized_at=initialized_at '
                'WHERE tenant_key=? AND mailbox_kind=? RETURNING tenant_key',
                (self.tenant, self.kind),
            ).fetchone()
            if marker is None:
                raise MailboxNotInitialized('Archivio della casella da riallineare: nessuna esportazione da copie storiche.')
            records = _validate({
                str(row[0]): json.loads(row[1])
                for row in conn.execute(
                    'SELECT message_key,payload_json FROM email_mailbox_records '
                    'WHERE tenant_key=? AND mailbox_kind=?',
                    (self.tenant, self.kind),
                ).fetchall()
            })
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.mirror_path.parent, delete=False) as stream:
                temporary = stream.name
                json.dump(records, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.mirror_path)
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
