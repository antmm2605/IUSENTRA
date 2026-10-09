"""Registro SQL tenant-aware: adozione esplicita, append e revisione concorrente.

Lo schema e l'adozione iniziale appartengono alla migrazione, non alle GET.
Il repository non legge né riscrive il JSON storico.
"""
from __future__ import annotations

import json
import hashlib
import math
from uuid import UUID
from datetime import datetime, timezone, timedelta

DDL = (
    """CREATE TABLE IF NOT EXISTS prima_nota_state (
        tenant_key TEXT PRIMARY KEY, revision BIGINT NOT NULL,
        source_sha256 TEXT NOT NULL, backup_reference TEXT NOT NULL,
        initialized_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS prima_nota_records (
        tenant_key TEXT NOT NULL, record_key TEXT NOT NULL,
        payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_key, record_key))""",
    """CREATE TABLE IF NOT EXISTS prima_nota_audit (
        tenant_key TEXT NOT NULL, revision BIGINT NOT NULL,
        record_key TEXT NOT NULL, actor_key TEXT NOT NULL,
        action TEXT NOT NULL, before_json TEXT NOT NULL,
        after_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY (tenant_key, revision, record_key))""",
    """CREATE TABLE IF NOT EXISTS prima_nota_commands (
        tenant_key TEXT NOT NULL, command_key TEXT NOT NULL,
        actor_key TEXT NOT NULL, operation TEXT NOT NULL,
        request_sha256 TEXT NOT NULL, result_json TEXT NOT NULL,
        committed_revision BIGINT, created_at TEXT NOT NULL,
        PRIMARY KEY (tenant_key, command_key))""",
)


class PrimaNotaConflict(ValueError):
    """Il registro è cambiato e una bozza obsoleta non può sostituirlo."""


