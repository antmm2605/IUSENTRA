"""Collegamenti SQL tra parcella e movimenti nativi di Prima nota.

Lo schema appartiene alla migrazione esplicita. Nessuna GET inizializza dati
o ricostruisce pagamenti dallo stato corrente della parcella.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from pct.fatturazione import Parcella, StatoParcella, GestioneFatturazione, parcella_revision, _write_parcella_row
from pct.prima_nota import MovimentoPrimaNota, METODI
from pct.prima_nota_repository import PrimaNotaRepository, PrimaNotaConflict, _encode, validate_legacy_payload
from pct.parcella_incassi_proofs import _cents, _cash_sha, verified_receipt, install_proof_guards


class ParcellaIncassoConflict(ValueError):
    """Il comando non può confermare un incasso sulla versione superata."""


class ParcellaIncassoOutcomeUnconfirmed(RuntimeError):
    """La conferma va recuperata con lo stesso comando, senza duplicarlo."""


class ParcellaIncassoCommandConflict(ParcellaIncassoConflict):
    """Il comando esiste per un intento differente: non autorizzare retry ciechi."""


DDL = (
    """CREATE TABLE IF NOT EXISTS parcella_incassi_state (
        tenant_key TEXT NOT NULL, parcella_id TEXT NOT NULL,
        revision BIGINT NOT NULL, source_revision TEXT NOT NULL,
        original_json TEXT NOT NULL, due_cents BIGINT NOT NULL CHECK(due_cents>=0), created_at TEXT NOT NULL,
        PRIMARY KEY(tenant_key, parcella_id),
        FOREIGN KEY(parcella_id) REFERENCES parcelle(id))""",
    """CREATE TABLE IF NOT EXISTS parcella_incassi_proofs (
        tenant_key TEXT NOT NULL, movement_id TEXT NOT NULL,
        parcella_id TEXT NOT NULL, command_key TEXT NOT NULL,
        amount_cents BIGINT NOT NULL CHECK(amount_cents>0),
        direction INTEGER NOT NULL CHECK(direction IN (-1,1)),
        paid_on TEXT NOT NULL, cash_sha256 TEXT NOT NULL,
        reverses_movement_id TEXT, created_at TEXT NOT NULL,
        PRIMARY KEY(tenant_key,movement_id),
        UNIQUE(tenant_key,command_key),
        UNIQUE(tenant_key,reverses_movement_id),
        FOREIGN KEY(tenant_key,movement_id) REFERENCES prima_nota_records(tenant_key,record_key),
        FOREIGN KEY(tenant_key,command_key) REFERENCES prima_nota_commands(tenant_key,command_key),
        FOREIGN KEY(tenant_key,parcella_id) REFERENCES parcella_incassi_state(tenant_key,parcella_id),
        FOREIGN KEY(tenant_key,reverses_movement_id) REFERENCES parcella_incassi_proofs(tenant_key,movement_id))""",
    "CREATE INDEX IF NOT EXISTS idx_parcella_incassi_balance ON parcella_incassi_proofs(tenant_key,parcella_id)",
    "CREATE INDEX IF NOT EXISTS idx_parcella_incassi_period ON parcella_incassi_proofs(tenant_key,paid_on,parcella_id)",
)


def verified_installment_keys(db, tenant, payload):
    """Riscontro delle sole ricevute che richiedono la regola multi-incasso."""
    conn = db.conn
    postgres = getattr(db, 'backend_kind', '') == 'postgresql' or hasattr(db, 'raw_conn')
    if postgres:
        present = conn.execute("SELECT to_regclass('parcella_incassi_proofs')").fetchone()[0]
    else:
        present = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='parcella_incassi_proofs'").fetchone()
    if not present:
        return frozenset()
    keys = list(payload)
    if not keys:
        return frozenset()
    found = set()
    # I parametri rispettano anche il limite SQLite: nessuna query costruita
    # con identificativi provenienti dal contenuto del documento.
    for start in range(0, len(keys), 400):
        page = keys[start:start + 400]
        rows = conn.execute(
            'SELECT movement_id,parcella_id,amount_cents,direction,cash_sha256 '
            'FROM parcella_incassi_proofs WHERE tenant_key=? AND movement_id IN ('
            + ','.join('?' for _ in page) + ')', (tenant, *page),
        ).fetchall()
        for row in rows:
            movement = payload[row[0]]
            if (movement.get('parcella_id') != row[1]
                    or _cents(movement.get('importo')) != int(row[2])
                    or (1 if movement.get('tipo') == 'INCASSO' else -1) != int(row[3])
                    or _cash_sha(movement) != row[4]):
                raise ValueError('Collegamento incasso discordante dal movimento di Prima nota.')
            found.add(row[0])
    return frozenset(found)


def guard_linked_receipt_reversals(db, tenant, changes):
    """Uno storno generico non può lasciare invariato il saldo della fattura."""
    sources = {value.get('storno_di') for value in changes.values() if value.get('storno_di')}
    if not sources:
        return
    conn = db.conn
    postgres = getattr(db, 'backend_kind', '') == 'postgresql'
    present = (conn.execute("SELECT to_regclass('parcella_incassi_proofs')").fetchone()[0] if postgres else
        conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='parcella_incassi_proofs'").fetchone())
    if not present:
        return
    ordered = sorted(sources)
    for offset in range(0, len(ordered), 400):
        page = ordered[offset:offset + 400]
        linked = conn.execute('SELECT 1 FROM parcella_incassi_proofs WHERE tenant_key=? AND movement_id IN ('
            + ','.join('?' for _ in page) + ') LIMIT 1', (tenant, *page)).fetchone()
        if linked:
            raise ValueError('Incasso collegato alla fattura: lo storno deve aggiornare insieme il documento e la Prima nota.')


class ParcellaIncassiRepository:
    def __init__(self, studio_db, tenant_key, *, actor_key):
        self.db = studio_db
        self.tenant = str(tenant_key or '').strip()
        self.actor = str(actor_key or '').strip()
        if not self.tenant or not self.actor:
            raise ValueError('Studio e operatore richiesti per la registrazione degli incassi.')
        self.cash = PrimaNotaRepository(studio_db, self.tenant, actor_key=self.actor)
        self.postgres = getattr(studio_db, 'backend_kind', '') == 'postgresql'
        if self.db.conn.execute('SELECT 1 FROM prima_nota_state WHERE tenant_key=?', (self.tenant,)).fetchone() is None:
            raise ValueError('Prima nota SQL non adottata per questo studio.')

    def require_prepared(self):
        from pct.parcella_incassi_preparation import InvoiceReceiptsNotPrepared, require_preparation_record, require_live_signals, require_receipt_indexes
        if self.postgres:
            present = {row[0] for row in self.db.conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() "
                "AND table_name IN ('parcella_incassi_state','parcella_incassi_proofs')").fetchall()}
            columns = {row[0] for row in self.db.conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() "
                "AND table_name='parcella_incassi_state'").fetchall()}
        else:
            present = {row[0] for row in self.db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('parcella_incassi_state','parcella_incassi_proofs')").fetchall()}
            columns = {row[1] for row in self.db.conn.execute('PRAGMA table_info(parcella_incassi_state)').fetchall()}
        if present != {'parcella_incassi_state', 'parcella_incassi_proofs'} or 'due_cents' not in columns:
            raise InvoiceReceiptsNotPrepared('Collegamenti degli incassi non preparati: eseguire la preparazione SQL governata.')
        require_preparation_record(self.db, self.tenant)
        require_live_signals(self.db)
        require_receipt_indexes(self.db)

    def ensure_schema(self):
        """Solo migrazione esplicita, dopo backup e adozione di Prima nota."""
        conn = self.cash._write_conn()
        try:
            if conn.execute('SELECT 1 FROM prima_nota_state WHERE tenant_key=?', (self.tenant,)).fetchone() is None:
                raise ValueError('Prima nota SQL non adottata per questo studio.')
            for statement in DDL:
                conn.execute(statement)
            install_proof_guards(conn, postgres=self.postgres)
            expression = "(payload_json::jsonb->>'parcella_id')" if self.postgres else "json_extract(payload_json,'$.parcella_id')"
            conn.execute('CREATE INDEX IF NOT EXISTS idx_prima_nota_invoice_source '
                         'ON prima_nota_records(tenant_key,' + expression + ')')
            self.cash._finish(conn)
        except Exception:
            self.cash._finish(conn, rollback=True)
            raise

    def _invoice(self, invoice_id, *, lock=False):
        row = self.db.conn.execute('SELECT dati_json,id_cliente,id_fascicolo FROM parcelle WHERE id=?'
                                  + (' FOR UPDATE' if self.postgres and lock else ''), (invoice_id,)).fetchone()
        if row is None:
            raise KeyError('Documento non trovato.')
        item = Parcella.from_dict(json.loads(row[0]))
        if (item.id != invoice_id or item.id_cliente != row[1]
                or (item.id_fascicolo or '') != (row[2] or '')):
            raise ValueError('Identità del documento SQL discordante.')
        return item

    def summary(self, invoice_id):
        result = self.summaries([invoice_id])
        if invoice_id not in result:
            raise KeyError('Documento non trovato.')
        return result[invoice_id]

    def summaries(self, invoice_ids):
        ids = list(dict.fromkeys(invoice_ids))
        if not ids:
            return {}
        if len(ids) > 400 or any(not isinstance(key, str) or not key for key in ids):
            raise ValueError('Lotto di documenti non valido.')
        # Documento, revisione e movimenti appartengono allo stesso snapshot,
        # senza aprire una transazione di lettura dentro quella di scrittura.
        expression = "(legacy.payload_json::jsonb->>'parcella_id')" if self.postgres else "json_extract(legacy.payload_json,'$.parcella_id')"
        rows = self.db.conn.execute(
            'SELECT i.dati_json,s.original_json,s.revision,p.movement_id,p.amount_cents,p.direction,p.cash_sha256,c.payload_json,'
            'EXISTS(SELECT 1 FROM prima_nota_records legacy WHERE legacy.tenant_key=? AND ' + expression + '=i.id),s.due_cents,p.reverses_movement_id,i.id_cliente,i.id_fascicolo,i.id,p.paid_on '
            'FROM parcelle i LEFT JOIN parcella_incassi_state s ON s.parcella_id=i.id AND s.tenant_key=? '
            'LEFT JOIN parcella_incassi_proofs p ON p.tenant_key=s.tenant_key AND p.parcella_id=s.parcella_id '
            'LEFT JOIN prima_nota_records c ON c.tenant_key=p.tenant_key AND c.record_key=p.movement_id '
            'WHERE i.id IN (' + ','.join('?' for _ in ids) + ')', (self.tenant, self.tenant, *ids)).fetchall()
        groups = {}
        for row in rows:
            groups.setdefault(row[13], []).append(row)
        return {key: self._summary_rows(key, group) for key, group in groups.items()}

    def _summary_rows(self, invoice_id, rows):
        item = Parcella.from_dict(json.loads(rows[0][0]))
        if (item.id != invoice_id or item.id_cliente != rows[0][11]
                or (item.id_fascicolo or '') != (rows[0][12] or '')):
            raise ValueError('Identità del documento SQL discordante.')
        identity = {'invoice_state': item.stato.value, 'is_proforma': GestioneFatturazione._is_proforma(item)}
        managed = rows[0][1] is not None
        if not managed and (item.stato == StatoParcella.PAGATA or item.data_pagamento or rows[0][8]):
            return {**identity, 'invoice_id': invoice_id, 'paid_cents': None, 'residual_cents': None,
                    'status': 'REVIEW', 'revision': parcella_revision(item),
                    'reason': 'Pagamento storico da riscontrare, senza ricostruire un importo dal totale corrente.',
                    'receipts': [], 'due_cents': None}
        if not managed and item.stato == StatoParcella.BOZZA:
            return {**identity, 'invoice_id': invoice_id, 'paid_cents': 0, 'residual_cents': 0,
                    'status': 'DRAFT', 'revision': parcella_revision(item), 'receipts': [],
                    'due_cents': _cents(item.netto_a_pagare),
                    'reason': 'Bozza non emessa: completa il documento prima di registrarne gli incassi.'}
        paid = 0
        receipts = []
        for row in rows:
            if row[3] is None:
                continue
            receipt = verified_receipt(invoice_id, row[3], row[4], row[5], row[6], row[7], row[10], row[14])
            paid += int(row[4]) * int(row[5])
            receipts.append(receipt)
        reversed_ids = {entry['reverses_movement_id'] for entry in receipts if entry['reverses_movement_id']}
        for entry in receipts:
            entry['reversed'] = entry['movement_id'] in reversed_ids
        receipts.sort(key=lambda entry: (entry['paid_on'], entry['movement_id']))
        if managed:
            original = Parcella.from_dict(json.loads(rows[0][1]))
            marker = (item.dati_personalizzati or {}).get('incassi_sql', {})
            if (self._financial_identity(item) != self._financial_identity(original)
                    or _cents(item.netto_a_pagare) != int(rows[0][9])
                    or not isinstance(marker, dict) or marker.get('owner') != 'prima_nota'
                    or marker.get('revision') != int(rows[0][2])):
                return {**identity, 'invoice_id': invoice_id, 'paid_cents': paid, 'residual_cents': None,
                        'status': 'REVIEW', 'revision': parcella_revision(item),
                        'reason': 'Dati economici modificati dopo gli incassi: riconciliazione necessaria.',
                        'receipts': receipts, 'due_cents': int(rows[0][9])}
        due = _cents(item.netto_a_pagare)
        if paid < 0 or paid > due:
            raise ValueError('Saldo incassi discordante: verifica della fonte necessaria.')
        if item.stato == StatoParcella.ANNULLATA:
            return {**identity, 'invoice_id': invoice_id, 'paid_cents': paid,
                'residual_cents': None if paid else 0, 'due_cents': due,
                'status': 'REVIEW' if paid else 'CANCELLED', 'revision': parcella_revision(item),
                'receipts': receipts, 'reason': 'Documento annullato: verifica o storna gli incassi ancora presenti.' if paid else ''}
        return {**identity, 'invoice_id': invoice_id, 'paid_cents': paid, 'residual_cents': due - paid,
                'status': 'PAID' if paid == due and due else 'PARTIAL' if paid else 'OPEN',
                'revision': parcella_revision(item), 'receipts': receipts, 'due_cents': due}

    @staticmethod
    def _financial_identity(item):
        payload = item.to_dict()
        for key in ('stato', 'data_pagamento', 'metodo_pagamento', 'note'):
            payload.pop(key, None)
        custom = dict(payload.get('dati_personalizzati') or {})
        custom.pop('incassi_sql', None)
        payload['dati_personalizzati'] = custom
        return _encode(payload)

    def _command(self, fields, command_key):
        if not isinstance(command_key, str) or str(UUID(command_key)) != command_key:
            raise ValueError('Identificativo del comando non valido.')
        return {'key': command_key, 'operation': 'registrazione',
                'request_sha256': hashlib.sha256(_encode(fields).encode('utf-8')).hexdigest()}

    def command_exists(self, command_key):
        try:
            if not isinstance(command_key, str) or str(UUID(command_key)) != command_key:
                return False
        except ValueError:
            return False
        return self.db.conn.execute('SELECT 1 FROM prima_nota_commands WHERE tenant_key=? AND command_key=?',
                                    (self.tenant, command_key)).fetchone() is not None

    def _result(self, invoice_id, movement_id, *, already_present=False):
        try:
            proof = self.db.conn.execute('SELECT parcella_id FROM parcella_incassi_proofs '
                                         'WHERE tenant_key=? AND movement_id=?',
                                         (self.tenant, movement_id)).fetchone()
            if proof is None or proof[0] != invoice_id:
                raise ValueError('Conferma incasso assente o riferita a un altro documento.')
            return {**self.summary(invoice_id), 'movement_id': movement_id,
                    'already_present': already_present}
        except Exception as exc:
            raise ParcellaIncassoOutcomeUnconfirmed('Conferma del movimento da recuperare con lo stesso comando.') from exc

    def _replay(self, command):
        try:
            return self.cash.command_replay(command)
        except PrimaNotaConflict as exc:
            raise ParcellaIncassoCommandConflict(str(exc)) from exc
        except Exception as exc:
            raise ParcellaIncassoOutcomeUnconfirmed('Conferma del comando non riscontrata: recupero necessario.') from exc

    def register(self, *, invoice_id, amount_cents, paid_on, method, note, command_key, expected_revision):
        if type(amount_cents) is not int or not 0 < amount_cents <= 9007199254740991:
            raise ValueError('Importo positivo in centesimi richiesto.')
        if _cents(amount_cents / 100) != amount_cents:
            raise ValueError('Importo non rappresentabile esattamente in centesimi nel registro nativo.')
        if not isinstance(note, str) or len(note) > 2000:
            raise ValueError('Nota del movimento non valida.')
        if method not in METODI:
            raise ValueError('Metodo di incasso non valido.')
        fields = {'kind': 'invoice_receipt', 'invoice_id': invoice_id, 'amount_cents': amount_cents,
                  'paid_on': paid_on, 'method': method, 'note': note, 'expected_revision': expected_revision}
        return self._execute(fields, command_key)

    def reverse(self, *, invoice_id, movement_id, paid_on, reason, command_key, expected_revision):
        if not isinstance(movement_id, str) or not re.fullmatch('[A-Za-z0-9_-]{1,100}', movement_id):
            raise ValueError('Riferimento del movimento non valido.')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise ValueError('Lo storno richiede il motivo.')
        fields = {'kind': 'invoice_receipt_reversal', 'invoice_id': invoice_id, 'movement_id': movement_id,
                  'paid_on': paid_on, 'reason': reason.strip(), 'expected_revision': expected_revision}
        return self._execute(fields, command_key)

    def _execute(self, fields, command_key):
        if not isinstance(fields['expected_revision'], str) or not re.fullmatch('[a-f0-9]{64}', fields['expected_revision']):
            raise ValueError('Rileggi il documento prima di registrare il movimento.')
        if not isinstance(fields['paid_on'], str) or date.fromisoformat(fields['paid_on']).isoformat() != fields['paid_on']:
            raise ValueError('Data del movimento non valida.')
        if date.fromisoformat(fields['paid_on']) > datetime.now(ZoneInfo('Europe/Rome')).date():
            raise ValueError('La data del movimento non può essere futura.')
        invoice_id = fields['invoice_id']
        command = self._command(fields, command_key)
        try:
            replay = self._replay(command)
            if replay is not None:
                return self._result(invoice_id, replay['movement']['id'], already_present=True)
            conn = self.cash._write_conn()
            if not self.postgres:
                if conn.in_transaction:
                    raise RuntimeError('Transazione estranea al comando incasso: nessuna scrittura eseguita.')
                conn.execute('BEGIN IMMEDIATE')
            try:
                item = self._invoice(invoice_id, lock=True)
                # Un comando identico può essersi confermato durante l'attesa
                # del lock. Il replay precede sempre il confronto di revisione.
                replay = self._replay(command)
                if replay is not None:
                    self.cash._finish(conn, rollback=True)
                    return self._result(invoice_id, replay['movement']['id'], already_present=True)
                if parcella_revision(item) != fields['expected_revision']:
                    raise ParcellaIncassoConflict('Documento aggiornato da un altro operatore. La bozza è conservata.')
                reversing = fields['kind'] == 'invoice_receipt_reversal'
                if not reversing and item.id_fascicolo:
                    case = conn.execute('SELECT id_cliente FROM fascicoli WHERE id=?'
                        + (' FOR SHARE' if self.postgres else ''), (item.id_fascicolo,)).fetchone()
                    if case is None or case[0] != item.id_cliente:
                        raise ValueError('Cliente del documento non concordante con il fascicolo: verifica il collegamento prima dell’incasso.')
                if not reversing and (GestioneFatturazione._is_proforma(item) or item.stato not in {StatoParcella.EMESSA, StatoParcella.SCADUTA, StatoParcella.PAGATA}):
                    raise ValueError('La procedura fiscale della proforma deve essere predisposta prima degli acconti.')
                balance = self.summary(invoice_id)
                if balance['status'] == 'REVIEW' and (not reversing or balance['paid_cents'] is None):
                    raise ParcellaIncassoConflict(balance['reason'])
                native_state = conn.execute('SELECT revision FROM prima_nota_state WHERE tenant_key=?'
                                            + (' FOR UPDATE' if self.postgres else ''), (self.tenant,)).fetchone()
                if native_state is None:
                    raise ValueError('Prima nota SQL non adottata per questo studio.')
                self.cash.revision = int(native_state[0])
                self.cash.original = {}
                state = conn.execute('SELECT revision,original_json,due_cents FROM parcella_incassi_state '
                                     'WHERE tenant_key=? AND parcella_id=?', (self.tenant, invoice_id)).fetchone()
                stamp = datetime.now(timezone.utc).isoformat()
                if state is None:
                    conn.execute('INSERT INTO parcella_incassi_state '
                                 '(tenant_key,parcella_id,revision,source_revision,original_json,due_cents,created_at) VALUES (?,?,0,?,?,?,?)',
                                 (self.tenant, invoice_id, fields['expected_revision'], _encode(item.to_dict()), _cents(item.netto_a_pagare), stamp))
                    revision = 0
                    frozen_due = _cents(item.netto_a_pagare)
                else:
                    revision = int(state[0])
                    frozen_due = int(state[2])
                    original = Parcella.from_dict(json.loads(state[1]))
                    if not reversing and self._financial_identity(item) != self._financial_identity(original):
                        raise ParcellaIncassoConflict('Dati economici modificati dopo gli incassi: riconciliazione necessaria.')
                reverse_id = None
                if fields['kind'] == 'invoice_receipt_reversal':
                    reverse_id = fields['movement_id']
                    original_row = conn.execute('SELECT p.amount_cents,p.direction,r.payload_json,p.cash_sha256 '
                                                'FROM parcella_incassi_proofs p JOIN prima_nota_records r '
                                                'ON r.tenant_key=p.tenant_key AND r.record_key=p.movement_id '
                                                'WHERE p.tenant_key=? AND p.parcella_id=? AND p.movement_id=?',
                                                (self.tenant, invoice_id, reverse_id)).fetchone()
                    if original_row is None or int(original_row[1]) != 1:
                        raise ValueError('Incasso originale non trovato per questo documento.')
                    if conn.execute('SELECT 1 FROM parcella_incassi_proofs WHERE tenant_key=? AND reverses_movement_id=?',
                                    (self.tenant, reverse_id)).fetchone():
                        raise ParcellaIncassoConflict('Incasso già stornato.')
                    source = json.loads(original_row[2])
                    if _cash_sha(source) != original_row[3]:
                        raise ValueError('Il movimento originale è discordante dalla prova di incasso.')
                    if fields['paid_on'] < source['data']:
                        raise ValueError('Lo storno non può precedere la data dell’incasso originale.')
                    cents = int(original_row[0])
                    movement = MovimentoPrimaNota(data=fields['paid_on'], tipo='PAGAMENTO', importo=cents / 100,
                        categoria='altri_pagamenti', controparte=source['controparte'], metodo=source['metodo'],
                        causale='Storno incasso ' + item.numero, note='Storno di ' + reverse_id + ': ' + fields['reason'],
                        parcella_id=item.id, fascicolo_id=item.id_fascicolo or '', cliente_id=item.id_cliente or '',
                        documento_riferimento=item.numero, creato_da=self.actor, storno_di=reverse_id)
                    direction = -1
                else:
                    cents = fields['amount_cents']
                    if cents > balance['residual_cents']:
                        raise ParcellaIncassoConflict('Importo superiore al residuo del documento.')
                    client_row = conn.execute('SELECT dati_json FROM clienti WHERE id=?', (item.id_cliente,)).fetchone()
                    if client_row is None:
                        raise ValueError('Cliente del documento non riscontrato nell’anagrafica SQL.')
                    client = json.loads(client_row[0]) if client_row and client_row[0] else {}
                    if client.get('id') not in (None, item.id_cliente):
                        raise ValueError('Identità del cliente SQL discordante dal documento.')
                    if item.id_fascicolo:
                        matter = conn.execute('SELECT id_cliente FROM fascicoli WHERE id=?', (item.id_fascicolo,)).fetchone()
                        if matter is None or matter[0] != item.id_cliente:
                            raise ValueError('Cliente e fascicolo del documento non concordanti nell’archivio SQL.')
                    label = client.get('ragione_sociale') or ' '.join(str(client.get(key) or '') for key in ('nome', 'cognome')).strip() or 'Cliente'
                    category = 'onorari' if all(voce.tipo == 'ONORARIO' for voce in item.voci) else 'altri_incassi'
                    movement = MovimentoPrimaNota(data=fields['paid_on'], tipo='INCASSO', importo=cents / 100,
                        categoria=category, controparte=label, metodo=fields['method'],
                        causale='Incasso fattura ' + item.numero, note=fields['note'],
                        parcella_id=item.id, fascicolo_id=item.id_fascicolo or '', cliente_id=item.id_cliente or '',
                        documento_riferimento=item.numero, creato_da=self.actor)
                    direction = 1
                validation = {movement.id: movement.to_dict()}
                if reverse_id:
                    validation[reverse_id] = source
                validate_legacy_payload(validation)
                command['result'] = {'movement': movement.to_dict()}
                _, result, replayed = self.cash._persist_changes(conn, {movement.id: _encode(movement.to_dict())}, command=command)
                if replayed:
                    self.cash._finish(conn, rollback=True)
                    return self._result(invoice_id, result['movement']['id'], already_present=True)
                conn.execute('INSERT INTO parcella_incassi_proofs '
                             '(tenant_key,movement_id,parcella_id,command_key,amount_cents,direction,paid_on,cash_sha256,reverses_movement_id,created_at) '
                             'VALUES (?,?,?,?,?,?,?,?,?,?)',
                             (self.tenant, movement.id, invoice_id, command_key, cents, direction, fields['paid_on'],
                              _cash_sha(movement.to_dict()), reverse_id, stamp))
                updated = conn.execute('UPDATE parcella_incassi_state SET revision=revision+1 '
                                       'WHERE tenant_key=? AND parcella_id=? AND revision=? RETURNING revision',
                                       (self.tenant, invoice_id, revision)).fetchone()
                if updated is None:
                    raise ParcellaIncassoConflict('Un altro incasso ha aggiornato il documento.')
                total_paid = balance['paid_cents'] + cents * direction
                due = frozen_due
                if not 0 <= total_paid <= due:
                    raise ParcellaIncassoConflict('Saldo discordante: il movimento non è stato registrato.')
                item.dati_personalizzati['incassi_sql'] = {'revision': int(updated[0]), 'owner': 'prima_nota'}
                if reversing and balance['status'] in {'REVIEW', 'CANCELLED'}:
                    # Lo storno corregge la cassa realmente provata, senza
                    # riemettere un documento annullato o riscriverne i valori.
                    pass
                elif total_paid == due:
                    item.stato = StatoParcella.PAGATA
                    item.data_pagamento = conn.execute('SELECT MAX(paid_on) FROM parcella_incassi_proofs p '
                        'WHERE tenant_key=? AND parcella_id=? AND direction=1 AND NOT EXISTS '
                        '(SELECT 1 FROM parcella_incassi_proofs reverse WHERE reverse.tenant_key=p.tenant_key AND reverse.reverses_movement_id=p.movement_id)',
                        (self.tenant, invoice_id)).fetchone()[0]
                else:
                    original_json = conn.execute('SELECT original_json FROM parcella_incassi_state WHERE tenant_key=? AND parcella_id=?',
                                                 (self.tenant, invoice_id)).fetchone()[0]
                    original = Parcella.from_dict(json.loads(original_json))
                    item.stato = item.stato if item.stato in {StatoParcella.EMESSA, StatoParcella.SCADUTA} else original.stato
                    item.data_pagamento = None
                _write_parcella_row(conn, item, expected_revision=fields['expected_revision'], postgres=self.postgres)
                self.cash._finish(conn)
            except Exception:
                self.cash._finish(conn, rollback=True)
                raise
            return self._result(invoice_id, movement.id)
        except PrimaNotaConflict as exc:
            raise ParcellaIncassoConflict(str(exc)) from exc
