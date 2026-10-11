"""Tenant-scoped registry, one-use challenges and transactional audit."""

import json
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .crypto import encode, public_key, verify


class DeviceRegistry:
    def __init__(self, db, tenant, actor, *, clock=time.time):
        if not tenant or not actor:
            raise PermissionError("Studio e identità richiesti.")
        self.db, self.tenant, self.actor, self.clock = db, tenant, actor, clock

    def ensure_schema(self):
        """Explicit migration/test setup only; never called by an API request."""
        path = Path(__file__).parents[1] / "sql" / "20261011_offline.sql"
        with self.transaction() as conn:
            for statement in path.read_text().split(";"):
                if statement.strip():
                    conn.execute(statement)

    @contextmanager
    def transaction(self):
        writer = getattr(self.db, "_conn_per_scrittura", None)
        conn = writer() if callable(writer) else self.db.conn
        raw = getattr(self.db, "raw_conn", conn)
        try:
            yield conn
            raw.commit()
        except Exception:
            raw.rollback()
            raise

    def lock(self, conn):
        conn.execute(
            "INSERT INTO offline_state(tenant_key) VALUES (?) ON CONFLICT(tenant_key) DO NOTHING", (self.tenant,)
        )
        # Serializes approvals, revocations, nonce consumption and sync commits.
        conn.execute("UPDATE offline_state SET revision=revision WHERE tenant_key=?", (self.tenant,))

    def audit(self, conn, device, action, details=None):
        conn.execute(
            "INSERT INTO offline_audit VALUES (?,?,?,?,?,?,?)",
            (self.tenant, str(uuid4()), self.actor, device, action, encode(details or {}), int(self.clock())),
        )

    def device(self, conn, device_id, *, owner=True):
        row = conn.execute(
            "SELECT device_id,actor_key,label,public_key,fingerprint,status,proven,generation,approved_by "
            "FROM offline_devices WHERE tenant_key=? AND device_id=?",
            (self.tenant, device_id),
        ).fetchone()
        if not row or (owner and row[1] != self.actor):
            raise PermissionError("Computer non autorizzato per questa identità.")
        return dict(
            zip(
                ("id", "actor", "label", "public_key", "fingerprint", "status", "proven", "generation", "approved_by"),
                row,
            )
        )

    def register(self, label, key):
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80:
            raise ValueError("Indica un nome del computer di massimo 80 caratteri.")
        key, fingerprint = public_key(key)
        device_id = str(uuid4())
        with self.transaction() as conn:
            self.lock(conn)
            count = conn.execute(
                "SELECT COUNT(*) FROM offline_devices WHERE tenant_key=? AND actor_key=? AND status='pending'",
                (self.tenant, self.actor),
            ).fetchone()[0]
            if count >= 5:
                raise ValueError("Revoca le richieste in attesa prima di registrarne altre.")
            conn.execute(
                "INSERT INTO offline_devices(tenant_key,device_id,actor_key,label,public_key,fingerprint,status,created_at) "
                "VALUES (?,?,?,?,?,?,'pending',?)",
                (self.tenant, device_id, self.actor, label.strip(), key, fingerprint, int(self.clock())),
            )
            self.audit(conn, device_id, "device.registered", {"fingerprint": fingerprint})
        return {"id": device_id, "fingerprint": fingerprint, "tenant": self.tenant, "actor": self.actor}

    def list_devices(self, *, admin=False):
        with self.transaction() as conn:
            sql = "SELECT device_id,actor_key,label,fingerprint,status,proven,generation FROM offline_devices WHERE tenant_key=?"
            args = (self.tenant,) if admin else (self.tenant, self.actor)
            if not admin:
                sql += " AND actor_key=?"
            rows = conn.execute(sql + " ORDER BY created_at DESC LIMIT 200", args).fetchall()
        return [
            dict(zip(("id", "actor", "label", "fingerprint", "status", "proven", "generation"), row)) for row in rows
        ]

    def change_status(self, device_id, action, fingerprint=""):
        if action not in {"approve", "revoke"}:
            raise ValueError("Operazione sul computer non valida.")
        with self.transaction() as conn:
            self.lock(conn)
            device = self.device(conn, device_id, owner=False)
            if action == "approve":
                if device["status"] != "pending" or not device["proven"] or fingerprint != device["fingerprint"]:
                    raise ValueError("Verifica il codice sul computer da approvare e la prova di registrazione.")
                conn.execute(
                    "UPDATE offline_devices SET status='approved',approved_by=? WHERE tenant_key=? AND device_id=?",
                    (self.actor, self.tenant, device_id),
                )
            else:
                conn.execute(
                    "UPDATE offline_devices SET status='revoked',revoked_by=?,generation=generation+1 WHERE tenant_key=? AND device_id=?",
                    (self.actor, self.tenant, device_id),
                )
                conn.execute(
                    "DELETE FROM offline_challenges WHERE tenant_key=? AND device_id=?", (self.tenant, device_id)
                )
            self.audit(conn, device_id, "device." + action, {"fingerprint": device["fingerprint"]})

    def challenge(self, device_id, purpose):
        if not isinstance(purpose, str) or len(purpose) > 100:
            raise ValueError("Operazione non valida.")
        with self.transaction() as conn:
            self.lock(conn)
            device = self.device(conn, device_id)
            if device["status"] == "revoked" or (purpose != "enroll" and device["status"] != "approved"):
                raise PermissionError("Computer non approvato o revocato.")
            now = int(self.clock())
            conn.execute(
                "DELETE FROM offline_challenges WHERE tenant_key=? AND (expires_at<=? OR device_id=?)",
                (self.tenant, now, device_id),
            )
            challenge_id = str(uuid4())
            message = encode(
                {
                    "protocol": "iusentra-offline-v1",
                    "nonce": uuid4().hex,
                    "tenant": self.tenant,
                    "actor": self.actor,
                    "device": device_id,
                    "generation": device["generation"],
                    "purpose": purpose,
                }
            )
            conn.execute(
                "INSERT INTO offline_challenges VALUES (?,?,?,?,?,?,?)",
                (self.tenant, challenge_id, device_id, self.actor, message, purpose, now + 120),
            )
        return {"challenge": challenge_id, "message": message}

    def authenticate(self, conn, device_id, proof, purpose):
        device = self.device(conn, device_id)
        if device["status"] == "revoked" or (purpose != "enroll" and device["status"] != "approved"):
            raise PermissionError("Computer non approvato o revocato.")
        if not isinstance(proof, dict):
            raise PermissionError("Prova del computer richiesta.")
        row = conn.execute(
            "SELECT message FROM offline_challenges WHERE tenant_key=? AND challenge_id=? "
            "AND device_id=? AND actor_key=? AND purpose=? AND expires_at>?",
            (self.tenant, proof.get("challenge", ""), device_id, self.actor, purpose, int(self.clock())),
        ).fetchone()
        if not row:
            raise PermissionError("Prova scaduta o già utilizzata.")
        verify(device["public_key"], row[0], proof.get("signature", ""))
        conn.execute(
            "DELETE FROM offline_challenges WHERE tenant_key=? AND challenge_id=?", (self.tenant, proof["challenge"])
        )
        return device

    def prove(self, device_id, proof):
        with self.transaction() as conn:
            self.lock(conn)
            self.authenticate(conn, device_id, proof, "enroll")
            conn.execute(
                "UPDATE offline_devices SET proven=1 WHERE tenant_key=? AND device_id=?", (self.tenant, device_id)
            )
            self.audit(conn, device_id, "device.proven")

    def events(self):
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT actor_key,device_id,action,details_json,created_at FROM offline_audit "
                "WHERE tenant_key=? ORDER BY created_at DESC,event_id DESC LIMIT 200",
                (self.tenant,),
            ).fetchall()
        return [
            {"actor": row[0], "device": row[1], "action": row[2], "details": json.loads(row[3]), "at": row[4]}
            for row in rows
        ]
