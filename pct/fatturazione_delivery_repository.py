"""Tentativi di invio idempotenti, sul database SQL proprietario della fattura."""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def request_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class FatturazioneDeliveryRepository:
    def __init__(self, studio_db: Any, tenant_id: str):
        if studio_db is None or not tenant_id:
            raise ValueError("Archivio invii dello studio non disponibile.")
        self.db = studio_db
        self.tenant_id = tenant_id
        self.conn = studio_db._conn_per_scrittura() if callable(getattr(studio_db, "_conn_per_scrittura", None)) else studio_db.conn
        # Migrazione idempotente esplicita, SQL compatibile su entrambi i backend.
        schema = Path(__file__).with_name("sql") / "20260908_fatturazione_delivery.sql"
        with self.transaction():
            for statement in schema.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    self.conn.execute(statement)
            if getattr(self.db, "raw_conn", None) is not None:
                columns = {row["column_name"] for row in self.conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'fatturazione_sdi_receipts'").fetchall()}
            else:
                columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(fatturazione_sdi_receipts)").fetchall()}
            for name, default in (("verification_state", "pending"), ("next_attempt_at", "")):
                if name not in columns:
                    self.conn.execute(f"ALTER TABLE fatturazione_sdi_receipts ADD COLUMN {name} TEXT NOT NULL DEFAULT '{default}'")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_fatturazione_sdi_retry ON fatturazione_sdi_receipts(tenant_id, verification_state, next_attempt_at)")

    @contextmanager
    def transaction(self):
        raw_connection = getattr(self.db, "raw_conn", None)
        if raw_connection is not None:
            try:
                yield self.conn
                raw_connection.commit()
            except Exception:
                raw_connection.rollback()
                raise
        else:
            with self.conn:
                yield self.conn

    def claim(self, invoice_id: str, channel: str, request_hash: str) -> dict[str, Any]:
        attempt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, ":".join((self.tenant_id, invoice_id, channel, request_hash))))
        nonce = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction():
            self.conn.execute(
                "INSERT INTO fatturazione_delivery_attempts (id, tenant_id, invoice_id, channel, request_hash, claim_token, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (attempt_id, self.tenant_id, invoice_id, channel, request_hash, nonce, "sending", now, now),
            )
            row = self.conn.execute("SELECT id, state, message_id, claim_token FROM fatturazione_delivery_attempts WHERE id = ? AND tenant_id = ?", (attempt_id, self.tenant_id)).fetchone()
        if row is None:
            row = self.conn.execute("SELECT id, state, message_id, claim_token FROM fatturazione_delivery_attempts WHERE tenant_id = ? AND invoice_id = ? AND channel = ? AND state IN ('sending', 'uncertain', 'sent_unrecorded') ORDER BY created_at DESC LIMIT 1", (self.tenant_id, invoice_id, channel)).fetchone()
        if row is None:
            raise ValueError("Tentativo concorrente non disponibile: aggiornare lo stato prima di riprovare.")
        result = dict(row)
        if result["state"] == "confirmed_not_sent":
            with self.transaction():
                self.conn.execute("UPDATE fatturazione_delivery_attempts SET state = ?, claim_token = ?, updated_at = ? WHERE id = ? AND tenant_id = ? AND state = ?", ("sending", nonce, now, attempt_id, self.tenant_id, "confirmed_not_sent"))
                result = dict(self.conn.execute("SELECT id, state, message_id, claim_token FROM fatturazione_delivery_attempts WHERE id = ? AND tenant_id = ?", (attempt_id, self.tenant_id)).fetchone())
        result["acquired"] = result.pop("claim_token") == nonce
        return result

    def finish(self, attempt_id: str, state: str, message_id: str = "") -> None:
        if state not in {"sent", "uncertain", "sent_unrecorded", "confirmed_not_sent"}:
            raise ValueError("Stato invio non valido.")
        with self.transaction():
            self.conn.execute("UPDATE fatturazione_delivery_attempts SET state = ?, message_id = ?, updated_at = ? WHERE id = ? AND tenant_id = ?", (state, message_id, datetime.now(timezone.utc).isoformat(), attempt_id, self.tenant_id))

    def resolve(self, invoice_id: str, attempt_id: str, state: str) -> dict[str, Any]:
        if state not in {"sent", "confirmed_not_sent"}:
            raise ValueError("Esito di verifica non valido.")
        with self.transaction():
            row = self.conn.execute("SELECT id, state, message_id, updated_at FROM fatturazione_delivery_attempts WHERE id = ? AND tenant_id = ? AND invoice_id = ?", (attempt_id, self.tenant_id, invoice_id)).fetchone()
            if row is None or row["state"] not in {"sending", "uncertain", "sent_unrecorded"}:
                raise ValueError("Tentativo non disponibile per la riconciliazione.")
            # Un invio ancora in corso non può essere sbloccato da un secondo tab.
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(row["updated_at"])).total_seconds()
            if row["state"] == "sending" and elapsed < 300:
                raise ValueError("Invio ancora in corso: attendi l'esito prima della riconciliazione.")
            self.conn.execute("UPDATE fatturazione_delivery_attempts SET state = ?, updated_at = ? WHERE id = ? AND tenant_id = ? AND invoice_id = ?", (state, datetime.now(timezone.utc).isoformat(), attempt_id, self.tenant_id, invoice_id))
        return dict(row)

    def list_for_invoice(self, invoice_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute("SELECT id, channel, state, message_id, created_at, updated_at FROM fatturazione_delivery_attempts WHERE tenant_id = ? AND invoice_id = ? ORDER BY created_at DESC", (self.tenant_id, invoice_id)).fetchall()]
