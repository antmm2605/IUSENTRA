"""Repository tenant-aware per Documenti AI Fascicolo."""

from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from typing import Any

from pct.postgres_runtime_support import PostgresRepositoryBackend

from .models import (
    DocumentCatalogAssignment,
    DocumentCatalogCandidate,
    DocumentCatalogEvidence,
    DocumentCatalogReview,
    DocumentAIPageText,
    DocumentAIRecord,
    DocumentAISearchResult,
    DocumentAIText,
    DocumentAIVersion,
    dataclass_from_dict,
    new_id,
    utc_now,
)
from .security import DocumentAIValidationError, safe_join_under_root


STORE_KEYS = ("documents", "versions", "texts", "audit_events")
SQLITE_SCHEMA_DOCUMENTI_AI = Path(__file__).resolve().parents[1] / "sql" / "20260505_documenti_ai.sql"
POSTGRES_SCHEMA_DOCUMENTI_AI = Path(__file__).resolve().parents[1] / "sql" / "20260505_documenti_ai_postgres.sql"
SQLITE_SCHEMA_DOCUMENT_CATALOG = Path(__file__).resolve().parents[1] / "sql" / "20260824_fascicolo_document_catalog.sql"
POSTGRES_SCHEMA_DOCUMENT_CATALOG = Path(__file__).resolve().parents[1] / "sql" / "20260824_fascicolo_document_catalog_postgres.sql"
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
        self._catalog_commit_batch_depth = 0
        self._catalog_commit_batch_requested = False
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

    def _catalog_migration_sql(self) -> str:
        schema = POSTGRES_SCHEMA_DOCUMENT_CATALOG if self._backend == "postgresql" else SQLITE_SCHEMA_DOCUMENT_CATALOG
        return schema.read_text(encoding="utf-8")

    def _ensure_sql_schema(self) -> None:
        if self._backend == "sqlite":
            conn = self.structured_db.conn
            conn.executescript(self._migration_sql("20260505_documenti_ai.sql"))
            self._ensure_sqlite_file_type_constraint(conn)
            conn.executescript(self._migration_sql("20260505_documenti_ai.sql"))
            conn.executescript(self._catalog_migration_sql())
            self._ensure_sqlite_catalog_review_history_schema(conn)
            conn.commit()
        elif self._backend == "postgresql":
            raw_conn = getattr(self.structured_db, "raw_conn", None)
            if raw_conn is not None:
                with raw_conn.cursor() as cur:
                    cur.execute(self._migration_sql("20260505_documenti_ai_postgres.sql"))
                    cur.execute(self._catalog_migration_sql())
                raw_conn.commit()
                return
            connection = getattr(self.structured_db, "connection", None)
            if not callable(connection):
                return
            conn = connection()
            conn.executescript(self._migration_sql("20260505_documenti_ai_postgres.sql"))
            conn.executescript(self._catalog_migration_sql())
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

    def _ensure_sqlite_catalog_review_history_schema(self, conn: sqlite3.Connection) -> None:
        """Rimuove il vecchio vincolo che impediva lo storico delle revisioni.

        Le prime build della catalogazione usavano per errore
        ``UNIQUE(assignment_id, state)``. Una seconda revisione risolta dello
        stesso documento non può quindi essere scartata: ricreiamo soltanto la
        tabella figlia, copiando tutti i record e mantenendo il vincolo FK.
        """

        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'document_catalog_reviews'"
        ).fetchone()
        create_sql = str(row[0] if row else "").upper().replace("\n", " ")
        if "UNIQUE (ASSIGNMENT_ID, STATE)" not in create_sql:
            return
        conn.commit()
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.execute("BEGIN")
            conn.execute(
                """
                CREATE TABLE document_catalog_reviews__history_migration (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    fascicolo_id TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('open', 'resolved', 'dismissed')),
                    reason_code TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    resolved_by TEXT,
                    resolution_note TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY (assignment_id) REFERENCES document_catalog_assignments(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                INSERT INTO document_catalog_reviews__history_migration (
                    id, tenant_id, fascicolo_id, assignment_id, state, reason_code,
                    reason, resolved_by, resolution_note, created_at, resolved_at
                )
                SELECT id, tenant_id, fascicolo_id, assignment_id, state, reason_code,
                       reason, resolved_by, resolution_note, created_at, resolved_at
                FROM document_catalog_reviews
                """
            )
            conn.execute("DROP TABLE document_catalog_reviews")
            conn.execute("ALTER TABLE document_catalog_reviews__history_migration RENAME TO document_catalog_reviews")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_catalog_reviews_tenant_fascicolo_state
                ON document_catalog_reviews (tenant_id, fascicolo_id, state, created_at)
                """
            )
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
        if self._catalog_commit_batch_depth:
            self._catalog_commit_batch_requested = True
            return
        if self._backend == "postgresql":
            raw_conn = getattr(self.structured_db, "raw_conn", None)
            if raw_conn is not None:
                raw_conn.commit()
            else:
                self._conn().commit()
        else:
            self._conn().commit()

    @contextmanager
    def catalog_write_batch(self):
        """Raggruppa i commit del catalogo in una transazione SQL.

        Un fascicolo può avere molte fonti, evidenze e documenti: il batch
        conserva le singole scritture e l'audit, ma evita che ciascuna apra un
        fsync separato. Le letture idempotenti non richiedono alcun commit.
        """

        if not self._backend:
            yield
            return
        outermost = self._catalog_commit_batch_depth == 0
        if outermost:
            self._catalog_commit_batch_requested = False
        self._catalog_commit_batch_depth += 1
        try:
            yield
        except Exception:
            self._catalog_commit_batch_depth -= 1
            if outermost:
                self._catalog_commit_batch_requested = False
                raw_conn = getattr(self.structured_db, "raw_conn", None)
                (raw_conn or self._conn()).rollback()
            raise
        else:
            self._catalog_commit_batch_depth -= 1
            if outermost and self._catalog_commit_batch_requested:
                self._catalog_commit_batch_requested = False
                self._commit()

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

    # Catalogazione documentale: queste operazioni richiedono SQL. Il mirror JSON
    # di Document AI non può diventare fonte di verità per decisioni sul fascicolo.
    def _require_catalog_sql(self) -> None:
        if not self._backend:
            raise DocumentAIValidationError(
                "Catalogazione non disponibile: l'archivio SQL dello studio deve essere attivo."
            )

    def ensure_catalog_rule_set(
        self,
        *,
        tenant_id: str,
        resolver_version: str,
        registry_version: str,
        description: str,
    ) -> str:
        self._require_catalog_sql()
        conn = self._conn()
        row = conn.execute(
            """
            SELECT id FROM document_catalog_rule_sets
            WHERE tenant_id = ? AND resolver_version = ? AND registry_version = ?
            """,
            (tenant_id, resolver_version, registry_version),
        ).fetchone()
        if row:
            return str(self._dict_row(row).get("id") or "")
        rule_set_id = new_id("catalog-rules")
        conn.execute(
            """
            INSERT INTO document_catalog_rule_sets (
                id, resolver_version, registry_version, tenant_id, description, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (rule_set_id, resolver_version, registry_version, tenant_id, description, utc_now()),
        )
        self._commit()
        return rule_set_id

    def upsert_catalog_source_snapshot(
        self,
        *,
        tenant_id: str,
        rule_set_id: str,
        profile_id: str,
        source_id: str,
        official_url: str,
        verification_status: str,
        snapshot_sha256: str | None,
        last_verified_at: str | None,
        source_metadata: dict[str, Any] | None = None,
    ) -> None:
        self._require_catalog_sql()
        conn = self._conn()
        now = utc_now()
        row = conn.execute(
            """
            SELECT * FROM document_catalog_source_snapshots
            WHERE tenant_id = ? AND rule_set_id = ? AND profile_id = ? AND source_id = ?
            """,
            (tenant_id, rule_set_id, profile_id, source_id),
        ).fetchone()
        metadata_json = json.dumps(dict(source_metadata or {}), ensure_ascii=False)
        if row:
            existing = self._dict_row(row)
            # Il catalogo delle fonti è versionato: quando lo snapshot è già
            # identico, non tocchiamo la riga né apriamo una transazione di
            # scrittura. In particolare, la lettura/apertura del fascicolo e
            # il refresh idempotente non devono generare decine di commit SQL.
            if (
                str(existing.get("official_url") or "") == official_url
                and str(existing.get("verification_status") or "") == verification_status
                and (existing.get("snapshot_sha256") or None) == (snapshot_sha256 or None)
                and (existing.get("last_verified_at") or None) == (last_verified_at or None)
                and str(existing.get("source_metadata_json") or "") == metadata_json
            ):
                return
            conn.execute(
                """
                UPDATE document_catalog_source_snapshots
                SET official_url = ?, verification_status = ?, snapshot_sha256 = ?,
                    last_verified_at = ?, source_metadata_json = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    official_url,
                    verification_status,
                    snapshot_sha256,
                    last_verified_at,
                    metadata_json,
                    now,
                    self._dict_row(row).get("id"),
                    tenant_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO document_catalog_source_snapshots (
                    id, tenant_id, rule_set_id, profile_id, source_id, official_url,
                    verification_status, snapshot_sha256, last_verified_at,
                    source_metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("catalog-source"), tenant_id, rule_set_id, profile_id, source_id,
                    official_url, verification_status, snapshot_sha256, last_verified_at,
                    metadata_json, now, now,
                ),
            )
        self._commit()

    def list_catalog_source_snapshots(
        self,
        tenant_id: str,
        rule_set_id: str,
    ) -> list[dict[str, Any]]:
        """Legge l'inventario delle fonti con una sola query SQL.

        Il resolver usa questo metodo per riconoscere uno snapshot già
        corrente prima di invocare l'upsert; l'apertura di un fascicolo non
        deve trasformarsi in una sequenza di query una-per-fonte.
        """

        self._require_catalog_sql()
        rows = self._conn().execute(
            """
            SELECT * FROM document_catalog_source_snapshots
            WHERE tenant_id = ? AND rule_set_id = ?
            """,
            (tenant_id, rule_set_id),
        ).fetchall()
        return [self._dict_row(row) for row in rows]

    def queue_catalog_job(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        document_ai_id: str | None,
        document_version_id: str | None,
        document_sha256: str,
        resolver_version: str,
        requested_by: str,
        retry: bool = False,
    ) -> dict[str, Any]:
        self._require_catalog_sql()
        conn = self._conn()
        now = utc_now()
        row = conn.execute(
            """
            SELECT * FROM document_catalog_jobs
            WHERE tenant_id = ? AND fascicolo_id = ? AND document_id = ?
              AND document_sha256 = ? AND resolver_version = ?
            """,
            (tenant_id, fascicolo_id, document_id, document_sha256, resolver_version),
        ).fetchone()
        if row:
            existing = self._dict_row(row)
            status = str(existing.get("status") or "")
            if retry and status in {"error", "review_required"}:
                conn.execute(
                    """
                    UPDATE document_catalog_jobs
                    SET status = 'queued', error_code = NULL, error_message = NULL,
                        requested_by = ?, requested_at = ?, updated_at = ?
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (requested_by, now, now, existing.get("id"), tenant_id),
                )
                self._commit()
                existing.update({"status": "queued", "updated_at": now})
            return existing
        job_id = new_id("catalog-job")
        conn.execute(
            """
            INSERT INTO document_catalog_jobs (
                id, tenant_id, fascicolo_id, document_id, document_ai_id, document_version_id,
                document_sha256, resolver_version, status, requested_by, requested_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)
            """,
            (
                job_id, tenant_id, fascicolo_id, document_id, document_ai_id, document_version_id,
                document_sha256, resolver_version, requested_by, now, now,
            ),
        )
        self._commit()
        return {"id": job_id, "status": "queued", "attempt_count": 0, "updated_at": now}

    def mark_catalog_job(
        self,
        *,
        tenant_id: str,
        job_id: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self._require_catalog_sql()
        if status not in {"queued", "processing", "completed", "review_required", "error"}:
            raise DocumentAIValidationError("Stato job di catalogazione non valido.")
        now = utc_now()
        started_at = now if status == "processing" else None
        completed_at = now if status in {"completed", "review_required", "error"} else None
        self._conn().execute(
            """
            UPDATE document_catalog_jobs
            SET status = ?, attempt_count = CASE WHEN ? = 'processing' THEN attempt_count + 1 ELSE attempt_count END,
                error_code = ?, error_message = ?, started_at = COALESCE(?, started_at),
                completed_at = ?, updated_at = ?
            WHERE id = ? AND tenant_id = ?
            """,
            (status, status, error_code, error_message, started_at, completed_at, now, job_id, tenant_id),
        )
        self._commit()

    def get_catalog_assignment(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        *,
        document_sha256: str | None = None,
    ) -> DocumentCatalogAssignment | None:
        self._require_catalog_sql()
        where = ["tenant_id = ?", "fascicolo_id = ?", "document_id = ?"]
        params: list[Any] = [tenant_id, fascicolo_id, document_id]
        if document_sha256:
            where.append("document_sha256 = ?")
            params.append(document_sha256)
        row = self._conn().execute(
            f"SELECT * FROM document_catalog_assignments WHERE {' AND '.join(where)} ORDER BY updated_at DESC LIMIT 1",
            tuple(params),
        ).fetchone()
        return self._catalog_assignment_from_row(row)

    def list_catalog_assignments(
        self,
        tenant_id: str,
        fascicolo_id: str,
        *,
        include_superseded: bool = False,
    ) -> list[DocumentCatalogAssignment]:
        self._require_catalog_sql()
        sql = "SELECT * FROM document_catalog_assignments WHERE tenant_id = ? AND fascicolo_id = ?"
        if not include_superseded:
            sql += " AND status NOT IN ('superseded', 'rejected')"
        sql += " ORDER BY updated_at DESC, document_label ASC"
        rows = self._conn().execute(sql, (tenant_id, fascicolo_id)).fetchall()
        return [assignment for row in rows if (assignment := self._catalog_assignment_from_row(row)) is not None]

    def save_catalog_assignment(
        self,
        assignment: DocumentCatalogAssignment,
        *,
        candidates: list[DocumentCatalogCandidate] | None = None,
        evidence: list[DocumentCatalogEvidence] | None = None,
        review: DocumentCatalogReview | None = None,
    ) -> DocumentCatalogAssignment:
        self._require_catalog_sql()
        current = self.get_catalog_assignment(
            assignment.tenant_id,
            assignment.fascicolo_id,
            assignment.document_id,
            document_sha256=assignment.document_sha256,
        )
        conn = self._conn()
        now = assignment.updated_at or utc_now()
        assignment.id = current.id if current else assignment.id or new_id("catalog-assignment")
        assignment.created_at = current.created_at if current else assignment.created_at or now
        assignment.created_by = current.created_by if current else assignment.created_by or assignment.updated_by or "catalog-pipeline"
        assignment.updated_at = now
        assignment.updated_by = assignment.updated_by or "catalog-pipeline"
        metadata_json = json.dumps(dict(assignment.metadata or {}), ensure_ascii=False)
        if current:
            conn.execute(
                """
                UPDATE document_catalog_assignments SET
                    document_ai_id = ?, document_version_id = ?, profile_id = ?, legal_area = ?, legal_branch = ?,
                    legal_subfamily = ?, jurisdiction = ?, rite = ?, proceeding_phase = ?, document_nature = ?,
                    document_label = ?, document_section = ?, deposit_role = ?, deposit_candidate = ?, status = ?,
                    confidence = ?, source_state = ?, resolver_version = ?, rule_set_id = ?, reason = ?,
                    metadata_json = ?, updated_by = ?, updated_at = ?, confirmed_at = ?
                WHERE id = ? AND tenant_id = ? AND fascicolo_id = ?
                """,
                (
                    assignment.document_ai_id, assignment.document_version_id, assignment.profile_id, assignment.legal_area,
                    assignment.legal_branch, assignment.legal_subfamily, assignment.jurisdiction, assignment.rite,
                    assignment.proceeding_phase, assignment.document_nature, assignment.document_label,
                    assignment.document_section, assignment.deposit_role, bool(assignment.deposit_candidate), assignment.status,
                    int(assignment.confidence), assignment.source_state, assignment.resolver_version, assignment.rule_set_id,
                    assignment.reason, metadata_json, assignment.updated_by, assignment.updated_at, assignment.confirmed_at,
                    assignment.id, assignment.tenant_id, assignment.fascicolo_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO document_catalog_assignments (
                    id, tenant_id, fascicolo_id, document_id, document_ai_id, document_version_id, document_sha256,
                    profile_id, legal_area, legal_branch, legal_subfamily, jurisdiction, rite, proceeding_phase,
                    document_nature, document_label, document_section, deposit_role, deposit_candidate, status,
                    confidence, source_state, resolver_version, rule_set_id, reason, metadata_json, created_by,
                    created_at, updated_by, updated_at, confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assignment.id, assignment.tenant_id, assignment.fascicolo_id, assignment.document_id,
                    assignment.document_ai_id, assignment.document_version_id, assignment.document_sha256,
                    assignment.profile_id, assignment.legal_area, assignment.legal_branch, assignment.legal_subfamily,
                    assignment.jurisdiction, assignment.rite, assignment.proceeding_phase, assignment.document_nature,
                    assignment.document_label, assignment.document_section, assignment.deposit_role,
                    bool(assignment.deposit_candidate), assignment.status, int(assignment.confidence), assignment.source_state,
                    assignment.resolver_version, assignment.rule_set_id, assignment.reason, metadata_json,
                    assignment.created_by, assignment.created_at, assignment.updated_by, assignment.updated_at,
                    assignment.confirmed_at,
                ),
            )
        conn.execute("DELETE FROM document_catalog_candidates WHERE assignment_id = ?", (assignment.id,))
        conn.execute("DELETE FROM document_catalog_evidence WHERE assignment_id = ?", (assignment.id,))
        for candidate in candidates or []:
            conn.execute(
                """
                INSERT INTO document_catalog_candidates (
                    id, tenant_id, fascicolo_id, assignment_id, rank_number, profile_id, document_nature,
                    document_label, document_section, deposit_role, confidence, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.id or new_id("catalog-candidate"), assignment.tenant_id, assignment.fascicolo_id,
                    assignment.id, int(candidate.rank_number), candidate.profile_id, candidate.document_nature,
                    candidate.document_label, candidate.document_section, candidate.deposit_role, int(candidate.confidence),
                    candidate.reason, candidate.created_at or now,
                ),
            )
        for item in evidence or []:
            conn.execute(
                """
                INSERT INTO document_catalog_evidence (
                    id, tenant_id, fascicolo_id, assignment_id, evidence_type, locator, excerpt,
                    weight, content_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id or new_id("catalog-evidence"), assignment.tenant_id, assignment.fascicolo_id,
                    assignment.id, item.evidence_type, item.locator, item.excerpt, int(item.weight),
                    item.content_sha256, item.created_at or now,
                ),
            )
        if review:
            conn.execute("DELETE FROM document_catalog_reviews WHERE assignment_id = ? AND state = 'open'", (assignment.id,))
            conn.execute(
                """
                INSERT INTO document_catalog_reviews (
                    id, tenant_id, fascicolo_id, assignment_id, state, reason_code, reason,
                    resolved_by, resolution_note, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.id or new_id("catalog-review"), assignment.tenant_id, assignment.fascicolo_id,
                    assignment.id, review.state, review.reason_code, review.reason, review.resolved_by,
                    review.resolution_note, review.created_at or now, review.resolved_at,
                ),
            )
        self._commit()
        return assignment

    def list_catalog_candidates(self, assignment_id: str) -> list[DocumentCatalogCandidate]:
        self._require_catalog_sql()
        rows = self._conn().execute(
            "SELECT * FROM document_catalog_candidates WHERE assignment_id = ? ORDER BY rank_number ASC", (assignment_id,)
        ).fetchall()
        return [dataclass_from_dict(DocumentCatalogCandidate, self._dict_row(row)) for row in rows]

    def list_catalog_evidence(self, assignment_id: str) -> list[DocumentCatalogEvidence]:
        self._require_catalog_sql()
        rows = self._conn().execute(
            "SELECT * FROM document_catalog_evidence WHERE assignment_id = ? ORDER BY weight DESC, created_at ASC", (assignment_id,)
        ).fetchall()
        return [dataclass_from_dict(DocumentCatalogEvidence, self._dict_row(row)) for row in rows]

    def list_catalog_reviews(
        self,
        tenant_id: str,
        fascicolo_id: str,
        *,
        include_resolved: bool = False,
    ) -> list[DocumentCatalogReview]:
        self._require_catalog_sql()
        sql = "SELECT * FROM document_catalog_reviews WHERE tenant_id = ? AND fascicolo_id = ?"
        if not include_resolved:
            sql += " AND state = 'open'"
        sql += " ORDER BY created_at ASC"
        rows = self._conn().execute(sql, (tenant_id, fascicolo_id)).fetchall()
        return [dataclass_from_dict(DocumentCatalogReview, self._dict_row(row)) for row in rows]

    def resolve_catalog_assignment(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        actor: str,
        status: str,
        note: str = "",
    ) -> DocumentCatalogAssignment | None:
        self._require_catalog_sql()
        if status not in {"confirmed", "rejected", "review_required"}:
            raise DocumentAIValidationError("Esito di revisione catalogo non valido.")
        assignment = self.get_catalog_assignment(tenant_id, fascicolo_id, document_id)
        if not assignment:
            return None
        now = utc_now()
        confirmed_at = now if status == "confirmed" else assignment.confirmed_at
        self._conn().execute(
            """
            UPDATE document_catalog_assignments
            SET status = ?, updated_by = ?, updated_at = ?, confirmed_at = ?
            WHERE id = ? AND tenant_id = ? AND fascicolo_id = ?
            """,
            (status, actor, now, confirmed_at, assignment.id, tenant_id, fascicolo_id),
        )
        self._conn().execute(
            """
            UPDATE document_catalog_reviews
            SET state = 'resolved', resolved_by = ?, resolution_note = ?, resolved_at = ?
            WHERE assignment_id = ? AND state = 'open'
            """,
            (actor, note, now, assignment.id),
        )
        self._commit()
        return self.get_catalog_assignment(tenant_id, fascicolo_id, document_id)

    def catalog_summary(self, tenant_id: str, fascicolo_id: str) -> dict[str, int]:
        self._require_catalog_sql()
        rows = self._conn().execute(
            """
            SELECT status, COUNT(*) AS total FROM document_catalog_assignments
            WHERE tenant_id = ? AND fascicolo_id = ?
            GROUP BY status
            """,
            (tenant_id, fascicolo_id),
        ).fetchall()
        out = {"total": 0, "proposed": 0, "confirmed": 0, "review_required": 0, "errors": 0}
        for row in rows:
            payload = self._dict_row(row)
            key = str(payload.get("status") or "")
            count = int(payload.get("total") or 0)
            out["total"] += count
            if key in out:
                out[key] = count
        job_error = self._conn().execute(
            """
            SELECT COUNT(*) AS total FROM document_catalog_jobs
            WHERE tenant_id = ? AND fascicolo_id = ? AND status = 'error'
            """,
            (tenant_id, fascicolo_id),
        ).fetchone()
        out["errors"] = int(self._dict_row(job_error).get("total") or 0) if job_error else 0
        return out

    def _catalog_assignment_from_row(self, row: Any) -> DocumentCatalogAssignment | None:
        if not row:
            return None
        payload = self._dict_row(row)
        payload["metadata"] = _dict_from_json(payload.pop("metadata_json", "{}"))
        payload["deposit_candidate"] = bool(payload.get("deposit_candidate"))
        return dataclass_from_dict(DocumentCatalogAssignment, payload)

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


def _dict_from_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    return dict(raw) if isinstance(raw, dict) else {}


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
