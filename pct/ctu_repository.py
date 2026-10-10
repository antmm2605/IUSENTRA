"""Incarichi CTU SQL: adozione esplicita, revisioni e comandi persistenti.

Nessun bootstrap, lettura del JSON, OCR o DDL nel costruttore/runtime.
Il collegamento del factory e l'adozione sono fasi distinte della consegna.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID, uuid5, NAMESPACE_URL

DDL = (
    """CREATE TABLE IF NOT EXISTS ctu_state (
        tenant_key TEXT PRIMARY KEY,revision BIGINT NOT NULL,
        source_sha256 TEXT NOT NULL,backup_reference TEXT NOT NULL,initialized_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS ctu_records (
        tenant_key TEXT NOT NULL,record_key TEXT NOT NULL,fascicolo_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(tenant_key,record_key))""",
    "CREATE INDEX IF NOT EXISTS idx_ctu_fascicolo ON ctu_records(tenant_key,fascicolo_id)",
    """CREATE TABLE IF NOT EXISTS ctu_commands (
        tenant_key TEXT NOT NULL,command_key TEXT NOT NULL,actor_key TEXT NOT NULL,
        operation TEXT NOT NULL,request_json TEXT NOT NULL,result_json TEXT NOT NULL,
        committed_revision BIGINT NOT NULL,created_at TEXT NOT NULL,
        PRIMARY KEY(tenant_key,command_key))""",
    """CREATE TABLE IF NOT EXISTS ctu_command_rejections (
        tenant_key TEXT NOT NULL,command_key TEXT NOT NULL,actor_key TEXT NOT NULL,
        operation TEXT NOT NULL,request_json TEXT NOT NULL,result_json TEXT NOT NULL,
        created_at TEXT NOT NULL,PRIMARY KEY(tenant_key,command_key))""",
    """CREATE TABLE IF NOT EXISTS ctu_audit (
        tenant_key TEXT NOT NULL,revision BIGINT NOT NULL,record_key TEXT NOT NULL,
        actor_key TEXT NOT NULL,action TEXT NOT NULL,before_json TEXT NOT NULL,
        after_json TEXT NOT NULL,created_at TEXT NOT NULL,
        PRIMARY KEY(tenant_key,revision,record_key))""",
)


class CtuConflict(ValueError):
    """La bozza è basata su una revisione superata: nessun dato sovrascritto."""


class CtuRejected(ValueError):
    """Rifiuto persistente: il medesimo comando non potrà scrivere in seguito."""

    def __init__(self, result):
        self.result = result
        super().__init__(result["message"])


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_payload(raw):
    """Preserva i campi della fonte, senza inventare identità o perdere righe."""
    from pct.ctu import ConsulenteParte, IncaricoCtu, RUOLI_STUDIO, STATI_INCARICO, _CAMPI_DATA

    if not isinstance(raw, dict):
        raise ValueError("Archivio CTU non valido: atteso un insieme di incarichi.")
    result = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(value, dict) or value.get("id") != key:
            raise ValueError("Identificativo CTU mancante o discordante.")
        if set(value) - IncaricoCtu.__dataclass_fields__.keys():
            raise ValueError("Campi CTU non riconosciuti: nessun campo eliminato.")
        structured = {"operazioni", "compenso_input", "consulenti_parte"}
        if any(not isinstance(item, str) for field, item in value.items() if field not in structured):
            raise ValueError("Campo testuale CTU non valido.")
        if not str(value.get("fascicolo_id", "")).strip():
            raise ValueError("Fascicolo CTU mancante.")
        if value.get("ruolo_studio", "PARTE") not in RUOLI_STUDIO or value.get("stato", "NOMINATO") not in STATI_INCARICO:
            raise ValueError("Ruolo o stato CTU non valido.")
        for field in _CAMPI_DATA:
            text = value.get(field, "")
            if text and date.fromisoformat(text).isoformat() != text:
                raise ValueError("Data CTU non canonica.")
        for field in ("creato_il", "modificato_il"):
            if not value.get(field) or "T" not in value[field]:
                raise ValueError("Tracciamento storico CTU mancante.")
            datetime.fromisoformat(value[field])
        parties = value.get("consulenti_parte", [])
        if not isinstance(parties, list) or any(
            not isinstance(row, dict) or set(row) - ConsulenteParte.__dataclass_fields__.keys()
            or any(not isinstance(item, str) for item in row.values()) for row in parties
        ):
            raise ValueError("Consulenti di parte non validi: nessuna riga eliminata.")
        operations = value.get("operazioni", [])
        if not isinstance(operations, list) or any(not isinstance(row, dict) for row in operations):
            raise ValueError("Operazioni CTU non valide.")
        seen = set()
        for row in operations:
            operation_id = row.get("id")
            if not isinstance(operation_id, str) or not operation_id.strip() or operation_id in seen:
                raise ValueError("Operazione CTU senza identità o duplicata.")
            seen.add(operation_id)
            if set(row) - {"id", "data", "ora", "tipo", "luogo", "descrizione", "minuti", "presenza_giudice"}:
                raise ValueError("Campi operazione CTU non riconosciuti.")
            if any(not isinstance(item, str) for field, item in row.items() if field not in {"minuti", "presenza_giudice"}):
                raise ValueError("Testo operazione CTU non valido.")
            if not row.get("data") or date.fromisoformat(row["data"]).isoformat() != row["data"]:
                raise ValueError("Data operazione CTU non valida.")
            hour = row.get("ora", "")
            if hour and (len(hour) != 5 or datetime.strptime(hour, "%H:%M").strftime("%H:%M") != hour):
                raise ValueError("Ora operazione CTU non valida.")
            if type(row.get("minuti", 0)) is not int or not 0 <= row.get("minuti", 0) <= 1440:
                raise ValueError("Durata operazione CTU non valida.")
            if "presenza_giudice" in row and type(row["presenza_giudice"]) is not bool:
                raise ValueError("Presenza del giudice non valida.")
        if not isinstance(value.get("compenso_input", {}), dict):
            raise ValueError("Dati del compenso CTU non validi.")
        encode(value)  # Rifiuta NaN/infinito anche nelle strutture annidate.
        result[key] = IncaricoCtu.from_dict(value).to_dict()
    return result


class CtuRepository:
    def __init__(self, studio_db, tenant_key, *, actor_key="", expected_adoption=None):
        if not isinstance(tenant_key, str) or not tenant_key.strip():
            raise ValueError("Contesto studio CTU mancante.")
        self.db, self.tenant, self.actor = studio_db, tenant_key, actor_key
        if not isinstance(actor_key, str):
            raise ValueError("Attore CTU non valido.")
        self.expected_adoption = expected_adoption
        self.revision = None
        self.original = {}

    def _write(self):
        writable = getattr(self.db, "_conn_per_scrittura", None)
        return writable() if callable(writable) else self.db.conn

    def _finish(self, conn, *, rollback=False):
        target = getattr(self.db, "raw_conn", None)
        target = conn if target is None else target
        target.rollback() if rollback else target.commit()

    def ensure_schema(self):
        """Solo migrazione esplicita; mai da GET o costruttore."""
        conn = self._write()
        try:
            for statement in DDL:
                conn.execute(statement)
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise

    def _audit(self, conn, revision, key, action, before, after, stamp):
        if not self.actor:
            raise ValueError("Attore della scrittura CTU mancante.")
        conn.execute(
            "INSERT INTO ctu_audit VALUES (?,?,?,?,?,?,?,?)",
            (self.tenant, revision, key, self.actor, action, before, after, stamp),
        )
        values = self._audit_values(revision, key, self.actor, action, before, after, stamp)
        conn.execute(
            "INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING", values,
        )
        stored = conn.execute("SELECT id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito "
                              "FROM audit_log WHERE id=?", (values[0],)).fetchone()
        if stored is None or tuple(stored[i] for i in range(10)) != values:
            raise RuntimeError("Audit CTU discordante: registrazione annullata.")

    def _audit_values(self, revision, key, actor, action, before, after, stamp):
        audit_id = str(uuid5(NAMESPACE_URL, encode(["ctu", self.tenant, revision, key])))
        return (audit_id, stamp, actor, actor, f"ctu.{action}", "ctu", key,
                encode({"tenant": self.tenant, "revision": revision, "before": json.loads(before), "after": json.loads(after)}), "", "OK")

    def initialize(self, payload, *, source_sha256, backup_reference):
        payload = validate_payload(payload)
        if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
            raise ValueError("Impronta della fonte CTU non valida.")
        if not isinstance(backup_reference, str) or not backup_reference.strip():
            raise ValueError("Backup coerente CTU mancante.")
        conn = self._write()
        try:
            stamp = datetime.now(timezone.utc).isoformat()
            inserted = conn.execute(
                "INSERT INTO ctu_state VALUES (?,0,?,?,?) ON CONFLICT(tenant_key) DO NOTHING RETURNING tenant_key",
                (self.tenant, source_sha256, backup_reference, stamp),
            ).fetchone()
            if inserted is None:
                row = conn.execute("SELECT source_sha256,backup_reference FROM ctu_state WHERE tenant_key=?", (self.tenant,)).fetchone()
                if row is None or row[0] != source_sha256 or row[1] != backup_reference:
                    raise ValueError("Adozione CTU già presente con fonte o backup diversi.")
            else:
                for key, value in payload.items():
                    conn.execute("INSERT INTO ctu_records VALUES (?,?,?,?,?)",
                                 (self.tenant, key, value["fascicolo_id"], encode(value), stamp))
                self._audit(conn, 0, "__adoption", "adozione", "{}",
                            encode({"source_sha256": source_sha256, "backup_reference": backup_reference, "records": len(payload)}), stamp)
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        return self.load()

    def load(self):
        rows = self.db.conn.execute(
            "SELECT s.revision,r.record_key,r.fascicolo_id,r.payload_json,s.source_sha256,s.backup_reference FROM ctu_state s "
            "LEFT JOIN ctu_records r ON r.tenant_key=s.tenant_key WHERE s.tenant_key=?", (self.tenant,),
        ).fetchall()
        if not rows:
            raise RuntimeError("Archivio CTU SQL non adottato: recupero necessario.")
        if self.expected_adoption is not None and (rows[0][4], rows[0][5]) != tuple(self.expected_adoption):
            raise RuntimeError("Adozione CTU cambiata durante l'apertura: accesso sospeso.")
        payload = {str(row[1]): json.loads(row[3]) for row in rows if row[1] is not None}
        payload = validate_payload(payload)
        if any(row[1] is not None and payload[str(row[1])]["fascicolo_id"] != row[2] for row in rows):
            raise RuntimeError("Collegamento CTU al fascicolo discordante.")
        self.revision = int(rows[0][0])
        self.original = {key: encode(value) for key, value in payload.items()}
        return payload

    def command(self, key, operation, request, expected_revision):
        """Identità immutabile: anche revisione e intento fanno parte del comando."""
        if not isinstance(key, str) or str(UUID(key)) != key:
            raise ValueError("Identificativo del comando CTU non valido.")
        if not isinstance(operation, str) or not operation.strip() or not isinstance(request, dict):
            raise ValueError("Intento CTU non valido.")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Revisione CTU non valida.")
        return {"key": key, "operation": operation, "request": encode({"expected_revision": expected_revision, "intent": request})}

    def replay(self, command, *, conn=None):
        self._validate_command(command)
        conn = self.db.conn if conn is None else conn
        row = conn.execute("SELECT actor_key,operation,request_json,result_json,committed_revision "
                           "FROM ctu_commands WHERE tenant_key=? AND command_key=?", (self.tenant, command["key"])).fetchone()
        if row is None:
            rejected = conn.execute("SELECT actor_key,operation,request_json,result_json,created_at "
                                    "FROM ctu_command_rejections WHERE tenant_key=? AND command_key=?",
                                    (self.tenant, command["key"])).fetchone()
            if rejected is not None:
                if tuple(rejected[i] for i in range(3)) != (self.actor, command["operation"], command["request"]):
                    raise ValueError("Comando CTU già utilizzato con attore o contenuto diversi.")
                result = json.loads(rejected[3])
                values = self._rejection_audit(command, result, rejected[4])
                stored = conn.execute("SELECT id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito "
                                      "FROM audit_log WHERE id=?", (values[0],)).fetchone()
                if stored is None or tuple(stored[i] for i in range(10)) != values:
                    raise RuntimeError("Rifiuto CTU senza audit concordante: recupero necessario.")
                raise CtuRejected(result)
            return None
        if tuple(row[i] for i in range(3)) != (self.actor, command["operation"], command["request"]):
            raise ValueError("Comando CTU già utilizzato con attore o contenuto diversi.")
        result = json.loads(row[3])
        audit = conn.execute("SELECT actor_key,action,after_json,before_json,created_at FROM ctu_audit WHERE tenant_key=? AND revision=? AND record_key=?",
                             (self.tenant, row[4], result["record"]["id"])).fetchone()
        if audit is None or tuple(audit[i] for i in range(3)) != (self.actor, command["operation"], encode(result["record"])):
            raise RuntimeError("Esito CTU senza audit concordante: recupero necessario.")
        values = self._audit_values(row[4], result["record"]["id"], self.actor, audit[1], audit[3], audit[2], audit[4])
        general = conn.execute("SELECT id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito "
                               "FROM audit_log WHERE id=?", (values[0],)).fetchone()
        if general is None or tuple(general[i] for i in range(10)) != values:
            raise RuntimeError("Audit generale CTU non riscontrato: recupero necessario.")
        if "delivery" in result:
            values = self._delivery_audit(command, result["delivery"], audit[4])
            receipt = conn.execute("SELECT id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito FROM audit_log WHERE id=?", (values[0],)).fetchone()
            if receipt is None or tuple(receipt[i] for i in range(10)) != values:
                raise RuntimeError("Audit della consegna CTU discordante: recupero necessario.")
        return result

    def _delivery_audit(self, command, result, stamp):
        identifier = str(uuid5(NAMESPACE_URL, encode(["ctu-delivery", self.tenant, command["key"]])))
        return (identifier, stamp, self.actor, self.actor, "ctu.consegna_interna", "ctu", command["key"],
                encode({"tenant": self.tenant, "operation": command["operation"], "result": result}), "", "OK")

    def _rejection_audit(self, command, result, stamp):
        identifier = str(uuid5(NAMESPACE_URL, encode(["ctu-rejected", self.tenant, command["key"]])))
        return (identifier, stamp, self.actor, self.actor, "ctu.comando_rifiutato", "ctu", command["key"],
                encode({"tenant": self.tenant, "operation": command["operation"],
                        "request": json.loads(command["request"]), "result": result}), "", "RIFIUTATO")

    def reject(self, command, *, code, message):
        """Serializza con le scritture; un esito già registrato prevale sul rifiuto."""
        self._validate_command(command)
        if not self.actor or code not in {"validation", "conflict"} or not isinstance(message, str) or not message.strip():
            raise ValueError("Rifiuto del comando CTU non valido.")
        conn = self._write()
        try:
            # Blocca la revisione senza fingere una mutazione del registro:
            # un rifiuto non deve produrre segnali live di dati aggiornati.
            if getattr(self.db, "raw_conn", None) is None:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT revision FROM ctu_state WHERE tenant_key=?", (self.tenant,)).fetchone()
            else:
                row = conn.execute("SELECT revision FROM ctu_state WHERE tenant_key=? FOR UPDATE", (self.tenant,)).fetchone()
            if row is None:
                raise RuntimeError("Archivio CTU non adottato: rifiuto non confermabile.")
            prior = self.replay(command, conn=conn)
            if prior is not None:
                self._finish(conn, rollback=True)
                return prior
            result = {"code": code, "message": message, "expected_revision": json.loads(command["request"])["expected_revision"],
                      "rejected_at_revision": int(row[0])}
            stamp = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO ctu_command_rejections VALUES (?,?,?,?,?,?,?)",
                         (self.tenant, command["key"], self.actor, command["operation"], command["request"], encode(result), stamp))
            values = self._rejection_audit(command, result, stamp)
            conn.execute("INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?)", values)
            stored = conn.execute("SELECT id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito "
                                  "FROM audit_log WHERE id=?", (values[0],)).fetchone()
            if stored is None or tuple(stored[i] for i in range(10)) != values:
                raise RuntimeError("Audit del rifiuto CTU discordante: registrazione annullata.")
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        raise CtuRejected(result)

    def save(self, payload, *, command, delivery=None):
        self._validate_command(command)
        validated = validate_payload(payload)
        encoded = {key: encode(value) for key, value in validated.items()}
        if self.original.keys() - encoded.keys():
            raise ValueError("L'incarico CTU non può essere eliminato.")
        changes = {key: value for key, value in encoded.items() if self.original.get(key) != value}
        if len(changes) != 1 or not self.actor:
            raise ValueError("Il comando CTU deve modificare un solo incarico con attore identificato.")
        key = next(iter(changes))
        if key in self.original and json.loads(self.original[key])["fascicolo_id"] != validated[key]["fascicolo_id"]:
            raise ValueError("Il comando non può trasferire l'incarico a un altro fascicolo.")
        conn = self._write()
        try:
            prior = self.replay(command, conn=conn)
            if prior is not None:
                self._finish(conn, rollback=True)
                return prior
            stamp = datetime.now(timezone.utc).isoformat()
            revision = conn.execute("UPDATE ctu_state SET revision=revision+1 WHERE tenant_key=? AND revision=? RETURNING revision",
                                    (self.tenant, self.revision)).fetchone()
            # La barriera è acquisita: rileggere anche un rifiuto arrivato fra
            # il primo controllo e questa scrittura, annullando l'incremento.
            prior = self.replay(command, conn=conn)
            if prior is not None:
                self._finish(conn, rollback=True)
                return prior
            if revision is None:
                prior = self.replay(command, conn=conn)
                if prior is not None:
                    self._finish(conn, rollback=True)
                    return prior
                raise CtuConflict("Incarichi CTU aggiornati da un altro utente. La bozza è conservata; nessuna modifica registrata.")
            expected = json.loads(command["request"])["expected_revision"]
            if expected != self.revision:
                raise CtuConflict("La bozza CTU usa una revisione superata: nessuna modifica registrata.")
            result = {"record": validated[key], "revision": int(revision[0])}
            conn.execute("INSERT INTO ctu_records VALUES (?,?,?,?,?) ON CONFLICT(tenant_key,record_key) "
                         "DO UPDATE SET payload_json=excluded.payload_json,updated_at=excluded.updated_at",
                         (self.tenant, key, validated[key]["fascicolo_id"], encoded[key], stamp))
            self._audit(conn, int(revision[0]), key, command["operation"], self.original.get(key, "{}"), encoded[key], stamp)
            if delivery is not None:
                result["delivery"] = delivery(conn, validated[key])
                if not isinstance(result["delivery"], dict):
                    raise ValueError("Consegna CTU priva di riscontro strutturato.")
                values = self._delivery_audit(command, result["delivery"], stamp)
                conn.execute("INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) VALUES (?,?,?,?,?,?,?,?,?,?)", values)
            conn.execute("INSERT INTO ctu_commands VALUES (?,?,?,?,?,?,?,?)",
                         (self.tenant, command["key"], self.actor, command["operation"], command["request"], encode(result), int(revision[0]), stamp))
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        self.revision, self.original = result["revision"], encoded
        return result

    def _validate_command(self, command):
        if not isinstance(command, dict) or set(command) != {"key", "operation", "request"}:
            raise ValueError("Comando CTU non valido.")
        request = json.loads(command["request"])
        if not isinstance(request, dict) or set(request) != {"expected_revision", "intent"}:
            raise ValueError("Intento CTU non valido.")
        expected = self.command(command["key"], command["operation"], request["intent"], request["expected_revision"])
        if command != expected:
            raise ValueError("Comando CTU non canonico.")