def _encode(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_legacy_payload(raw):
    """Verifica la fonte prima dell'adozione, senza inventare id, date o importi."""
    from pct.prima_nota import CATEGORIE, METODI, MovimentoPrimaNota
    if not isinstance(raw, dict):
        raise ValueError("Registro storico non valido: atteso un insieme di movimenti.")
    result = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(value, dict) or value.get('id') != key:
            raise ValueError(f"Identificativo storico non coerente: {key}.")
        if set(value) - MovimentoPrimaNota.__dataclass_fields__.keys():
            raise ValueError(f"Campi storici non riconosciuti: {key}; nessun campo eliminato.")
        if any(not isinstance(item, str) for field, item in value.items() if field != 'importo'):
            raise ValueError(f"Campo testuale storico non valido: {key}.")
        if not value.get('creato_il') or not value.get('data'):
            raise ValueError(f"Data o tracciamento storico mancante: {key}.")
        try:
            parsed_date = datetime.strptime(value['data'], '%Y-%m-%d')
            if parsed_date.strftime('%Y-%m-%d') != value['data']:
                raise ValueError('Data non canonica')
            if isinstance(value['importo'], bool) or not isinstance(value['importo'], (int, float)):
                raise ValueError('Importo non numerico')
            amount = float(value['importo'])
            for timestamp in ('creato_il', 'riconciliato_il'):
                text = value.get(timestamp, '')
                if text and ('T' not in text or not datetime.fromisoformat(text)):
                    raise ValueError('Tracciamento non valido')
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Data o importo storico non valido: {key}.") from exc
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError(f"Importo storico non valido: {key}.")
        if value.get('categoria') not in CATEGORIE.get(value.get('tipo'), ()):
            raise ValueError(f"Tipo o categoria storica non validi: {key}.")
        if value.get('metodo', 'banca') not in METODI:
            raise ValueError(f"Metodo storico non valido: {key}.")
        if bool(value.get('riga_estratto_id')) != bool(value.get('riconciliato_il')):
            raise ValueError(f"Riconciliazione storica incompleta: {key}.")
        result[key] = MovimentoPrimaNota.from_dict(value).to_dict()
    bank_rows, reversed_ids, parcels = set(), set(), set()
    for key, value in result.items():
        reverse = value.get('storno_di', '')
        # Recupera solo il collegamento esplicitamente scritto nel formato storico nativo.
        if not reverse and str(value.get('note', '')).lower().startswith('storno di '):
            reverse = str(value['note'])[10:].split(':', 1)[0].strip()
            value['storno_di'] = reverse
        if reverse:
            original = result.get(reverse)
            if (not original or reverse == key or reverse in reversed_ids or original.get('storno_di')
                    or str(original.get('note', '')).lower().startswith('storno di ')
                    or original['tipo'] == value['tipo'] or original['importo'] != value['importo']):
                raise ValueError(f"Storno storico non riscontrato o duplicato: {key}.")
            reversed_ids.add(reverse)
        bank = value.get('riga_estratto_id', '')
        if bank:
            if bank in bank_rows or not value.get('riconciliato_il'):
                raise ValueError(f"Riga bancaria storica duplicata o senza conferma: {key}.")
            bank_rows.add(bank)
        parcel = value.get('parcella_id', '')
        if parcel and value['tipo'] == 'INCASSO' and not reverse:
            if parcel in parcels:
                raise ValueError(f"Incasso storico della parcella duplicato: {key}.")
            parcels.add(parcel)
    return result


class PrimaNotaRepository:
    def __init__(self, studio_db, tenant_key: str, *, actor_key: str = ""):
        if not str(tenant_key).strip():
            raise ValueError("Contesto studio mancante per la prima nota.")
        self.db = studio_db
        self.tenant = str(tenant_key)
        self.actor_key = str(actor_key).strip()
        self.revision = None
        self.original = {}
        self.last_command_replayed = False

    def _validate_command(self, command):
        if not self.actor_key:
            raise ValueError('Attore del comando Prima nota mancante.')
        try:
            key = command['key']
            if str(UUID(key)) != key:
                raise ValueError('Identificativo non canonico')
            sha = command['request_sha256']
            if len(sha) != 64 or any(char not in '0123456789abcdef' for char in sha):
                raise ValueError('Impronta non valida')
            if command['operation'] != 'registrazione':
                raise ValueError('Operazione non supportata')
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise ValueError('Identificativo o impronta del comando Prima nota non validi.') from exc

    def _command_result(self, row, command):
        if row is None:
            raise RuntimeError('Conferma persistente del comando Prima nota assente.')
        if row[0] != self.actor_key or row[1] != command['operation'] or row[2] != command['request_sha256']:
            raise PrimaNotaConflict('Identificativo del comando già usato per dati o operatore differenti.')
        if not isinstance(row[4], int) or row[4] < 1:
            raise RuntimeError('Comando Prima nota senza conferma persistente: recupero necessario.')
        result = json.loads(row[3])
        if not isinstance(result, dict) or set(result) != {'movement'} or not isinstance(result['movement'], dict):
            raise RuntimeError('Esito archiviato del comando Prima nota non valido.')
        movement = result['movement']
        validate_legacy_payload({movement.get('id'): movement})
        record = self.db.conn.execute('SELECT payload_json FROM prima_nota_records WHERE tenant_key=? AND record_key=?',
                                      (self.tenant, movement['id'])).fetchone()
        audit = self.db.conn.execute(
            'SELECT actor_key,action,before_json,after_json,created_at FROM prima_nota_audit WHERE tenant_key=? AND revision=? AND record_key=?',
            (self.tenant, row[4], movement['id']),
        ).fetchone()
        if record is None or audit is None or tuple(audit[index] for index in range(4)) != (self.actor_key, 'registrazione', '{}', _encode(movement)):
            raise RuntimeError('Movimento o audit del comando Prima nota non riscontrati: recupero necessario.')
        self._verify_audit_delivery(self.db.conn, self._audit_delivery_event(
            revision=row[4], key=movement['id'], action='registrazione',
            before='{}', after=_encode(movement), stamp=audit[4],
        ))
        stored = json.loads(record[0])
        if any(stored.get(field) != value for field, value in movement.items() if field not in {'riconciliato_il', 'riga_estratto_id'}):
            raise RuntimeError('Movimento del comando Prima nota discordante: recupero necessario.')
        return result

    def command_replay(self, command):
        self._validate_command(command)
        row = self.db.conn.execute(
            'SELECT actor_key,operation,request_sha256,result_json,committed_revision '
            'FROM prima_nota_commands WHERE tenant_key=? AND command_key=?',
            (self.tenant, command['key']),
        ).fetchone()
        return self._command_result(row, command) if row is not None else None

    def _write_conn(self):
        writable = getattr(self.db, "_conn_per_scrittura", None)
        return writable() if callable(writable) else self.db.conn

    def _finish(self, conn, *, rollback=False):
        target = getattr(self.db, "raw_conn", None)
        if target is None:
            target = conn
        target.rollback() if rollback else target.commit()

    def _audit_delivery_event(self, *, revision, key, action, before, after, stamp):
        from pct.transactional_outbox import OutboxEvent
        identity = _encode([self.tenant, int(revision), key, action])
        delivery_key = 'prima-nota-audit:' + hashlib.sha256(identity.encode('utf-8')).hexdigest()
        return OutboxEvent(
            tenant_id=self.tenant, aggregate_type='prima_nota', aggregate_id=key,
            aggregate_version=int(revision), event_type='prima_nota.audit_requested',
            idempotency_key=delivery_key, actor_id=self.actor_key,
            payload={'action': action, 'before': json.loads(before), 'after': json.loads(after),
                     'recorded_at': stamp},
        )

    def _verify_audit_delivery(self, conn, event):
        row = conn.execute(
            'SELECT tenant_id,aggregate_type,aggregate_id,aggregate_version,event_type,actor_id,payload_json '
            'FROM transactional_outbox WHERE idempotency_key=?', (event.idempotency_key,),
        ).fetchone()
        expected = (event.tenant_id, event.aggregate_type, event.aggregate_id,
                    event.aggregate_version, event.event_type, event.actor_id)
        if row is None or tuple(row[index] for index in range(6)) != expected or _encode(json.loads(row[6])) != _encode(event.payload):
            raise RuntimeError('Richiesta di audit Prima nota non riscontrata: recupero necessario.')

    def deliver_audit(self, *, record_key=None, limit=50, event_id=None):
        """Append e conferma nella stessa transazione SQL, nessun invio esterno.

        Il retry usa l'ID dell'evento; eventi elaborati rimangono conservati
        e possono essere riscontrati puntualmente senza scansioni storiche.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Lotto audit non valido.')
        conn = self._write_conn()
        try:
            params = [self.tenant]
            condition = "AND status='PENDING' AND available_at<=?"
            params.append(datetime.now(timezone.utc).isoformat())
            if event_id is not None:
                condition += ' AND id=?'
                params.append(event_id)
            if record_key is not None:
                condition = 'AND aggregate_id=?'
                params = [self.tenant,record_key]
            rows = conn.execute(
                "SELECT id,aggregate_id,aggregate_version,actor_id,payload_json FROM transactional_outbox "
                "WHERE tenant_id=? AND aggregate_type='prima_nota' AND event_type='prima_nota.audit_requested' "
                + condition + ' ORDER BY created_at,id LIMIT ?', tuple(params + [limit + 1]),
            ).fetchall()
            if record_key is not None and not rows:
                raise RuntimeError('Consegna audit del movimento assente: recupero necessario.')
            if len(rows) > limit and record_key is not None:
                raise RuntimeError('Lotto audit da riprendere prima della conferma.')
            rows = rows[:limit]
            for row in rows:
                event_id, key, revision, actor, encoded_payload = tuple(row[i] for i in range(5))
                payload = json.loads(encoded_payload)
                audit = conn.execute(
                    'SELECT actor_key,action,before_json,after_json,created_at FROM prima_nota_audit '
                    'WHERE tenant_key=? AND revision=? AND record_key=?', (self.tenant,revision,key),
                ).fetchone()
                if audit is None or actor != audit[0] or payload != {
                        'action': audit[1], 'before': json.loads(audit[2]),
                        'after': json.loads(audit[3]), 'recorded_at': audit[4]}:
                    raise RuntimeError('Fonte della consegna audit discordante: recupero necessario.')
                action = 'prima_nota.registrato' if audit[1] == 'registrazione' else 'prima_nota.riconciliato'
                from pct.pagamenti_giustizia import format_importo_euro_it
                movement = payload['after']
                username = movement.get('creato_da', '') if audit[1] == 'registrazione' else actor
                details = f"{movement['tipo']} {format_importo_euro_it(movement['importo'])}"
                values = (event_id, audit[4], actor, username, action, 'prima_nota', key, details, '', 'OK')
                conn.execute(
                    'INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) '
                    'VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING', values,
                )
                persisted = conn.execute(
                    'SELECT id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito '
                    'FROM audit_log WHERE id=?', (event_id,),
                ).fetchone()
                if persisted is None or tuple(persisted[i] for i in range(10)) != values:
                    raise RuntimeError('Audit generale discordante: consegna non confermata.')
                conn.execute("UPDATE transactional_outbox SET status='PROCESSED',processed_at=?,last_error=NULL "
                             "WHERE id=? AND tenant_id=? AND status='PENDING'", (datetime.now(timezone.utc).isoformat(),event_id,self.tenant))
            self._finish(conn)
            return len(rows)
        except Exception:
            self._finish(conn,rollback=True)
            raise

    def retry_pending_audit(self, *, limit=50):
        """Lotto finito, errori isolati e retry con attesa persistente."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Lotto audit non valido.')
        conn = self._write_conn()
        rows = conn.execute(
            "SELECT id,attempts FROM transactional_outbox WHERE tenant_id=? "
            "AND aggregate_type='prima_nota' AND event_type='prima_nota.audit_requested' "
            "AND status='PENDING' AND available_at<=? ORDER BY available_at,id LIMIT ?",
            (self.tenant,datetime.now(timezone.utc).isoformat(),limit),
        ).fetchall()
        self._finish(conn)
        delivered, failed = 0, 0
        for row in rows:
            try:
                delivered += self.deliver_audit(event_id=row[0],limit=1)
            except Exception:
                failed += 1
                attempts = int(row[1]) + 1
                available = datetime.now(timezone.utc) + timedelta(seconds=min(3600,60*2**min(attempts,6)))
                conn.execute("UPDATE transactional_outbox SET attempts=attempts+1,available_at=?,last_error=? "
                             "WHERE id=? AND tenant_id=? AND status='PENDING'",
                             (available.isoformat(),'Consegna audit non confermata: recupero necessario.',row[0],self.tenant))
                self._finish(conn)
        return {'delivered':delivered,'failed':failed}

    def ensure_schema(self):
        conn = self._write_conn()
        try:
            for statement in DDL:
                conn.execute(statement)
            from pct.transactional_outbox import SQLITE_SCHEMA
            # Stesso schema condiviso, solo nella migrazione esplicita; niente executescript/commit implicito.
            for statement in SQLITE_SCHEMA.split(';'):
                if statement.strip():
                    conn.execute(statement)
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise

    def initialize(self, payload, *, source_sha256: str, backup_reference: str):
        """Adozione esplicita dopo backup; ripetizioni non riimportano il mirror."""
        payload = validate_legacy_payload(payload)
        encoded = {key: _encode(value) for key, value in payload.items()}
        if len(source_sha256) != 64 or any(ch not in '0123456789abcdef' for ch in source_sha256):
            raise ValueError("Impronta della fonte mancante o non valida.")
        if not str(backup_reference).strip():
            raise ValueError("Riferimento al backup mancante.")
        conn = self._write_conn()
        try:
            stamp = datetime.now(timezone.utc).isoformat()
            inserted = conn.execute(
                "INSERT INTO prima_nota_state "
                "(tenant_key,revision,source_sha256,backup_reference,initialized_at) "
                "VALUES (?,0,?,?,?) ON CONFLICT (tenant_key) DO NOTHING RETURNING tenant_key",
                (self.tenant, source_sha256, backup_reference, stamp),
            ).fetchone()
            if inserted is not None:
                for key, value in encoded.items():
                    conn.execute(
                        "INSERT INTO prima_nota_records (tenant_key,record_key,payload_json,updated_at) "
                        "VALUES (?,?,?,?)", (self.tenant, key, value, stamp),
                    )
                conn.execute(
                    'INSERT INTO prima_nota_audit (tenant_key,revision,record_key,actor_key,action,before_json,after_json,created_at) '
                    'VALUES (?,0,?,?,?,?,?,?)',
                    (self.tenant,'__adoption',self.actor_key or 'migrazione-prima-nota','adozione','{}',
                     _encode({'source_sha256':source_sha256,'backup_reference':str(backup_reference),'records':len(encoded)}),stamp),
                )
            else:
                state = conn.execute('SELECT source_sha256,backup_reference FROM prima_nota_state WHERE tenant_key=?',(self.tenant,)).fetchone()
                if state is None or state[0] != source_sha256 or state[1] != str(backup_reference):
                    raise RuntimeError('Adozione esistente discordante da fonte o backup: recupero necessario.')
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        return self.load()

    def load(self):
        # Una sola SELECT: la revisione e i movimenti appartengono allo stesso snapshot.
        rows = self.db.conn.execute(
            "SELECT s.revision,r.record_key,r.payload_json FROM prima_nota_state s "
            "LEFT JOIN prima_nota_records r ON r.tenant_key=s.tenant_key "
            "WHERE s.tenant_key=?", (self.tenant,),
        ).fetchall()
        if not rows:
            raise ValueError("Prima nota SQL non inizializzata: recupero dell'archivio necessario.")
        payload = {str(row[1]): json.loads(row[2]) for row in rows if row[1] is not None}
        payload = validate_legacy_payload(payload)
        self.revision = int(rows[0][0])
        self.original = {key: _encode(value) for key, value in payload.items()}
        return payload

    def save(self, payload, *, command=None):
        self.last_command_replayed = False
        if self.revision is None:
            raise ValueError("Leggi il registro SQL prima di modificarlo.")
        payload = validate_legacy_payload(payload)
        encoded = {key: _encode(value) for key, value in payload.items()}
        if self.original.keys() - encoded.keys():
            raise ValueError("I movimenti non possono essere eliminati: usa lo storno.")
        changes = {key: value for key, value in encoded.items() if self.original.get(key) != value}
        for key in self.original.keys() & changes.keys():
            before, after = json.loads(self.original[key]), payload[key]
            for field in before.keys() | after.keys():
                if field not in {'riconciliato_il', 'riga_estratto_id'} and before.get(field) != after.get(field):
                    raise ValueError("Il movimento originale non può essere riscritto: usa lo storno.")
        if not changes:
            if command is not None:
                raise ValueError('Comando Prima nota privo di una nuova registrazione.')
            return
        if not self.actor_key:
            raise ValueError("Attore della scrittura Prima nota mancante: comando non registrato.")
        conn = self._write_conn()
        try:
            stamp = datetime.now(timezone.utc).isoformat()
            if command is not None:
                self._validate_command(command)
                result = command.get('result')
                if not isinstance(result, dict) or set(result) != {'movement'} or not isinstance(result['movement'], dict):
                    raise ValueError('Esito del comando Prima nota non valido.')
                movement = result['movement']
                key = movement.get('id')
                if not isinstance(key, str) or set(changes) != {key} or key in self.original or changes[key] != _encode(movement):
                    raise ValueError('Esito del comando discordante dal movimento registrato.')
                result_json = _encode(command['result'])
                # La prenotazione si conferma insieme al movimento e al suo audit.
                inserted = conn.execute(
                    'INSERT INTO prima_nota_commands '
                    '(tenant_key,command_key,actor_key,operation,request_sha256,result_json,committed_revision,created_at) '
                    'VALUES (?,?,?,?,?,?,NULL,?) ON CONFLICT (tenant_key,command_key) DO NOTHING RETURNING command_key',
                    (self.tenant, command['key'], self.actor_key, command['operation'], command['request_sha256'], result_json, stamp),
                ).fetchone()
                if inserted is None:
                    row = conn.execute(
                        'SELECT actor_key,operation,request_sha256,result_json,committed_revision '
                        'FROM prima_nota_commands WHERE tenant_key=? AND command_key=?', (self.tenant, command['key']),
                    ).fetchone()
                    result = self._command_result(row, command)
                    self._finish(conn, rollback=True)
                    self.last_command_replayed = True
                    return result
            updated = conn.execute(
                "UPDATE prima_nota_state SET revision=revision+1 WHERE tenant_key=? "
                "AND revision=? RETURNING revision", (self.tenant, self.revision),
            ).fetchone()
            if updated is None:
                raise PrimaNotaConflict("Prima nota aggiornata da un altro utente. La bozza non è stata registrata; ricarica il registro.")
            for key, value in changes.items():
                conn.execute(
                    "INSERT INTO prima_nota_records (tenant_key,record_key,payload_json,updated_at) "
                    "VALUES (?,?,?,?) ON CONFLICT (tenant_key,record_key) "
                    "DO UPDATE SET payload_json=excluded.payload_json,updated_at=excluded.updated_at",
                    (self.tenant, key, value, stamp),
                )
                conn.execute(
                    "INSERT INTO prima_nota_audit "
                    "(tenant_key,revision,record_key,actor_key,action,before_json,after_json,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (self.tenant, int(updated[0]), key, self.actor_key,
                     'riconciliazione' if key in self.original else 'registrazione',
                     self.original.get(key, '{}'), value, stamp),
                )
                from pct.transactional_outbox import enqueue
                delivery = self._audit_delivery_event(
                    revision=int(updated[0]), key=key,
                    action='riconciliazione' if key in self.original else 'registrazione',
                    before=self.original.get(key, '{}'), after=value, stamp=stamp,
                )
                enqueue(conn, delivery)
                self._verify_audit_delivery(conn, delivery)
            if command is not None:
                conn.execute('UPDATE prima_nota_commands SET committed_revision=? WHERE tenant_key=? AND command_key=?',
                             (int(updated[0]), self.tenant, command['key']))
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        self.revision = int(updated[0])
        self.original = encoded
        if command is not None:
            return command['result']
