"""Preparazioni SQL: adozione esplicita e comandi con effetti atomici.

Il costruttore e le letture non creano schema e non importano file. Gli
effetti partecipano alla transazione nativa, prima della conferma del comando.
Il collegamento alla UI e l'adozione sono ancora fasi distinte della consegna.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from pct.wizard_pro import ESITI, SessioneWizardPro

DDL = (
    """CREATE TABLE IF NOT EXISTS preparazioni_state (
        tenant_key TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL,
        backup_reference TEXT NOT NULL, initialized_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS preparazioni_sessions (
        tenant_key TEXT NOT NULL, session_key TEXT NOT NULL, fascicolo_id TEXT NOT NULL,
        appuntamento_id TEXT NOT NULL, revision BIGINT NOT NULL,
        payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(tenant_key,session_key))""",
    "CREATE INDEX IF NOT EXISTS idx_preparazioni_fascicolo ON preparazioni_sessions(tenant_key,fascicolo_id)",
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_preparazioni_appuntamento
        ON preparazioni_sessions(tenant_key,appuntamento_id) WHERE appuntamento_id<>''""",
    """CREATE TABLE IF NOT EXISTS preparazioni_commands (
        tenant_key TEXT NOT NULL, command_key TEXT NOT NULL, actor_key TEXT NOT NULL,
        session_key TEXT NOT NULL, operation TEXT NOT NULL, request_json TEXT NOT NULL,
        result_json TEXT NOT NULL, audit_id TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(tenant_key,command_key))""",
)


class PreparazioneConflict(ValueError):
    """La versione visibile è superata; nessun effetto viene confermato."""


