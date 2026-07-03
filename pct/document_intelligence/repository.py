"""Repository tenant-aware per Documenti AI Fascicolo."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pct.postgres_runtime_support import PostgresRepositoryBackend

from .models import (
    DocumentAIPageText,
    DocumentAIRecord,
    DocumentAISearchResult,
    DocumentAIText,
    DocumentAIVersion,
    dataclass_from_dict,
    utc_now,
)
from .security import DocumentAIValidationError, safe_join_under_root


STORE_KEYS = ("documents", "versions", "texts", "audit_events")
SQLITE_SCHEMA_DOCUMENTI_AI = Path(__file__).resolve().parents[1] / "sql" / "20260505_documenti_ai.sql"
POSTGRES_SCHEMA_DOCUMENTI_AI = Path(__file__).resolve().parents[1] / "sql" / "20260505_documenti_ai_postgres.sql"
SQL_DOCUMENT_AI_FILE_TYPES = (
    "pdf",
    "docx",
    "doc",
    "txt",
    "xml",
    "json",
    "csv",
    "html",
    "htm",
    "rtf",
    "odt",
    "xlsx",
    "xls",
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
    "bmp",
    "gif",
    "eml",
    "msg",
    "zip",
    "p7m",
    "pm7",
    "bin",
)


def _postgres_backend_type() -> type[Any] | None:
    return PostgresRepositoryBackend if isinstance(PostgresRepositoryBackend, type) else None


class _ManagedSqliteBackend:
    backend_kind = "sqlite"

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=30000")

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()


class DocumentAIRepository:
    """Persistenza filtrata sempre per tenant e fascicolo.

    Il runtime JSON resta nel data root dello studio. Se lo storage strutturato
    e' attivo, il repository applica anche le migrazioni e usa le tabelle SQL.
    """

    def __init__(self, json_path: str | Path, storage_root: str | Path, structured_db: Any = None):
        self.json_path = Path(json_path)
        self.storage_root = Path(storage_root)
        self.structured_db = structured_db
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self._backend = self._detect_backend(structured_db)
        if self._backend:
            self._ensure_sql_schema()
        self._data = self._load_json()

    @property
    def backend_kind(self) -> str:
        return self._backend or "json"

    @classmethod
    def from_fascicoli_db(
        cls,
        fascicoli_db_path: str | Path,
        *,
        structured_db: Any = None,
    ) -> "DocumentAIRepository":
        base = Path(fascicoli_db_path).resolve().parent / "documenti_ai"
        return cls(base / "documenti_ai.json", base, structured_db=structured_db)

    @classmethod
    def from_sqlite_db(
        cls,
        db_path: str | Path,
        *,
        storage_root: str | Path | None = None,
    ) -> "DocumentAIRepository":
        db = Path(db_path)
        root = Path(storage_root) if storage_root is not None else db.resolve().parent / "documenti_ai"
        backend = _ManagedSqliteBackend(db)
        return cls(root / "documenti_ai.json", root, structured_db=backend)

    @classmethod
    def from_postgres_dsn(
        cls,
        dsn: str,
        *,
        storage_root: str | Path,
        schema_path: str | Path | None = None,
    ) -> "DocumentAIRepository":
        backend_cls = _postgres_backend_type()
        if backend_cls is None:
            raise RuntimeError("Backend PostgreSQL documentale non disponibile.")
        backend = backend_cls(str(dsn or "").strip(), schema_path or POSTGRES_SCHEMA_DOCUMENTI_AI)
        root = Path(storage_root)
        return cls(root / "documenti_ai.json", root, structured_db=backend)

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

    def _migration_sql(self, filename: str) -> str:
        if filename.endswith("_postgres.sql"):
            return POSTGRES_SCHEMA_DOCUMENTI_AI.read_text(encoding="utf-8")
        return SQLITE_SCHEMA_DOCUMENTI_AI.read_text(encoding="utf-8")

    def _ensure_sql_schema(self) -> None:
        if self._backend == "sqlite":
            conn = self.structured_db.conn
            conn.executescript(self._migration_sql("20260505_documenti_ai.sql"))
            self._ensure_sqlite_file_type_constraint(conn)
            conn.executescript(self._migration_sql("20260505_documenti_ai.sql"))
            conn.commit()
        elif self._backend == "postgresql":
            raw_conn = getattr(self.structured_db, "raw_conn", None)
            if raw_conn is not None:
                with raw_conn.cursor() as cur:
                    cur.execute(self._migration_sql("20260505_documenti_ai_postgres.sql"))
                raw_conn.commit()
                return
            connection = getattr(self.structured_db, "connection", None)
            if not callable(connection):
                return
            conn = connection()
            conn.executescript(self._migration_sql("20260505_documenti_ai_postgres.sql"))
            conn.commit()

    def _ensure_sqlite_file_type_constraint(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'fascicolo_documenti_ai'
            """
        ).fetchone()
        create_sql = str(row[0] if row else "")
        if all(f"'{file_type}'" in create_sql for file_type in SQL_DOCUMENT_AI_FILE_TYPES):
            return

        conn.commit()
        file_types_sql = ", ".join(f"'{file_type}'" for file_type in SQL_DOCUMENT_AI_FILE_TYPES)
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.execute("BEGIN")
            conn.execute(
                f"""
                CREATE TABLE fascicolo_documenti_ai__file_type_migration (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    fascicolo_id TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    safe_filename TEXT NOT NULL,
                    file_type TEXT NOT NULL CHECK (file_type IN ({file_types_sql})),
                    mime_type TEXT,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('uploaded', 'processing', 'ready', 'error', 'archived')),
                    current_version_id TEXT,
                    page_count INTEGER,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO fascicolo_documenti_ai__file_type_migration (
                    id, tenant_id, fascicolo_id, original_filename, safe_filename, file_type,
                    mime_type, size_bytes, sha256, status, current_version_id, page_count,
                    created_by, created_at, updated_at
                )
                SELECT
                    id, tenant_id, fascicolo_id, original_filename, safe_filename, file_type,
                    mime_type, size_bytes, sha256, status, current_version_id, page_count,
                    created_by, created_at, updated_at
                FROM fascicolo_documenti_ai
                """
            )
            conn.execute("DROP TABLE fascicolo_documenti_ai")
            conn.execute("ALTER TABLE fascicolo_documenti_ai__file_type_migration RENAME TO fascicolo_documenti_ai")
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys=ON")

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

    def list_documents(self, tenant_id: str, fascicolo_id: str, user_context: object | None = None) -> list[DocumentAIRecord]:
        if self._backend:
            rows = self._conn().execute(
                """
                SELECT * FROM fascicolo_documenti_ai
                WHERE tenant_id = ? AND fascicolo_id = ?
                ORDER BY created_at DESC, original_filename ASC
                """,
                (tenant_id, fascicolo_id),
            ).fetchall()
            return [dataclass_from_dict(DocumentAIRecord, self._dict_row(row)) for row in rows]
        rows = [
            dataclass_from_dict(DocumentAIRecord, row)
            for row in self._data["documents"]
            if row.get("tenant_id") == tenant_id and row.get("fascicolo_id") == fascicolo_id
        ]
        return sorted(rows, key=lambda item: (item.created_at, item.original_filename), reverse=True)

    def get_document(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        user_context: object | None = None,
    ) -> DocumentAIRecord | None:
        if self._backend:
            row = self._conn().execute(
                """
                SELECT * FROM fascicolo_documenti_ai
                WHERE tenant_id = ? AND fascicolo_id = ? AND id = ?
                """,
                (tenant_id, fascicolo_id, document_id),
            ).fetchone()
            return dataclass_from_dict(DocumentAIRecord, self._dict_row(row)) if row else None
        for row in self._data["documents"]:
            if row.get("tenant_id") == tenant_id and row.get("fascicolo_id") == fascicolo_id and row.get("id") == document_id:
                return dataclass_from_dict(DocumentAIRecord, row)
        return None

    def create_document_record(self, record: DocumentAIRecord) -> DocumentAIRecord:
        if self._backend:
            self._conn().execute(
                """
                INSERT INTO fascicolo_documenti_ai (
                    id, tenant_id, fascicolo_id, original_filename, safe_filename, file_type,
                    mime_type, size_bytes, sha256, status, current_version_id, page_count,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.tenant_id,
                    record.fascicolo_id,
                    record.original_filename,
                    record.safe_filename,
                    record.file_type,
                    record.mime_type,
                    record.size_bytes,
                    record.sha256,
                    record.status,
                    record.current_version_id,
                    record.page_count,
                    record.created_by,
                    record.created_at,
                    record.updated_at,
                ),
            )
            self._commit()
        else:
            self._data["documents"].append(record.to_dict())
            self._save_json()
        return record

    def create_document(self, record: DocumentAIRecord) -> DocumentAIRecord:
        return self.create_document_record(record)

    def create_version(self, version: DocumentAIVersion) -> DocumentAIVersion:
        existing = self.list_versions(version.tenant_id, version.fascicolo_id, version.document_id)
        if any(row.version_number == version.version_number for row in existing):
            raise DocumentAIValidationError("Numero versione gia' esistente per il documento.")
        if self._backend:
            self._conn().execute(
                """
                INSERT INTO fascicolo_documenti_ai_versioni (
                    id, tenant_id, fascicolo_id, document_id, version_number, source,
                    storage_path, extracted_text_path, pdf_preview_path, sha256,
                    created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version.id,
                    version.tenant_id,
                    version.fascicolo_id,
                    version.document_id,
                    version.version_number,
                    version.source,
                    version.storage_path,
                    version.extracted_text_path,
                    version.pdf_preview_path,
                    version.sha256,
                    version.created_by,
                    version.created_at,
                ),
            )
            self._commit()
        else:
            self._data["versions"].append(version.to_dict())
            self._save_json()
        return version

    def list_versions(self, tenant_id: str, fascicolo_id: str, document_id: str) -> list[DocumentAIVersion]:
        if self._backend:
            rows = self._conn().execute(
                """
                SELECT * FROM fascicolo_documenti_ai_versioni
                WHERE tenant_id = ? AND fascicolo_id = ? AND document_id = ?
                ORDER BY version_number ASC
                """,
                (tenant_id, fascicolo_id, document_id),
            ).fetchall()
            return [dataclass_from_dict(DocumentAIVersion, self._dict_row(row)) for row in rows]
        rows = [
            dataclass_from_dict(DocumentAIVersion, row)
            for row in self._data["versions"]
            if row.get("tenant_id") == tenant_id
            and row.get("fascicolo_id") == fascicolo_id
            and row.get("document_id") == document_id
        ]
        return sorted(rows, key=lambda item: item.version_number)

    def get_version(self, tenant_id: str, fascicolo_id: str, document_id: str, version_id: str) -> DocumentAIVersion | None:
        for version in self.list_versions(tenant_id, fascicolo_id, document_id):
            if version.id == version_id:
                return version
        return None

    def set_current_version(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        version_id: str | None,
        *,
        status: str | None = None,
        page_count: int | None = None,
    ) -> None:
        updated_at = utc_now()
        if self._backend:
            self._conn().execute(
                """
                UPDATE fascicolo_documenti_ai
                SET current_version_id = COALESCE(?, current_version_id),
                    status = COALESCE(?, status),
                    page_count = ?,
                    updated_at = ?
                WHERE tenant_id = ? AND fascicolo_id = ? AND id = ?
                """,
                (version_id, status, page_count, updated_at, tenant_id, fascicolo_id, document_id),
            )
            self._commit()
            return
        for row in self._data["documents"]:
            if row.get("tenant_id") == tenant_id and row.get("fascicolo_id") == fascicolo_id and row.get("id") == document_id:
                if version_id is not None:
                    row["current_version_id"] = version_id
                if status is not None:
                    row["status"] = status
                row["page_count"] = page_count
                row["updated_at"] = updated_at
                break
        self._save_json()

    def save_extracted_text(self, extracted: DocumentAIText, *, extracted_text_path: str | None = None) -> DocumentAIText:
        row = extracted.to_dict()
        row["pages_json"] = [page.to_dict() for page in extracted.pages]
        row["warnings_json"] = list(extracted.warnings)
        if self._backend:
            conn = self._conn()
            conn.execute(
                "DELETE FROM fascicolo_documenti_ai_testi WHERE tenant_id = ? AND fascicolo_id = ? AND version_id = ?",
                (extracted.tenant_id, extracted.fascicolo_id, extracted.version_id),
            )
            conn.execute(
                """
                INSERT INTO fascicolo_documenti_ai_testi (
                    tenant_id, fascicolo_id, document_id, version_id,
                    extraction_engine, text, pages_json, warnings_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    extracted.tenant_id,
                    extracted.fascicolo_id,
                    extracted.document_id,
                    extracted.version_id,
                    extracted.extraction_engine,
                    extracted.text,
                    json.dumps(row["pages_json"], ensure_ascii=False),
                    json.dumps(row["warnings_json"], ensure_ascii=False),
                    extracted.created_at,
                ),
            )
            if extracted_text_path:
                conn.execute(
                    """
                    UPDATE fascicolo_documenti_ai_versioni
                    SET extracted_text_path = ?
                    WHERE tenant_id = ? AND fascicolo_id = ? AND document_id = ? AND id = ?
                    """,
                    (
                        extracted_text_path,
                        extracted.tenant_id,
                        extracted.fascicolo_id,
                        extracted.document_id,
                        extracted.version_id,
                    ),
                )
            self._commit()
        else:
            self._data["texts"] = [
                item
                for item in self._data["texts"]
                if not (
                    item.get("tenant_id") == extracted.tenant_id
                    and item.get("fascicolo_id") == extracted.fascicolo_id
                    and item.get("version_id") == extracted.version_id
                )
            ]
            self._data["texts"].append(row)
            if extracted_text_path:
                for version in self._data["versions"]:
                    if version.get("id") == extracted.version_id and version.get("document_id") == extracted.document_id:
                        version["extracted_text_path"] = extracted_text_path
            self._save_json()
        return extracted

    def get_extracted_text(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        version_id: str | None = None,
    ) -> DocumentAIText | None:
        if version_id is None:
            document = self.get_document(tenant_id, fascicolo_id, document_id)
            version_id = document.current_version_id if document else None
        if not version_id:
            return None
        if self._backend:
            row = self._conn().execute(
                """
                SELECT * FROM fascicolo_documenti_ai_testi
                WHERE tenant_id = ? AND fascicolo_id = ? AND document_id = ? AND version_id = ?
                """,
                (tenant_id, fascicolo_id, document_id, version_id),
            ).fetchone()
            if not row:
                return None
            payload = self._dict_row(row)
            payload["pages"] = _pages_from_json(payload.pop("pages_json", "[]"))
            payload["warnings"] = _list_from_json(payload.pop("warnings_json", "[]"))
            payload.pop("id", None)
            return dataclass_from_dict(DocumentAIText, payload)
        for row in self._data["texts"]:
            if (
                row.get("tenant_id") == tenant_id
                and row.get("fascicolo_id") == fascicolo_id
                and row.get("document_id") == document_id
                and row.get("version_id") == version_id
            ):
                payload = dict(row)
                payload["pages"] = _pages_from_json(payload.get("pages") or payload.get("pages_json") or [])
                payload["warnings"] = list(payload.get("warnings") or payload.get("warnings_json") or [])
                return dataclass_from_dict(DocumentAIText, payload)
        return None

    def search_extracted_text(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        query: str,
        user_context: object | None = None,
        max_results: int = 20,
    ) -> list[DocumentAISearchResult]:
        needle = str(query or "").strip()
        if not needle:
            return []
        extracted = self.get_extracted_text(tenant_id, fascicolo_id, document_id)
        if not extracted:
            return []
        max_results = max(1, min(int(max_results or 20), 50))
        results: list[DocumentAISearchResult] = []
        if extracted.pages:
            for page in extracted.pages:
                results.extend(_search_in_text(extracted.document_id, extracted.version_id, page.text, needle, max_results, page.page_number))
                if len(results) >= max_results:
                    return results[:max_results]
        else:
            results = _search_in_text(extracted.document_id, extracted.version_id, extracted.text, needle, max_results, None)
        return results[:max_results]

    def mark_status(self, tenant_id: str, fascicolo_id: str, document_id: str, status: str) -> None:
        document = self.get_document(tenant_id, fascicolo_id, document_id)
        self.set_current_version(
            tenant_id,
            fascicolo_id,
            document_id,
            document.current_version_id if document else None,
            status=status,
            page_count=document.page_count if document else None,
        )

    def update_document_status(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        self.mark_status(tenant_id, fascicolo_id, document_id, status)

    def append_audit_event(self, event: dict[str, Any]) -> None:
        clean = dict(event or {})
        clean.pop("text", None)
        if self._backend:
            payload = {
                "sha256": clean.get("sha256", ""),
                "filename": clean.get("filename", ""),
                "status": clean.get("status", ""),
                "error_code": clean.get("error_code", ""),
                "error_message": clean.get("error_message", ""),
                "payload": clean.get("payload", {}),
            }
            self._conn().execute(
                """
                INSERT INTO fascicolo_documenti_ai_audit (
                    id, tenant_id, fascicolo_id, document_id, version_id,
                    user_id, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean.get("id"),
                    clean.get("tenant_id"),
                    clean.get("fascicolo_id"),
                    clean.get("document_id") or None,
                    clean.get("version_id") or None,
                    clean.get("user_id"),
                    clean.get("event_type"),
                    json.dumps(payload, ensure_ascii=False),
                    clean.get("timestamp") or utc_now(),
                ),
            )
            self._commit()
        else:
            self._data["audit_events"].append(clean)
            self._save_json()

    def audit_summary(self, tenant_id: str, fascicolo_id: str, document_id: str) -> dict[str, str | None]:
        if self._backend:
            row = self._conn().execute(
                """
                SELECT event_type, created_at FROM fascicolo_documenti_ai_audit
                WHERE tenant_id = ? AND fascicolo_id = ? AND document_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (tenant_id, fascicolo_id, document_id),
            ).fetchone()
            return {"last_event": row["event_type"], "last_event_at": row["created_at"]} if row else {"last_event": None, "last_event_at": None}
        events = [
            row
            for row in self._data["audit_events"]
            if row.get("tenant_id") == tenant_id and row.get("fascicolo_id") == fascicolo_id and row.get("document_id") == document_id
        ]
        if not events:
            return {"last_event": None, "last_event_at": None}
        last = sorted(events, key=lambda item: item.get("timestamp", ""), reverse=True)[0]
        return {"last_event": last.get("event_type"), "last_event_at": last.get("timestamp")}

    def write_blob(self, relative_path: str, content: bytes) -> str:
        target = safe_join_under_root(self.storage_root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return relative_path

    def write_text_blob(self, relative_path: str, text: str) -> str:
        target = safe_join_under_root(self.storage_root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return relative_path

    def storage_stats(self, tenant_id: str | None = None, fascicolo_id: str | None = None) -> dict[str, Any]:
        if self._backend:
            where = []
            params: list[Any] = []
            if tenant_id:
                where.append("tenant_id = ?")
                params.append(tenant_id)
            if fascicolo_id:
                where.append("fascicolo_id = ?")
                params.append(fascicolo_id)
            suffix = f" WHERE {' AND '.join(where)}" if where else ""
            conn = self._conn()
            return {
                "backend_kind": self.backend_kind,
                "documents": _count_sql(conn, f"SELECT COUNT(*) FROM fascicolo_documenti_ai{suffix}", params),
                "versions": _count_sql(conn, f"SELECT COUNT(*) FROM fascicolo_documenti_ai_versioni{suffix}", params),
                "texts": _count_sql(conn, f"SELECT COUNT(*) FROM fascicolo_documenti_ai_testi{suffix}", params),
                "audit_events": _count_sql(conn, f"SELECT COUNT(*) FROM fascicolo_documenti_ai_audit{suffix}", params),
            }
        rows = {
            "documents": self._data["documents"],
            "versions": self._data["versions"],
            "texts": self._data["texts"],
            "audit_events": self._data["audit_events"],
        }
        if tenant_id:
            rows = {key: [row for row in value if row.get("tenant_id") == tenant_id] for key, value in rows.items()}
        if fascicolo_id:
            rows = {key: [row for row in value if row.get("fascicolo_id") == fascicolo_id] for key, value in rows.items()}
        return {"backend_kind": self.backend_kind, **{key: len(value) for key, value in rows.items()}}

    def close(self) -> None:
        closer = getattr(self.structured_db, "close", None)
        if callable(closer):
            closer()


def _pages_from_json(raw: Any) -> list[DocumentAIPageText]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    if not isinstance(raw, list):
        return []
    pages: list[DocumentAIPageText] = []
    for page in raw:
        if not isinstance(page, dict):
            continue
        page_number = page.get("page_number")
        if page_number is not None and not str(page_number).isdigit():
            continue
        pages.append(dataclass_from_dict(DocumentAIPageText, page))
    return pages


def _list_from_json(raw: Any) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw]


def _count_sql(conn: Any, sql: str, params: list[Any]) -> int:
    row = conn.execute(sql, tuple(params)).fetchone()
    if row is None:
        return 0
    if isinstance(row, sqlite3.Row):
        return int(row[0] or 0)
    if isinstance(row, dict):
        return int(next(iter(row.values()), 0) or 0)
    return int(row[0] or 0)


def _search_in_text(
    document_id: str,
    version_id: str,
    text: str,
    needle: str,
    max_results: int,
    page_number: int | None,
) -> list[DocumentAISearchResult]:
    haystack = text or ""
    lowered = haystack.lower()
    lowered_needle = needle.lower()
    results: list[DocumentAISearchResult] = []
    start = 0
    while len(results) < max_results:
        index = lowered.find(lowered_needle, start)
        if index < 0:
            break
        end = index + len(needle)
        snippet_start = max(0, index - 90)
        snippet_end = min(len(haystack), end + 90)
        snippet = haystack[snippet_start:snippet_end].strip()
        results.append(
            DocumentAISearchResult(
                document_id=document_id,
                version_id=version_id,
                page_number=page_number,
                snippet=snippet,
                start_offset=index,
                end_offset=end,
            )
        )
        start = end
    return results


DocumentIntelligenceRepository = DocumentAIRepository
