"""Persistenza SQL tenant-aware delle condivisioni, senza fallback operativi."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)
KINDS = ("cartelle", "fascicoli", "link")
DDL = (
    """CREATE TABLE IF NOT EXISTS condivisioni_records (
        tenant_key TEXT NOT NULL, kind TEXT NOT NULL, record_key TEXT NOT NULL,
        payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_key, kind, record_key))""",
    """CREATE TABLE IF NOT EXISTS condivisioni_bootstrap (
        tenant_key TEXT PRIMARY KEY, bootstrap_source TEXT NOT NULL,
        initialized_at TEXT NOT NULL)""",
)


class CondivisioniConflict(RuntimeError):
    """Una modifica concorrente impedisce di sovrascrivere accessi più recenti."""


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize(raw):
    if not isinstance(raw, dict):
        raise ValueError("Archivio condivisioni non valido")
    if raw and all(isinstance(v, dict) and "accessi" in v for v in raw.values()):
        raw = {"cartelle": raw}
    result = {kind: raw.get(kind, {}) for kind in KINDS}
    if any(not isinstance(value, dict) for value in result.values()):
        raise ValueError("Sezioni dell'archivio condivisioni non valide")
    return result


class CondivisioniRepository:
    def __init__(self, studio_db, tenant_key: str, mirror_path: Path):
        if not str(tenant_key).strip():
            raise ValueError("Contesto studio mancante per le condivisioni")
        self.db = studio_db
        self.tenant = str(tenant_key)
        self.mirror_path = mirror_path
        self.original = {kind: {} for kind in KINDS}
        self._ensure_schema()

    def _write_conn(self):
        writable = getattr(self.db, "_conn_per_scrittura", None)
        return writable() if callable(writable) else self.db.conn

    def _finish(self, conn, *, rollback=False):
        raw = getattr(self.db, "raw_conn", None)
        target = raw if raw is not None else conn
        target.rollback() if rollback else target.commit()

    def _ensure_schema(self):
        conn = self._write_conn()
        try:
            for statement in DDL:
                conn.execute(statement)
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise

    def _bootstrap_source(self, conn):
        module = conn.execute(
            "SELECT nome FROM moduli_dati WHERE nome=?", ("condivisioni",)
        ).fetchone()
        if module is not None:
            rows = conn.execute(
                "SELECT record_key,payload_json FROM moduli_json_records WHERE modulo=?",
                ("condivisioni",),
            ).fetchall()
            # Anche un modulo inizializzato senza record è un insieme vuoto reale.
            raw = {str(row[0]): json.loads(row[1]) for row in rows}
            return _normalize(raw), "sql_module"
        # Solo bootstrap iniziale governato, mai ripiego dopo un errore SQL.
        raw = json.loads(self.mirror_path.read_text(encoding="utf-8")) if self.mirror_path.exists() else {}
        return _normalize(raw), "controlled_json_bootstrap"

    def _bootstrap(self):
        conn = self._write_conn()
        try:
            stamp = datetime.now(timezone.utc).isoformat()
            created = conn.execute(
                "INSERT INTO condivisioni_bootstrap (tenant_key,bootstrap_source,initialized_at) "
                "VALUES (?,?,?) ON CONFLICT (tenant_key) DO NOTHING RETURNING tenant_key",
                (self.tenant, "pending", stamp),
            ).fetchone()
            if created is not None:
                payload, source = self._bootstrap_source(conn)
                for kind, items in payload.items():
                    for key, value in items.items():
                        conn.execute(
                            "INSERT INTO condivisioni_records (tenant_key,kind,record_key,payload_json,updated_at) "
                            "VALUES (?,?,?,?,?)", (self.tenant, kind, str(key), _encode(value), stamp)
                        )
                conn.execute(
                    "UPDATE condivisioni_bootstrap SET bootstrap_source=? WHERE tenant_key=?",
                    (source, self.tenant),
                )
                logger.info("Condivisioni: bootstrap SQL governato, origine=%s", source)
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise

    def load(self, *, update_original=True):
        marker = self.db.conn.execute(
            "SELECT bootstrap_source FROM condivisioni_bootstrap WHERE tenant_key=?", (self.tenant,)
        ).fetchone()
        if marker is None:
            self._bootstrap()
        rows = self.db.conn.execute(
            "SELECT kind,record_key,payload_json FROM condivisioni_records WHERE tenant_key=?",
            (self.tenant,),
        ).fetchall()
        payload = {kind: {} for kind in KINDS}
        for row in rows:
            if row[0] not in KINDS:
                raise ValueError("Categoria di condivisione non valida")
            payload[row[0]][str(row[1])] = json.loads(row[2])
        if update_original:
            self.original = json.loads(_encode(payload))
        return payload

    def save(self, payload):
        payload = _normalize(payload)
        conn = self._write_conn()
        try:
            stamp = datetime.now(timezone.utc).isoformat()
            for kind in KINDS:
                before, after = self.original[kind], payload[kind]
                for key in before.keys() | after.keys():
                    if key in before and key in after and before[key] == after[key]:
                        continue
                    if key not in before:
                        result = conn.execute(
                            "INSERT INTO condivisioni_records (tenant_key,kind,record_key,payload_json,updated_at) "
                            "VALUES (?,?,?,?,?) ON CONFLICT (tenant_key,kind,record_key) DO NOTHING RETURNING record_key",
                            (self.tenant, kind, str(key), _encode(after[key]), stamp),
                        ).fetchone()
                    elif key not in after:
                        result = conn.execute(
                            "DELETE FROM condivisioni_records WHERE tenant_key=? AND kind=? AND record_key=? "
                            "AND payload_json=? RETURNING record_key",
                            (self.tenant, kind, str(key), _encode(before[key])),
                        ).fetchone()
                    else:
                        result = conn.execute(
                            "UPDATE condivisioni_records SET payload_json=?,updated_at=? WHERE tenant_key=? "
                            "AND kind=? AND record_key=? AND payload_json=? RETURNING record_key",
                            (_encode(after[key]), stamp, self.tenant, kind, str(key), _encode(before[key])),
                        ).fetchone()
                    if result is None:
                        raise CondivisioniConflict("Le condivisioni sono state aggiornate da un altro utente. Ricarica prima di ripetere l'operazione.")
            self._finish(conn)
        except Exception:
            self._finish(conn, rollback=True)
            raise
        self.original = json.loads(_encode(payload))
