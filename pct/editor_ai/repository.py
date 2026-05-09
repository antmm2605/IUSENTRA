"""Repository tenant-aware per Editor AI."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pct.postgres_runtime_support import PostgresRepositoryBackend

from .models import (
    AttoAIEditProposal,
    AttoAIRecord,
    AttoAISource,
    AttoAIVersion,
    dataclass_from_dict,
    utc_now,
)
from .validators import EditorAIValidationError


STORE_KEYS = ("records", "versions", "sources", "edit_proposals", "audit_events")
SQLITE_SCHEMA_EDITOR_AI = Path(__file__).resolve().parents[1] / "sql" / "20260505_editor_ai.sql"
POSTGRES_SCHEMA_EDITOR_AI = Path(__file__).resolve().parents[1] / "sql" / "20260505_editor_ai_postgres.sql"


def _postgres_backend_type() -> type[Any] | None:
    return PostgresRepositoryBackend if isinstance(PostgresRepositoryBackend, type) else None


class _ManagedSqliteBackend:
    backend_kind = "sqlite"

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()


class EditorAIRepository:
    def __init__(self, json_path: str | Path, structured_db: Any = None):
        self.json_path = Path(json_path)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.structured_db = structured_db
        self._backend = self._detect_backend(structured_db)
        if self._backend:
            self._ensure_sql_schema()
        self._data = self._load_json()

    @property
    def backend_kind(self) -> str:
        return self._backend or "json"

    @classmethod
    def from_fascicoli_db(cls, fascicoli_db_path: str | Path, *, structured_db: Any = None) -> "EditorAIRepository":
        base = Path(fascicoli_db_path).resolve().parent / "editor_ai"
        return cls(base / "editor_ai.json", structured_db=structured_db)

    @classmethod
    def from_sqlite_db(cls, db_path: str | Path) -> "EditorAIRepository":
        backend = _ManagedSqliteBackend(db_path)
        return cls(Path(db_path).resolve().parent / "editor_ai" / "editor_ai.json", structured_db=backend)

    @classmethod
    def from_postgres_dsn(cls, dsn: str, *, json_root: str | Path) -> "EditorAIRepository":
        backend_cls = _postgres_backend_type()
        if backend_cls is None:
            raise RuntimeError("Backend PostgreSQL editor AI non disponibile.")
        backend = backend_cls(str(dsn or "").strip(), POSTGRES_SCHEMA_EDITOR_AI)
        return cls(Path(json_root) / "editor_ai.json", structured_db=backend)

    def _detect_backend(self, structured_db: Any) -> str:
        if structured_db is None:
            return ""
        postgres_backend_cls = _postgres_backend_type()
        if postgres_backend_cls is not None and isinstance(structured_db, postgres_backend_cls):
            return "postgresql"
        kind = str(getattr(structured_db, "backend_kind", "") or "").lower()
        if kind == "postgresql":
            return "postgresql"
        if hasattr(structured_db, "conn"):
            return "sqlite"
        if hasattr(structured_db, "connection") and hasattr(structured_db, "raw_conn"):
            return "postgresql"
        return ""

    def _ensure_sql_schema(self) -> None:
        if self._backend == "sqlite":
            self.structured_db.conn.executescript(SQLITE_SCHEMA_EDITOR_AI.read_text(encoding="utf-8"))
            self.structured_db.conn.commit()
            return
        if self._backend == "postgresql":
            raw_conn = getattr(self.structured_db, "raw_conn", None)
            if raw_conn is not None:
                with raw_conn.cursor() as cur:
                    cur.execute(POSTGRES_SCHEMA_EDITOR_AI.read_text(encoding="utf-8"))
                raw_conn.commit()
                return
            connection = getattr(self.structured_db, "connection", None)
            if callable(connection):
                conn = connection()
                conn.executescript(POSTGRES_SCHEMA_EDITOR_AI.read_text(encoding="utf-8"))
                conn.commit()

    def _empty(self) -> dict[str, Any]:
        return {key: [] for key in STORE_KEYS}

    def _load_json(self) -> dict[str, Any]:
        if not self.json_path.exists():
            return self._empty()
        try:
            raw = json.loads(self.json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty()
        data = self._empty()
        if isinstance(raw, dict):
            for key in STORE_KEYS:
                value = raw.get(key, [])
                data[key] = value if isinstance(value, list) else []
        return data

    def _save_json(self) -> None:
        if self._backend:
            return
        self.json_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _conn(self):
        postgres_backend_cls = _postgres_backend_type()
        if (
            self._backend == "postgresql"
            and postgres_backend_cls is not None
            and isinstance(self.structured_db, postgres_backend_cls)
        ):
            return self.structured_db.connection()
        connection = getattr(self.structured_db, "connection", None)
        if self._backend == "postgresql" and callable(connection) and not hasattr(self.structured_db, "conn"):
            return connection()
        return self.structured_db.conn

    def _commit(self) -> None:
        if self._backend == "postgresql":
            raw_conn = getattr(self.structured_db, "raw_conn", None)
            if raw_conn is not None:
                raw_conn.commit()
            else:
                self._conn().commit()
        else:
            self._conn().commit()

    def _dict_row(self, row: Any) -> dict[str, Any]:
        return dict(row) if isinstance(row, sqlite3.Row) else dict(row or {})

    def create_record(self, record: AttoAIRecord) -> AttoAIRecord:
        if self._backend:
            self._conn().execute(
                """
                INSERT INTO fascicolo_editor_ai_atti (
                    id, tenant_id, fascicolo_id, tipo_atto, template_id, title, status,
                    editor_document_id, current_version_id, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.tenant_id,
                    record.fascicolo_id,
                    record.tipo_atto,
                    record.template_id,
                    record.title,
                    record.status,
                    record.editor_document_id,
                    record.current_version_id,
                    record.created_by,
                    record.created_at,
                    record.updated_at,
                ),
            )
            self._commit()
        else:
            self._data["records"].append(record.to_dict())
            self._save_json()
        return record

    def update_record(self, record: AttoAIRecord) -> AttoAIRecord:
        record.updated_at = utc_now()
        if self._backend:
            self._conn().execute(
                """
                UPDATE fascicolo_editor_ai_atti
                SET tipo_atto = ?, template_id = ?, title = ?, status = ?,
                    editor_document_id = ?, current_version_id = ?, updated_at = ?
                WHERE tenant_id = ? AND fascicolo_id = ? AND id = ?
                """,
                (
                    record.tipo_atto,
                    record.template_id,
                    record.title,
                    record.status,
                    record.editor_document_id,
                    record.current_version_id,
                    record.updated_at,
                    record.tenant_id,
                    record.fascicolo_id,
                    record.id,
                ),
            )
            self._commit()
        else:
            for index, item in enumerate(self._data["records"]):
                if item.get("tenant_id") == record.tenant_id and item.get("fascicolo_id") == record.fascicolo_id and item.get("id") == record.id:
                    self._data["records"][index] = record.to_dict()
                    break
            self._save_json()
        return record

    def get_record(self, tenant_id: str, fascicolo_id: str, atto_ai_id: str) -> AttoAIRecord | None:
        if self._backend:
            row = self._conn().execute(
                """
                SELECT * FROM fascicolo_editor_ai_atti
                WHERE tenant_id = ? AND fascicolo_id = ? AND id = ?
                """,
                (tenant_id, fascicolo_id, atto_ai_id),
            ).fetchone()
            return dataclass_from_dict(AttoAIRecord, self._dict_row(row)) if row else None
        for row in self._data["records"]:
            if row.get("tenant_id") == tenant_id and row.get("fascicolo_id") == fascicolo_id and row.get("id") == atto_ai_id:
                return dataclass_from_dict(AttoAIRecord, row)
        return None

    def get_record_by_editor_document(self, tenant_id: str, fascicolo_id: str, editor_document_id: str) -> AttoAIRecord | None:
        if self._backend:
            row = self._conn().execute(
                """
                SELECT * FROM fascicolo_editor_ai_atti
                WHERE tenant_id = ? AND fascicolo_id = ? AND editor_document_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (tenant_id, fascicolo_id, editor_document_id),
            ).fetchone()
            return dataclass_from_dict(AttoAIRecord, self._dict_row(row)) if row else None
        rows = [
            row
            for row in self._data["records"]
            if row.get("tenant_id") == tenant_id
            and row.get("fascicolo_id") == fascicolo_id
            and row.get("editor_document_id") == editor_document_id
        ]
        if not rows:
            return None
        return dataclass_from_dict(AttoAIRecord, sorted(rows, key=lambda item: item.get("created_at", ""), reverse=True)[0])

    def list_records(self, tenant_id: str, fascicolo_id: str) -> list[AttoAIRecord]:
        if self._backend:
            rows = self._conn().execute(
                """
                SELECT * FROM fascicolo_editor_ai_atti
                WHERE tenant_id = ? AND fascicolo_id = ?
                ORDER BY created_at DESC
                """,
                (tenant_id, fascicolo_id),
            ).fetchall()
            return [dataclass_from_dict(AttoAIRecord, self._dict_row(row)) for row in rows]
        rows = [
            dataclass_from_dict(AttoAIRecord, row)
            for row in self._data["records"]
            if row.get("tenant_id") == tenant_id and row.get("fascicolo_id") == fascicolo_id
        ]
        return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def create_version(self, version: AttoAIVersion) -> AttoAIVersion:
        if any(row.version_number == version.version_number for row in self.list_versions(version.tenant_id, version.fascicolo_id, version.atto_ai_id)):
            raise EditorAIValidationError("Numero versione gia' esistente per l'atto AI.")
        snapshot_json = json.dumps(version.editor_document_snapshot, ensure_ascii=False)
        if self._backend:
            self._conn().execute(
                """
                INSERT INTO fascicolo_editor_ai_versioni (
                    id, atto_ai_id, tenant_id, fascicolo_id, version_number, source,
                    editor_document_snapshot_json, docx_path, pdf_path, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version.id,
                    version.atto_ai_id,
                    version.tenant_id,
                    version.fascicolo_id,
                    version.version_number,
                    version.source,
                    snapshot_json,
                    version.docx_path,
                    version.pdf_path,
                    version.created_by,
                    version.created_at,
                ),
            )
            self._commit()
        else:
            self._data["versions"].append(version.to_dict())
            self._save_json()
        return version

    def list_versions(self, tenant_id: str, fascicolo_id: str, atto_ai_id: str) -> list[AttoAIVersion]:
        if self._backend:
            rows = self._conn().execute(
                """
                SELECT * FROM fascicolo_editor_ai_versioni
                WHERE tenant_id = ? AND fascicolo_id = ? AND atto_ai_id = ?
                ORDER BY version_number ASC
                """,
                (tenant_id, fascicolo_id, atto_ai_id),
            ).fetchall()
            return [_version_from_row(self._dict_row(row)) for row in rows]
        rows = [
            dataclass_from_dict(AttoAIVersion, row)
            for row in self._data["versions"]
            if row.get("tenant_id") == tenant_id
            and row.get("fascicolo_id") == fascicolo_id
            and row.get("atto_ai_id") == atto_ai_id
        ]
        return sorted(rows, key=lambda item: item.version_number)

    def create_source(self, source: AttoAISource) -> AttoAISource:
        if self._backend:
            self._conn().execute(
                """
                INSERT INTO fascicolo_editor_ai_fonti (
                    id, atto_ai_id, source_type, source_id, document_id,
                    page_number, quote, sha256, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.id,
                    source.atto_ai_id,
                    source.source_type,
                    source.source_id,
                    source.document_id,
                    source.page_number,
                    source.quote,
                    source.sha256,
                    source.reason,
                ),
            )
            self._commit()
        else:
            self._data["sources"].append(source.to_dict())
            self._save_json()
        return source

    def list_sources(self, atto_ai_id: str) -> list[AttoAISource]:
        if self._backend:
            rows = self._conn().execute(
                "SELECT * FROM fascicolo_editor_ai_fonti WHERE atto_ai_id = ? ORDER BY id ASC",
                (atto_ai_id,),
            ).fetchall()
            return [dataclass_from_dict(AttoAISource, self._dict_row(row)) for row in rows]
        return [dataclass_from_dict(AttoAISource, row) for row in self._data["sources"] if row.get("atto_ai_id") == atto_ai_id]

    def create_edit_proposal(self, proposal: AttoAIEditProposal) -> AttoAIEditProposal:
        if self._backend:
            self._conn().execute(
                """
                INSERT INTO fascicolo_editor_ai_modifiche (
                    id, atto_ai_id, version_id, status, operation_type, target_block_id,
                    find_text, replace_text, insert_text, reason, created_by, created_at,
                    resolved_by, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.id,
                    proposal.atto_ai_id,
                    proposal.version_id,
                    proposal.status,
                    proposal.operation_type,
                    proposal.target_block_id,
                    proposal.find_text,
                    proposal.replace_text,
                    proposal.insert_text,
                    proposal.reason,
                    proposal.created_by,
                    proposal.created_at,
                    proposal.resolved_by,
                    proposal.resolved_at,
                ),
            )
            self._commit()
        else:
            self._data["edit_proposals"].append(proposal.to_dict())
            self._save_json()
        return proposal

    def get_edit_proposal(self, atto_ai_id: str, edit_id: str) -> AttoAIEditProposal | None:
        proposals = self.list_edit_proposals(atto_ai_id)
        return next((proposal for proposal in proposals if proposal.id == edit_id), None)

    def list_edit_proposals(self, atto_ai_id: str, *, status: str | None = None) -> list[AttoAIEditProposal]:
        if self._backend:
            sql = "SELECT * FROM fascicolo_editor_ai_modifiche WHERE atto_ai_id = ?"
            params: list[Any] = [atto_ai_id]
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            rows = self._conn().execute(sql, tuple(params)).fetchall()
            return [dataclass_from_dict(AttoAIEditProposal, self._dict_row(row)) for row in rows]
        rows = [
            dataclass_from_dict(AttoAIEditProposal, row)
            for row in self._data["edit_proposals"]
            if row.get("atto_ai_id") == atto_ai_id and (not status or row.get("status") == status)
        ]
        return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def update_edit_proposal(self, proposal: AttoAIEditProposal) -> AttoAIEditProposal:
        if self._backend:
            self._conn().execute(
                """
                UPDATE fascicolo_editor_ai_modifiche
                SET status = ?, resolved_by = ?, resolved_at = ?
                WHERE atto_ai_id = ? AND id = ?
                """,
                (proposal.status, proposal.resolved_by, proposal.resolved_at, proposal.atto_ai_id, proposal.id),
            )
            self._commit()
        else:
            for index, item in enumerate(self._data["edit_proposals"]):
                if item.get("atto_ai_id") == proposal.atto_ai_id and item.get("id") == proposal.id:
                    self._data["edit_proposals"][index] = proposal.to_dict()
                    break
            self._save_json()
        return proposal

    def append_audit_event(self, event: dict[str, Any]) -> None:
        clean = dict(event or {})
        clean.pop("text", None)
        clean.pop("html", None)
        if self._backend:
            self._conn().execute(
                """
                INSERT INTO fascicolo_editor_ai_audit (
                    id, tenant_id, fascicolo_id, atto_ai_id, version_id,
                    editor_document_id, user_id, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean.get("id"),
                    clean.get("tenant_id"),
                    clean.get("fascicolo_id"),
                    clean.get("atto_ai_id") or None,
                    clean.get("version_id") or None,
                    clean.get("editor_document_id") or None,
                    clean.get("user_id"),
                    clean.get("event_type"),
                    json.dumps(
                        {
                            "status": clean.get("status", ""),
                            "error_code": clean.get("error_code", ""),
                            "error_message": clean.get("error_message", ""),
                            "payload": clean.get("payload", {}),
                        },
                        ensure_ascii=False,
                    ),
                    clean.get("timestamp") or utc_now(),
                ),
            )
            self._commit()
        else:
            self._data["audit_events"].append(clean)
            self._save_json()

    def close(self) -> None:
        closer = getattr(self.structured_db, "close", None)
        if callable(closer):
            closer()


def _version_from_row(row: dict[str, Any]) -> AttoAIVersion:
    payload = dict(row)
    snapshot_raw = payload.pop("editor_document_snapshot_json", "{}")
    if isinstance(snapshot_raw, str):
        try:
            snapshot = json.loads(snapshot_raw)
        except json.JSONDecodeError:
            snapshot = {}
    else:
        snapshot = snapshot_raw if isinstance(snapshot_raw, dict) else {}
    payload["editor_document_snapshot"] = snapshot
    return dataclass_from_dict(AttoAIVersion, payload)
