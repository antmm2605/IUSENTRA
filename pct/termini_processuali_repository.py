"""Archivio SQL verticale dei termini; adozione esplicita, mai nelle GET.

Il motore di calcolo resta quello nativo. Questo repository conserva i payload
canonici e l'audit senza sostituire lo snapshot dell'intero studio.
Il collegamento ai factory e la migrazione fanno parte della stessa consegna.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pct.termini_processuali import DEFAULT_TEMPLATES, DeadlineAuditRecord, DeadlineTemplate, canonical_sha256


DDL = (
    """CREATE TABLE IF NOT EXISTS termini_state (
        tenant_key TEXT PRIMARY KEY,revision BIGINT NOT NULL,
        source_sha256 TEXT NOT NULL,backup_reference TEXT NOT NULL,
        archive_sha256 TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS termini_records (
        tenant_key TEXT NOT NULL,kind TEXT NOT NULL,record_key TEXT NOT NULL,
        payload_json TEXT NOT NULL,order_key TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(tenant_key,kind,record_key))""",
    "CREATE INDEX IF NOT EXISTS idx_termini_order ON termini_records(tenant_key,kind,order_key)",
)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def archive_records(payload):
    """Valida l'archivio prima dell'adozione, senza scartare campi storici."""
    if not isinstance(payload, dict):
        raise ValueError("Archivio dei termini non valido.")
    keys = {"templates": "code", "audit_logs": "id", "notification_logs": "idempotency_key",
            "calendar_versions": "version", "official_holidays": "day"}
    records = []
    for kind, key_field in keys.items():
        rows = payload.get(kind, [])
        if not isinstance(rows, list):
            raise ValueError("Righe dell'archivio dei termini non valide.")
        if kind == "templates" and not rows:
            rows = [template.to_dict() for template in DEFAULT_TEMPLATES]
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Record dei termini non valido.")
            key = row.get(key_field)
            if not isinstance(key, str) or not key.strip() or key in seen:
                raise ValueError("Identificativo del termine mancante o duplicato: recupero necessario.")
            seen.add(key)
            if kind == "templates":
                template = DeadlineTemplate.from_dict(row)
                if type(template.base_value) is not int or template.base_value <= 0:
                    raise ValueError("Durata del modello di termine non valida.")
                if template.period_type not in {"days", "months"} or template.direction not in {"forward", "backward"}:
                    raise ValueError("Regola del modello di termine non valida.")
                if template.ferial_suspension_policy not in {"applies", "excluded", "not_applicable", "partial", "manual_review"}:
                    raise ValueError("Regime feriale del termine non valido.")
            if kind == "audit_logs":
                audit = DeadlineAuditRecord(**row)
                if audit.immutable_hash != audit.with_hash().immutable_hash:
                    raise ValueError("Impronta dell'audit del termine discordante: nessun dato eliminato.")
            order_key = str(row.get("created_at") or row.get("scheduled_at") or row.get("day") or "")
            records.append((kind, key, encode(row), order_key))
    # Le regole importate, i resoconti e ogni altro campo storico restano
    # disponibili per la revisione; non vengono usati come calcoli verificati.
    extras = {key: value for key, value in payload.items() if key not in keys}
    records.append(("archive_metadata", "historical", encode(extras), ""))
    return records


class DeadlineSqlRepository:
    """SQL canonico dello studio, senza import o DDL nel costruttore."""

    backend = "sql"

    def __init__(self, database, tenant_key, *, source, actor_key, expected_adoption):
        if not isinstance(tenant_key, str) or not tenant_key.strip():
            raise ValueError("Studio dei termini processuali non determinato.")
        if not isinstance(actor_key, str):
            raise ValueError("Attore dei termini processuali non valido.")
        self.db = database
        self.tenant = tenant_key
        self.actor = actor_key
        self.path = Path(source)
        self.expected_adoption = expected_adoption

    def _write(self):
        writable = getattr(self.db, "_conn_per_scrittura", None)
        return writable() if callable(writable) else self.db.conn

    def _finish(self, conn, *, rollback=False):
        target = getattr(self.db, "raw_conn", None)
        target = conn if target is None else target
        target.rollback() if rollback else target.commit()

    def ensure_schema(self):
        """Solo procedura di adozione, dopo backup e barriera dei produttori."""
        conn = self._write()
        try:
            for statement in DDL:
                conn.execute(statement)
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise

    def _assert_adoption(self, conn):
        row = conn.execute(
            "SELECT source_sha256,backup_reference FROM termini_state WHERE tenant_key=?",
            (self.tenant,),
        ).fetchone()
        if row is None or tuple(row[i] for i in range(2)) != tuple(self.expected_adoption or ()):
            raise RuntimeError("Adozione SQL dei termini non riscontrata: recupero necessario.")

    def initialize(self, payload, *, source_sha256, backup_reference):
        """Adozione atomica dopo verifica esterna di backup e fonte bloccata."""
        records = archive_records(payload)
        if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in source_sha256
        ):
            raise ValueError("Impronta della fonte dei termini non valida.")
        if not isinstance(backup_reference, str) or not backup_reference.strip() or not self.actor:
            raise ValueError("Backup coerente o attore dell'adozione dei termini mancante.")
        if tuple(self.expected_adoption or ()) != (source_sha256, backup_reference):
            raise ValueError("Adozione dei termini non concordante con la fonte attesa.")
        conn = self._write()
        try:
            inserted = conn.execute(
                "INSERT INTO termini_state VALUES (?,0,?,?,?) "
                "ON CONFLICT(tenant_key) DO NOTHING RETURNING tenant_key",
                (self.tenant, source_sha256, backup_reference, canonical_sha256(payload)),
            ).fetchone()
            self._assert_adoption(conn)
            archive = conn.execute("SELECT archive_sha256 FROM termini_state WHERE tenant_key=?",
                                   (self.tenant,)).fetchone()
            if archive is None or archive[0] != canonical_sha256(payload):
                raise ValueError("Archivio iniziale dei termini discordante: nessuna nuova adozione.")
            if inserted is not None:
                for kind, key, value, order_key in records:
                    conn.execute("INSERT INTO termini_records VALUES (?,?,?,?,?)",
                                 (self.tenant, kind, key, value, order_key))
                stamp = datetime.now(timezone.utc).isoformat()
                audit_id = str(uuid5(NAMESPACE_URL, encode(["termini.adoption", self.tenant, source_sha256])))
                conn.execute(
                    "INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (audit_id, stamp, self.actor, self.actor, "termini.adozione", "termini", self.tenant,
                     encode({"source_sha256": source_sha256, "backup_reference": backup_reference,
                             "archive_sha256": canonical_sha256(payload), "records": len(records)}), "", "OK"),
                )
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        return {"source_sha256": source_sha256, "backup_reference": backup_reference,
                "records": len(records), "already_present": inserted is None}

    def _records(self, kind):
        conn = self.db.conn
        self._assert_adoption(conn)
        rows = conn.execute(
            "SELECT payload_json FROM termini_records WHERE tenant_key=? AND kind=? ORDER BY record_key",
            (self.tenant, kind),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_templates(self):
        return sorted(self._records("templates"),
                      key=lambda row: (str(row.get("matter_type", "")), str(row.get("name", ""))))

    def get_template(self, code):
        return DeadlineTemplate.from_dict(self.get_template_payload(code))

    def get_template_payload(self, code):
        normalized = str(code or "").strip() or "CUSTOM_PROCESSUALE"
        conn = self.db.conn
        self._assert_adoption(conn)
        row = conn.execute(
            "SELECT payload_json FROM termini_records WHERE tenant_key=? AND kind='templates' AND record_key=?",
            (self.tenant, normalized),
        ).fetchone()
        if row is None:
            raise ValueError("Template termine non trovato")
        return json.loads(row[0])

    def revise_template(self, code, *, expected, replacement, revision, reason, source):
        """Rettifica verificata con confronto atomico e storico, senza toccare i calcoli."""
        if not self.actor or not all(isinstance(value, str) and value.strip()
                                     for value in (code, revision, reason, source)):
            raise ValueError("Rettifica del termine priva di attore, motivo o fonte.")
        if expected.get("code") != code or replacement.get("code") != code:
            raise ValueError("Identità della regola da rettificare discordante.")
        archive_records({"templates": [replacement]})
        before, after = encode(expected), encode(replacement)
        if before == after:
            raise ValueError("La rettifica non modifica la regola.")
        history_key = encode([code, revision])
        history = encode({"code": code, "revision": revision, "reason": reason,
                          "source": source, "actor": self.actor,
                          "previous": expected, "replacement": replacement})
        conn = self._write()
        try:
            self._assert_adoption(conn)
            prior = conn.execute(
                "SELECT payload_json FROM termini_records WHERE tenant_key=? "
                "AND kind='template_revisions' AND record_key=?",
                (self.tenant, history_key),
            ).fetchone()
            if prior is not None:
                if prior[0] != history:
                    raise ValueError("Revisione del termine già presente con contenuto discordante.")
                self._finish(conn)
                return {"already_present": True, "revision": revision}
            updated = conn.execute(
                "UPDATE termini_records SET payload_json=? WHERE tenant_key=? "
                "AND kind='templates' AND record_key=? AND payload_json=? RETURNING record_key",
                (after, self.tenant, code, before),
            ).fetchone()
            if updated is None:
                raise ValueError("Regola modificata o personalizzata: rettifica non applicata.")
            stamp = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO termini_records VALUES (?,'template_revisions',?,?,?)",
                         (self.tenant, history_key, history, stamp))
            conn.execute("UPDATE termini_state SET revision=revision+1 WHERE tenant_key=?", (self.tenant,))
            audit_id = str(uuid5(NAMESPACE_URL, encode(["termini.revisione", self.tenant, code, revision])))
            conn.execute(
                "INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (audit_id, stamp, self.actor, self.actor, "termini.revisione", "termini", code, history, "", "OK"),
            )
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        return {"already_present": False, "revision": revision}

    def save_audit(self, record):
        if not self.actor or record.user_id != self.actor:
            raise ValueError("Attore del calcolo non concordante con lo studio autenticato.")
        hashed = record.with_hash()
        payload = encode(hashed.to_dict())
        conn = self._write()
        try:
            self._assert_adoption(conn)
            inserted = conn.execute(
                "INSERT INTO termini_records VALUES (?,'audit_logs',?,?,?) "
                "ON CONFLICT(tenant_key,kind,record_key) DO NOTHING RETURNING record_key",
                (self.tenant, hashed.id, payload, hashed.created_at),
            ).fetchone()
            stored = conn.execute(
                "SELECT payload_json FROM termini_records WHERE tenant_key=? AND kind='audit_logs' AND record_key=?",
                (self.tenant, hashed.id),
            ).fetchone()
            if stored is None or stored[0] != payload:
                raise RuntimeError("Audit del termine discordante: nessun dato sovrascritto.")
            if inserted is not None:
                conn.execute("UPDATE termini_state SET revision=revision+1 WHERE tenant_key=?", (self.tenant,))
                audit_id = str(uuid5(NAMESPACE_URL, encode(["termini", self.tenant, hashed.id])))
                conn.execute(
                    "INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (audit_id, hashed.created_at, self.actor, self.actor,
                     "termini.calcolo", "termini", hashed.id,
                     encode({"tenant": self.tenant, "immutable_hash": hashed.immutable_hash}), "", "OK"),
                )
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        return hashed

    def list_audit(self, limit=20):
        conn = self.db.conn
        self._assert_adoption(conn)
        rows = conn.execute(
            "SELECT payload_json FROM termini_records WHERE tenant_key=? AND kind='audit_logs' "
            "ORDER BY order_key DESC,record_key DESC LIMIT ?",
            (self.tenant, max(1, int(limit))),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_notification_logs(self, limit=20):
        conn = self.db.conn
        self._assert_adoption(conn)
        rows = conn.execute(
            "SELECT payload_json FROM termini_records WHERE tenant_key=? AND kind='notification_logs' "
            "ORDER BY order_key ASC,record_key ASC LIMIT ?",
            (self.tenant, max(1, int(limit))),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_notification_plan(self, *, deadline_id, case_reference, user_id, notification_plan):
        """Conserva il piano interno; non invia messaggi e non avvia la PEC."""
        if not self.actor or user_id != self.actor:
            raise ValueError("Attore del piano non concordante con lo studio autenticato.")
        if not isinstance(deadline_id, str) or not deadline_id.strip():
            raise ValueError("Calcolo di riferimento del piano mancante.")
        now = datetime.now(timezone.utc).isoformat()
        planned = {}
        for item in notification_plan:
            key = str(item.get("idempotencyKey") or item.get("idempotency_key") or "").strip()
            due = str(item.get("date") or item.get("scheduled_at") or "").strip()
            if not key or not due:
                raise ValueError("Piano incompleto: data o identificativo mancante.")
            row = {
                "id": str(uuid5(NAMESPACE_URL, encode(["termini.piano", self.tenant, key]))),
                "deadline_id": deadline_id, "case_reference": case_reference, "user_id": user_id,
                "channel": str(item.get("channel") or "PEC"),
                "days_left": int(item.get("daysLeft", item.get("days_left", 0))),
                "scheduled_at": due, "status": str(item.get("status") or "pianificabile"),
                "idempotency_key": key, "message_id": "", "receipt_status": "",
                "created_at": now, "updated_at": now,
            }
            if key in planned and planned[key] != row:
                raise ValueError("Piano discordante per lo stesso identificativo.")
            planned[key] = row
        conn = self._write()
        inserted_count = 0
        try:
            self._assert_adoption(conn)
            reference = conn.execute(
                "SELECT record_key FROM termini_records WHERE tenant_key=? AND kind='audit_logs' AND record_key=?",
                (self.tenant, deadline_id),
            ).fetchone()
            if reference is None:
                raise ValueError("Calcolo di riferimento del piano non presente nello studio.")
            for key, row in planned.items():
                inserted = conn.execute(
                    "INSERT INTO termini_records VALUES (?,'notification_logs',?,?,?) "
                    "ON CONFLICT(tenant_key,kind,record_key) DO NOTHING RETURNING record_key",
                    (self.tenant, key, encode(row), row["scheduled_at"]),
                ).fetchone()
                stored = conn.execute(
                    "SELECT payload_json FROM termini_records WHERE tenant_key=? AND kind='notification_logs' AND record_key=?",
                    (self.tenant, key),
                ).fetchone()
                previous = json.loads(stored[0])
                # Stato di consegna e timestamp possono avanzare altrove;
                # il replay deve confrontare il fatto pianificato, senza azzerarli.
                identity = ("deadline_id", "case_reference", "user_id", "channel", "days_left", "scheduled_at")
                if any(previous.get(field) != row[field] for field in identity):
                    raise RuntimeError("Piano del termine discordante: nessun dato sovrascritto.")
                inserted_count += int(inserted is not None)
            if inserted_count:
                conn.execute("UPDATE termini_state SET revision=revision+1 WHERE tenant_key=?", (self.tenant,))
                conn.execute(
                    "INSERT INTO audit_log (id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (str(uuid5(NAMESPACE_URL, encode(["termini.piano", self.tenant, deadline_id, sorted(planned)]))),
                     now, self.actor, self.actor, "termini.piano", "termini", deadline_id,
                     encode({"inserted": inserted_count, "keys": sorted(planned)}), "", "OK"),
                )
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        return inserted_count