class PreparazioneRejected(ValueError):
    """Il rifiuto dello stesso intento rimane persistente anche dopo un refresh."""
    def __init__(self, result):
        self.result = result
        super().__init__(result["message"])


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_record(raw):
    """Non eliminare silenziosamente campi o righe della fonte storica."""
    if not isinstance(raw, dict) or set(raw) - SessioneWizardPro.__dataclass_fields__.keys():
        raise ValueError("Campi della preparazione non riconosciuti: recupero necessario.")
    for key in ("id", "id_fascicolo", "titolo"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError("Identità della preparazione incompleta.")
    if raw.get("stato", "in_corso") not in {"in_corso", "completato", "archiviato"}:
        raise ValueError("Stato della preparazione non valido.")
    if raw.get("esito", "") and raw["esito"] not in dict(ESITI):
        raise ValueError("Esito della preparazione non valido.")
    if type(raw.get("step_corrente", 1)) is not int or not 1 <= raw.get("step_corrente", 1) <= 5:
        raise ValueError("Passo della preparazione non valido.")
    nested = {"checklist_documenti", "verifiche_tipo", "termini_assegnati"}
    flags = {key for key in SessioneWizardPro.__dataclass_fields__ if key.endswith("_confermato")
             or key.startswith("precheck_") and key != "precheck_note"} | {"esito_aggiorna_fascicolo"}
    for key, value in raw.items():
        if key in flags and type(value) is not bool:
            raise ValueError("Conferma della preparazione non valida.")
        if key not in flags | nested | {"step_corrente"} and not isinstance(value, str):
            raise ValueError("Campo testuale della preparazione non valido.")
    for key in ("checklist_documenti", "termini_assegnati"):
        if not isinstance(raw.get(key, []), list) or any(not isinstance(row, dict) for row in raw.get(key, [])):
            raise ValueError("Righe della preparazione non valide.")
    checks = raw.get("verifiche_tipo", {})
    if not isinstance(checks, dict) or any(not isinstance(k, str) or type(v) is not bool for k, v in checks.items()):
        raise ValueError("Verifiche della preparazione non valide.")
    for key in ("creato_il", "modificato_il", "completato_il"):
        if raw.get(key):
            datetime.fromisoformat(raw[key])
    if raw.get("esito_rinvio_data"):
        date.fromisoformat(raw["esito_rinvio_data"])
    encode(raw)
    return SessioneWizardPro.from_dict(raw).to_dict()


class PreparazioniRepository:
    def __init__(self, database, tenant, *, actor="", expected_adoption=None):
        if not isinstance(tenant, str) or not tenant.strip() or not isinstance(actor, str):
            raise ValueError("Studio o operatore della preparazione non valido.")
        self.db, self.tenant, self.actor = database, tenant, actor
        self.expected_adoption = expected_adoption
        self._reference_issues = None

    def ensure_schema(self):
        """Solo dalla procedura di migrazione esplicita con produttori drenati."""
        def install(conn, _):
            for statement in DDL:
                conn.execute(statement)
        self.db.salva_tabella("preparazioni_state", [None], install, delete_all=False)

    def _adoption(self, conn):
        row = conn.execute("SELECT source_sha256,backup_reference FROM preparazioni_state WHERE tenant_key=?", (self.tenant,)).fetchone()
        if row is None or self.expected_adoption is not None and tuple(row[i] for i in range(2)) != tuple(self.expected_adoption):
            raise RuntimeError("Preparazioni SQL non adottate o fonte discordante: recupero necessario.")
        return row

    def initialize(self, records, *, source_sha256, backup_reference, unresolved_references=None):
        if not isinstance(records, list):
            raise ValueError("Archivio delle preparazioni non valido.")
        validated = [validate_record(item) for item in records]
        unresolved = {} if unresolved_references is None else unresolved_references
        if (not isinstance(unresolved, dict) or set(unresolved) - {r["id"] for r in validated}
                or any(not isinstance(reason, str) or not reason.strip() for reason in unresolved.values())):
            raise ValueError("Riscontri dei collegamenti storici non validi.")
        if len({r["id"] for r in validated}) != len(validated):
            raise ValueError("Preparazioni duplicate nella fonte: nessuna riga eliminata.")
        hearings = [r["id_appuntamento"] for r in validated if r["id_appuntamento"]]
        if len(set(hearings)) != len(hearings):
            raise ValueError("Più preparazioni per la stessa udienza: riconciliazione necessaria.")
        if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
            raise ValueError("Impronta della fonte non valida.")
        if not isinstance(backup_reference, str) or not backup_reference.strip() or not self.actor:
            raise ValueError("Backup o operatore dell'adozione mancante.")
        stamp = datetime.now(timezone.utc).isoformat()
        def adopt(conn, _):
            inserted = conn.execute("INSERT INTO preparazioni_state VALUES (?,?,?,?) ON CONFLICT(tenant_key) DO NOTHING RETURNING tenant_key",
                                    (self.tenant, source_sha256, backup_reference, stamp)).fetchone()
            if inserted is None:
                existing = self._adoption(conn)
                if tuple(existing[i] for i in range(2)) != (source_sha256, backup_reference):
                    raise ValueError("Adozione delle preparazioni già presente con fonte diversa.")
                return
            for item in validated:
                conn.execute("INSERT INTO preparazioni_sessions VALUES (?,?,?,?,0,?,?)",
                             (self.tenant, item["id"], item["id_fascicolo"], item["id_appuntamento"], encode(item), stamp))
            after = {"records": len(validated), "source_sha256": source_sha256, "backup_reference": backup_reference}
            if unresolved:
                after["unresolved_references"] = unresolved
            self._audit(conn, "__adoption", "adozione", 0, {}, after, stamp)
        self.db.salva_tabella("preparazioni_state", [None], adopt, delete_all=False)
        self._reference_issues = None

    def list(self, *, fascicolo_id=None):
        self._adoption(self.db.conn)
        sql = "SELECT session_key,fascicolo_id,appuntamento_id,revision,payload_json FROM preparazioni_sessions WHERE tenant_key=?"
        args = (self.tenant,)
        if fascicolo_id is not None:
            sql += " AND fascicolo_id=?"
            args += (fascicolo_id,)
        return [self._read(row) for row in self.db.conn.execute(sql, args).fetchall()]

    def get(self, key, *, conn=None):
        conn = self.db.conn if conn is None else conn
        self._adoption(conn)
        row = conn.execute("SELECT session_key,fascicolo_id,appuntamento_id,revision,payload_json FROM preparazioni_sessions WHERE tenant_key=? AND session_key=?",
                           (self.tenant, key)).fetchone()
        return self._read(row) if row is not None else None

    def _read(self, row):
        record = validate_record(json.loads(row[4]))
        if (record["id"], record["id_fascicolo"], record["id_appuntamento"]) != tuple(row[i] for i in range(3)):
            raise RuntimeError("Identità SQL della preparazione discordante.")
        if self._reference_issues is None:
            adoption_audit = self.db.conn.execute(
                "SELECT dettagli FROM audit_log WHERE azione='udienza.adozione' AND risorsa_id='__adoption'").fetchall()
            self._reference_issues = {}
            for audit in adoption_audit:
                details = json.loads(audit[0])
                if details.get("tenant") == self.tenant:
                    self._reference_issues.update(details.get("after", {}).get("unresolved_references", {}))
        result = {"record": record, "revision": int(row[3])}
        if record["id"] in self._reference_issues:
            result["reference_issue"] = self._reference_issues[record["id"]]
        return result

    def _audit(self, conn, key, operation, revision, before, after, stamp, *, command_key=""):
        if not self.actor:
            raise ValueError("Operatore della preparazione mancante.")
        identifier = str(uuid5(NAMESPACE_URL, encode(["preparazione", self.tenant, key, revision, operation, command_key])))
        values = (identifier, stamp, self.actor, self.actor, f"udienza.{operation}", "preparazione_udienza", key,
                  encode({"tenant": self.tenant, "revision": revision, "before": before, "after": after}), "",
                  "RIFIUTATO" if after.get("status") == "rejected" else "OK")
        conn.execute("INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) VALUES (?,?,?,?,?,?,?,?,?,?)", values)
        return identifier

    def _prior(self, conn, key, operation, request, command_key):
        prior = conn.execute("SELECT actor_key,session_key,operation,request_json,result_json,audit_id FROM preparazioni_commands WHERE tenant_key=? AND command_key=?",
                             (self.tenant, command_key)).fetchone()
        if prior is None:
            return None
        if tuple(prior[i] for i in range(4)) != (self.actor, key, operation, request):
            raise ValueError("Comando già utilizzato con contenuto o operatore diversi.")
        receipt = json.loads(prior[4])
        audit = conn.execute("SELECT id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,esito FROM audit_log WHERE id=?", (prior[5],)).fetchone()
        details = json.loads(audit[5]) if audit is not None else {}
        expected_actor = (self.actor, self.actor, f"udienza.{operation}", "preparazione_udienza", key)
        expected_outcome = "RIFIUTATO" if receipt.get("status") == "rejected" else "OK"
        if (audit is None or tuple(audit[i] for i in range(5)) != expected_actor or audit[6] != expected_outcome
                or details.get("tenant") != self.tenant or details.get("revision") != receipt.get("revision")
                or details.get("after") != receipt):
            raise RuntimeError("Conferma della preparazione senza audit concordante.")
        if receipt.get("status") == "rejected":
            raise PreparazioneRejected(receipt)
        return receipt

    def reject(self, key, operation, intent, *, command_key, expected_revision, code, message):
        """Un comando rifiutato non potrà scrivere dopo un aggiornamento dei dati."""
        if not self.actor or not isinstance(command_key, str) or str(UUID(command_key)) != command_key:
            raise ValueError("Identità del rifiuto della preparazione non valida.")
        if (not isinstance(operation, str) or not operation.strip() or not isinstance(intent, dict)
                or type(expected_revision) is not int or expected_revision < 0
                or code not in {"validation", "conflict"} or not isinstance(message, str) or not message.strip()):
            raise ValueError("Intento del rifiuto della preparazione non valido.")
        request = encode({"intent": intent, "expected_revision": expected_revision})
        result = {}
        def write(conn, _):
            result.clear()
            self._adoption(conn)
            try:
                prior = self._prior(conn, key, operation, request, command_key)
            except PreparazioneRejected as exc:
                prior = exc.result
            if prior is not None:
                result.update(prior)
                return
            current = self.get(key, conn=conn)
            revision = current["revision"] if current else 0
            stamp = datetime.now(timezone.utc).isoformat()
            result.update({"status": "rejected", "code": code, "message": message,
                           "revision": revision, "expected_revision": expected_revision})
            identifier = str(uuid5(NAMESPACE_URL, encode(["preparazione", self.tenant, key, revision, operation, command_key])))
            inserted = conn.execute("INSERT INTO preparazioni_commands VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_key,command_key) DO NOTHING RETURNING command_key",
                (self.tenant, command_key, self.actor, key, operation, request, encode(result), identifier, stamp)).fetchone()
            if inserted is None:
                try:
                    prior = self._prior(conn, key, operation, request, command_key)
                except PreparazioneRejected as exc:
                    prior = exc.result
                if prior is None:
                    raise RuntimeError("Ricevuta concorrente non riscontrata.")
                result.clear()
                result.update(prior)
                return
            self._audit(conn, key, operation, revision, current["record"] if current else {}, result, stamp, command_key=command_key)
        self.db.salva_tabella("preparazioni_commands", [None], write, delete_all=False)
        return result

    def execute(self, key, operation, intent, *, command_key, expected_revision, apply, initial_record=None):
        """Il callback usa esclusivamente conn, senza commit o scritture JSON."""
        if not self.actor or not isinstance(command_key, str) or str(UUID(command_key)) != command_key:
            raise ValueError("Identità del comando di preparazione non valida.")
        if not isinstance(intent, dict) or not isinstance(operation, str) or not operation.strip():
            raise ValueError("Intento della preparazione non valido.")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Versione della preparazione non valida.")
        initial = validate_record(initial_record) if initial_record is not None else None
        if initial is not None and (operation != "avvio" or expected_revision != 0 or initial["id"] != key):
            raise ValueError("Intento di avvio della preparazione non valido.")
        if initial is not None and (intent.get("id_fascicolo"), intent.get("id_appuntamento")) != (initial["id_fascicolo"], initial["id_appuntamento"]):
            raise ValueError("Collegamenti dell'avvio discordanti dall'intento.")
        # Checklist e timestamp derivano dal repository e possono cambiare
        # mentre si ripete una risposta persa. L'identità immutabile è l'intento
        # dell'operatore: il replay restituisce il primo risultato confermato.
        request = encode({"intent": intent, "expected_revision": expected_revision})
        result = {}
        def write(conn, _):
            result.clear()  # Anche il retry nativo riparte da una ricevuta vuota.
            self._adoption(conn)
            prior = self._prior(conn, key, operation, request, command_key)
            if prior is not None:
                result.update(prior)
                return
            current = self.get(key, conn=conn)
            created = False
            stamp = datetime.now(timezone.utc).isoformat()
            if current is None and initial is not None:
                inserted = conn.execute("INSERT INTO preparazioni_sessions VALUES (?,?,?,?,0,?,?) ON CONFLICT DO NOTHING RETURNING session_key",
                    (self.tenant, key, initial["id_fascicolo"], initial["id_appuntamento"], encode(initial), stamp)).fetchone()
                current = self.get(key, conn=conn)
                created = inserted is not None
                if current is None:
                    raise PreparazioneConflict("Udienza già preparata in un'altra sessione: riaprire la preparazione esistente.")
            if current is None:
                raise ValueError("Preparazione non trovata nello studio.")
            if current.get("reference_issue"):
                raise ValueError(current["reference_issue"] + " Preparazione conservata in sola lettura; recupero della fonte necessario.")
            if initial is not None and not created:
                if (current["record"]["id_fascicolo"], current["record"]["id_appuntamento"]) != (initial["id_fascicolo"], initial["id_appuntamento"]):
                    raise PreparazioneConflict("Udienza già preparata per un altro fascicolo: collegamento da verificare.")
                # Un secondo avvio riapre il lavoro corrente senza ricrearlo o
                # riportarlo ai valori iniziali, anche dopo il completamento.
                result.update({**current, "effects": {"status": "already_present"}})
                audit_id = self._audit(conn, key, operation, current["revision"], current["record"], result, stamp, command_key=command_key)
                conn.execute("INSERT INTO preparazioni_commands VALUES (?,?,?,?,?,?,?,?,?)",
                    (self.tenant, command_key, self.actor, key, operation, request, encode(result), audit_id, stamp))
                return
            if current["revision"] != expected_revision:
                raise PreparazioneConflict("Preparazione aggiornata da un altro utente: bozza conservata, nessun effetto registrato.")
            # Acquisisce la versione prima di chiamare lo scrittore degli effetti.
            claimed = conn.execute("UPDATE preparazioni_sessions SET revision=revision+1 WHERE tenant_key=? AND session_key=? AND revision=? RETURNING revision",
                                   (self.tenant, key, expected_revision)).fetchone()
            if claimed is None:
                raise PreparazioneConflict("Preparazione cambiata durante il salvataggio.")
            session = SessioneWizardPro.from_dict(current["record"])
            effects = apply(conn, session, intent)
            if not isinstance(effects, dict):
                raise ValueError("Effetti della preparazione senza riscontro strutturato.")
            stamp = datetime.now(timezone.utc).isoformat()
            session.modificato_il = stamp
            record = validate_record(session.to_dict())
            if (record["id"], record["id_fascicolo"], record["id_appuntamento"]) != (key, current["record"]["id_fascicolo"], current["record"]["id_appuntamento"]):
                raise ValueError("Identità della preparazione modificata dal comando.")
            if operation == "elimina":
                conn.execute("DELETE FROM preparazioni_sessions WHERE tenant_key=? AND session_key=?",
                             (self.tenant, key))
            else:
                conn.execute("UPDATE preparazioni_sessions SET payload_json=?,updated_at=? WHERE tenant_key=? AND session_key=?",
                             (encode(record), stamp, self.tenant, key))
            result.update({"record": record, "revision": int(claimed[0]), "effects": effects})
            if operation == "elimina":
                result["deleted"] = True
            audit_id = self._audit(conn, key, operation, result["revision"], current["record"], result, stamp, command_key=command_key)
            conn.execute("INSERT INTO preparazioni_commands VALUES (?,?,?,?,?,?,?,?,?)",
                         (self.tenant, command_key, self.actor, key, operation, request, encode(result), audit_id, stamp))
        self.db.salva_tabella("preparazioni_sessions", [None], write, delete_all=False)
        return result
