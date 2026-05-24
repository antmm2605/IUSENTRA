"""Repository SQLite tenant-aware per Legal Document Understanding."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

from werkzeug.utils import safe_join as werkzeug_safe_join

from .evidence_hash import canonical_json, chain_hash, sha256_bytes, sha256_file, utc_now
from .ingestion_audit import build_audit_payload


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT,
    parent_document_id TEXT,
    root_document_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_message_id TEXT,
    original_filename TEXT NOT NULL,
    normalized_filename TEXT NOT NULL,
    stored_uri TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    status TEXT NOT NULL,
    security_status TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    version_type TEXT NOT NULL,
    stored_uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    author TEXT NOT NULL,
    reason TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    prev_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(id),
    UNIQUE(document_id, version_number)
);

CREATE TABLE IF NOT EXISTS document_files (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    normalized_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    parent_document_id TEXT,
    root_pec_id TEXT,
    extraction_path_virtuale TEXT NOT NULL DEFAULT '',
    extraction_depth INTEGER NOT NULL DEFAULT 0,
    security_status TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    stored_uri TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS document_archive_children (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    parent_document_id TEXT NOT NULL,
    child_document_id TEXT NOT NULL,
    root_document_id TEXT NOT NULL,
    root_pec_id TEXT,
    extraction_path_virtuale TEXT NOT NULL,
    extraction_depth INTEGER NOT NULL,
    security_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_ocr_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    engine TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    language TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    confidence_document REAL NOT NULL DEFAULT 0,
    raw_text TEXT NOT NULL DEFAULT '',
    corrected_text TEXT NOT NULL DEFAULT '',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    errors_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS document_ocr_tokens (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    ocr_run_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    token_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_json TEXT NOT NULL DEFAULT '{}',
    warning TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS document_classifications (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    legal_area TEXT NOT NULL,
    macro_area TEXT NOT NULL,
    rito TEXT NOT NULL,
    fase TEXT NOT NULL,
    procedimento TEXT NOT NULL,
    portale_probabile TEXT NOT NULL,
    confidence REAL NOT NULL,
    motivation TEXT NOT NULL,
    signals_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_entities (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL NOT NULL,
    page INTEGER,
    bbox_json TEXT NOT NULL DEFAULT '{}',
    source_document_id TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_validations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    result TEXT NOT NULL,
    valid INTEGER NOT NULL DEFAULT 0,
    missing_critical_fields_json TEXT NOT NULL DEFAULT '[]',
    issues_json TEXT NOT NULL DEFAULT '[]',
    consistency_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_case_matches (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    matched_case_id TEXT,
    confidence REAL NOT NULL,
    matched_signals_json TEXT NOT NULL DEFAULT '[]',
    conflicts_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    date_value TEXT NOT NULL DEFAULT '',
    evidence_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS document_review_tasks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    fields_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    decision_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS evidence_audit_logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS evidence_audit_logs_no_update
BEFORE UPDATE ON evidence_audit_logs
BEGIN
    SELECT RAISE(ABORT, 'evidence_audit_logs is append-only');
END;

CREATE TRIGGER IF NOT EXISTS evidence_audit_logs_no_delete
BEFORE DELETE ON evidence_audit_logs
BEGIN
    SELECT RAISE(ABORT, 'evidence_audit_logs is append-only');
END;

CREATE TABLE IF NOT EXISTS evidence_hash_chain (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proof_bundles (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    stored_uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    manifest_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lex_index_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    chunks_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS lex_document_chunks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER,
    text TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_tenant_status ON documents(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_fascicolo ON documents(tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_document_files_doc ON document_files(tenant_id, document_id);
CREATE INDEX IF NOT EXISTS idx_archive_parent ON document_archive_children(tenant_id, parent_document_id);
CREATE INDEX IF NOT EXISTS idx_entities_doc ON legal_entities(tenant_id, document_id);
CREATE INDEX IF NOT EXISTS idx_events_doc ON document_events(tenant_id, document_id);
CREATE INDEX IF NOT EXISTS idx_lex_chunks_doc ON lex_document_chunks(tenant_id, document_id);
"""


class LegalDocumentRepository:
    def __init__(self, db_path: str | Path, storage_root: str | Path):
        self.db_path = Path(db_path)
        self.storage_root = Path(storage_root)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SQLITE_SCHEMA)
            conn.commit()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def write_file(self, tenant_id: str, filename: str, content: bytes) -> str:
        safe_name = sanitize_filename(filename)
        digest = sha256_bytes(content)
        rel = Path("files") / safe_tenant(tenant_id) / digest[:2] / f"{digest}-{safe_name}"
        target = safe_join(self.storage_root, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)
        return rel.as_posix()

    def read_file(self, stored_uri: str) -> bytes:
        return safe_join(self.storage_root, stored_uri).read_bytes()

    def insert_document(self, row: dict[str, Any], *, content: bytes | None = None, actor: str = "sistema") -> dict[str, Any]:
        now = utc_now()
        document_id = str(row.get("id") or uuid.uuid4().hex)
        tenant_id = str(row.get("tenant_id") or "default")
        root_id = str(row.get("root_document_id") or document_id)
        stored_uri = str(row.get("stored_uri") or "")
        if content is not None and not stored_uri:
            stored_uri = self.write_file(tenant_id, str(row.get("normalized_filename") or row.get("original_filename") or document_id), content)
        payload = {
            "id": document_id,
            "tenant_id": tenant_id,
            "fascicolo_id": row.get("fascicolo_id") or None,
            "parent_document_id": row.get("parent_document_id") or None,
            "root_document_id": root_id,
            "source_type": str(row.get("source_type") or "upload manuale"),
            "source_message_id": row.get("source_message_id") or None,
            "original_filename": str(row.get("original_filename") or "documento"),
            "normalized_filename": str(row.get("normalized_filename") or sanitize_filename(str(row.get("original_filename") or "documento.bin"))),
            "stored_uri": stored_uri,
            "mime_type": str(row.get("mime_type") or "application/octet-stream"),
            "extension": str(row.get("extension") or "").lower(),
            "sha256": str(row.get("sha256") or (sha256_bytes(content or b"") if content is not None else "")),
            "file_size": int(row.get("file_size") or (len(content) if content is not None else 0)),
            "status": str(row.get("status") or "acquired"),
            "security_status": str(row.get("security_status") or "validated"),
            "processing_status": str(row.get("processing_status") or "queued"),
            "created_at": str(row.get("created_at") or now),
            "updated_at": str(row.get("updated_at") or now),
            "created_by": str(row.get("created_by") or actor or "sistema"),
            "reviewed_by": row.get("reviewed_by") or None,
            "reviewed_at": row.get("reviewed_at") or None,
            "metadata_json": canonical_json(row.get("metadata") or {}),
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, fascicolo_id, parent_document_id, root_document_id,
                    source_type, source_message_id, original_filename, normalized_filename,
                    stored_uri, mime_type, extension, sha256, file_size, status,
                    security_status, processing_status, created_at, updated_at,
                    created_by, reviewed_by, reviewed_at, metadata_json
                ) VALUES (
                    :id, :tenant_id, :fascicolo_id, :parent_document_id, :root_document_id,
                    :source_type, :source_message_id, :original_filename, :normalized_filename,
                    :stored_uri, :mime_type, :extension, :sha256, :file_size, :status,
                    :security_status, :processing_status, :created_at, :updated_at,
                    :created_by, :reviewed_by, :reviewed_at, :metadata_json
                )
                """,
                payload,
            )
            self._insert_initial_version(conn, payload, actor=actor)
            self.append_file_row(conn, payload, root_pec_id=str(row.get("root_pec_id") or ""), extraction_path=str(row.get("extraction_path_virtuale") or ""), extraction_depth=int(row.get("extraction_depth") or 0))
            self.append_audit(
                conn,
                tenant_id=tenant_id,
                actor=actor,
                action="document.uploaded" if not row.get("parent_document_id") else "pec.attachment.detected",
                resource_type="document",
                resource_id=document_id,
                payload={"sha256": payload["sha256"], "source_type": payload["source_type"], "security_status": payload["security_status"]},
            )
            conn.commit()
        return self.get_document(tenant_id, document_id) or payload

    def append_file_row(self, conn: sqlite3.Connection, document_row: dict[str, Any], *, root_pec_id: str = "", extraction_path: str = "", extraction_depth: int = 0) -> str:
        file_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO document_files (
                id, tenant_id, document_id, original_filename, normalized_filename, mime_type,
                extension, size, sha256, parent_document_id, root_pec_id,
                extraction_path_virtuale, extraction_depth, security_status,
                processing_status, stored_uri, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                document_row["tenant_id"],
                document_row["id"],
                document_row["original_filename"],
                document_row["normalized_filename"],
                document_row["mime_type"],
                document_row["extension"],
                document_row["file_size"],
                document_row["sha256"],
                document_row.get("parent_document_id"),
                root_pec_id,
                extraction_path,
                extraction_depth,
                document_row["security_status"],
                document_row["processing_status"],
                document_row["stored_uri"],
                utc_now(),
            ),
        )
        return file_id

    def link_archive_child(self, tenant_id: str, parent_document_id: str, child_document_id: str, root_document_id: str, *, root_pec_id: str = "", extraction_path: str = "", extraction_depth: int = 0, security_status: str = "validated", actor: str = "sistema") -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO document_archive_children (
                    id, tenant_id, parent_document_id, child_document_id, root_document_id,
                    root_pec_id, extraction_path_virtuale, extraction_depth, security_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (uuid.uuid4().hex, tenant_id, parent_document_id, child_document_id, root_document_id, root_pec_id, extraction_path, extraction_depth, security_status, utc_now()),
            )
            self.append_audit(
                conn,
                tenant_id=tenant_id,
                actor=actor,
                action="archive.extracted",
                resource_type="document",
                resource_id=parent_document_id,
                payload={"child_document_id": child_document_id, "path": extraction_path, "security_status": security_status},
            )
            conn.commit()

    def update_document_status(self, tenant_id: str, document_id: str, *, status: str | None = None, security_status: str | None = None, processing_status: str | None = None, reviewed_by: str | None = None) -> None:
        current = self.get_document(tenant_id, document_id)
        if not current:
            return
        next_status = status or current["status"]
        next_security = security_status or current["security_status"]
        next_processing = processing_status or current["processing_status"]
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE documents
                SET status=?, security_status=?, processing_status=?, updated_at=?,
                    reviewed_by=COALESCE(?, reviewed_by),
                    reviewed_at=CASE WHEN ? IS NULL THEN reviewed_at ELSE ? END
                WHERE tenant_id=? AND id=?
                """,
                (next_status, next_security, next_processing, utc_now(), reviewed_by, reviewed_by, utc_now(), tenant_id, document_id),
            )
            self.append_audit(
                conn,
                tenant_id=tenant_id,
                actor=reviewed_by or "sistema",
                action="document.status.updated",
                resource_type="document",
                resource_id=document_id,
                payload={"before": {"status": current["status"]}, "after": {"status": next_status, "security_status": next_security, "processing_status": next_processing}},
            )
            conn.commit()

    def get_document(self, tenant_id: str, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE tenant_id=? AND id=?", (tenant_id, document_id)).fetchone()
            return self._row(row) if row else None

    def list_documents(self, tenant_id: str, *, fascicolo_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        limit_value = max(1, min(int(limit or 100), 500))
        query = "SELECT * FROM documents WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?"
        params: tuple[Any, ...] = (tenant_id, limit_value)
        if fascicolo_id:
            query = "SELECT * FROM documents WHERE tenant_id=? AND fascicolo_id=? ORDER BY created_at DESC LIMIT ?"
            params = (tenant_id, fascicolo_id, limit_value)
        with self.connect() as conn:
            return [
                self._row(row)
                for row in conn.execute(query, params).fetchall()
            ]

    def file_for_document(self, tenant_id: str, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM document_files WHERE tenant_id=? AND document_id=? ORDER BY created_at DESC LIMIT 1",
                (tenant_id, document_id),
            ).fetchone()
            return self._row(row) if row else None

    def insert_ocr_run(self, tenant_id: str, document_id: str, run: dict[str, Any], tokens: Iterable[dict[str, Any]], *, actor: str = "ocr-forense") -> dict[str, Any]:
        run_id = str(run.get("id") or uuid.uuid4().hex)
        token_rows = list(tokens or [])
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO document_ocr_runs (
                    id, tenant_id, document_id, engine, engine_version, language,
                    started_at, completed_at, page_count, token_count, confidence_document,
                    raw_text, corrected_text, warnings_json, errors_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    tenant_id,
                    document_id,
                    str(run.get("engine") or "iusentra-forensic-ocr"),
                    str(run.get("engine_version") or "1"),
                    str(run.get("language") or "ita"),
                    str(run.get("started_at") or utc_now()),
                    str(run.get("completed_at") or utc_now()),
                    int(run.get("page_count") or 0),
                    len(token_rows),
                    float(run.get("confidence_document") or 0.0),
                    str(run.get("raw_text") or ""),
                    str(run.get("corrected_text") or ""),
                    canonical_json(run.get("warnings") or []),
                    canonical_json(run.get("errors") or []),
                ),
            )
            for token in token_rows:
                conn.execute(
                    """
                    INSERT INTO document_ocr_tokens (
                        id, tenant_id, ocr_run_id, document_id, page_number,
                        token_text, confidence, bbox_json, warning
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(token.get("id") or uuid.uuid4().hex),
                        tenant_id,
                        run_id,
                        document_id,
                        int(token.get("page_number") or 1),
                        str(token.get("token_text") or ""),
                        float(token.get("confidence") or 0.0),
                        canonical_json(token.get("bbox") or {}),
                        str(token.get("warning") or ""),
                    ),
                )
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action="ocr.completed", resource_type="document", resource_id=document_id, payload={"ocr_run_id": run_id, "tokens": len(token_rows), "confidence": run.get("confidence_document")})
            conn.commit()
        return self.get_ocr_overlay(tenant_id, document_id)

    def latest_ocr_text(self, tenant_id: str, document_id: str) -> str:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT corrected_text, raw_text FROM document_ocr_runs WHERE tenant_id=? AND document_id=? ORDER BY completed_at DESC LIMIT 1",
                (tenant_id, document_id),
            ).fetchone()
            if not row:
                return ""
            return str(row["corrected_text"] or row["raw_text"] or "")

    def get_ocr_overlay(self, tenant_id: str, document_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            run = conn.execute(
                "SELECT * FROM document_ocr_runs WHERE tenant_id=? AND document_id=? ORDER BY completed_at DESC LIMIT 1",
                (tenant_id, document_id),
            ).fetchone()
            if not run:
                return {"document_id": document_id, "ocr_run": None, "tokens": []}
            tokens = [
                self._row(row)
                for row in conn.execute(
                    "SELECT * FROM document_ocr_tokens WHERE tenant_id=? AND ocr_run_id=? ORDER BY page_number, rowid",
                    (tenant_id, run["id"]),
                ).fetchall()
            ]
            return {"document_id": document_id, "ocr_run": self._row(run), "tokens": tokens}

    def replace_classification(self, tenant_id: str, document_id: str, classification: dict[str, Any], *, actor: str = "classifier") -> dict[str, Any]:
        row_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO document_classifications (
                    id, tenant_id, document_id, document_type, legal_area, macro_area, rito,
                    fase, procedimento, portale_probabile, confidence, motivation,
                    signals_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    tenant_id,
                    document_id,
                    str(classification.get("document_type") or "unknown"),
                    str(classification.get("legal_area") or "unknown"),
                    str(classification.get("macro_area") or "unknown"),
                    str(classification.get("rito") or ""),
                    str(classification.get("fase") or ""),
                    str(classification.get("procedimento") or ""),
                    str(classification.get("portale_probabile") or ""),
                    float(classification.get("confidence") or 0.0),
                    str(classification.get("motivation") or ""),
                    canonical_json(classification.get("signals") or []),
                    str(classification.get("status") or "unknown"),
                    utc_now(),
                ),
            )
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action="document.classified", resource_type="document", resource_id=document_id, payload=classification)
            conn.commit()
        return self.latest_classification(tenant_id, document_id) or {}

    def latest_classification(self, tenant_id: str, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM document_classifications WHERE tenant_id=? AND document_id=? ORDER BY created_at DESC LIMIT 1",
                (tenant_id, document_id),
            ).fetchone()
            return self._row(row) if row else None

    def replace_entities(self, tenant_id: str, document_id: str, entities: Iterable[dict[str, Any]], *, actor: str = "entity-extractor") -> list[dict[str, Any]]:
        rows = list(entities or [])
        with self.connect() as conn:
            for item in rows:
                conn.execute(
                    """
                    INSERT INTO legal_entities (
                        id, tenant_id, document_id, entity_type, value, confidence, page,
                        bbox_json, source_document_id, extraction_method, validation_status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(item.get("id") or uuid.uuid4().hex),
                        tenant_id,
                        document_id,
                        str(item.get("entity_type") or ""),
                        str(item.get("value") or ""),
                        float(item.get("confidence") or 0.0),
                        item.get("page"),
                        canonical_json(item.get("bbox") or {}),
                        str(item.get("source_document_id") or document_id),
                        str(item.get("extraction_method") or "regex"),
                        str(item.get("validation_status") or "not_checked"),
                        utc_now(),
                    ),
                )
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action="entities.extracted", resource_type="document", resource_id=document_id, payload={"count": len(rows)})
            conn.commit()
        return self.list_entities(tenant_id, document_id)

    def list_entities(self, tenant_id: str, document_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [
                self._row(row)
                for row in conn.execute(
                    "SELECT * FROM legal_entities WHERE tenant_id=? AND document_id=? ORDER BY entity_type, value",
                    (tenant_id, document_id),
                ).fetchall()
            ]

    def replace_validation(self, tenant_id: str, document_id: str, validation: dict[str, Any], *, actor: str = "validator") -> dict[str, Any]:
        row_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO document_validations (
                    id, tenant_id, document_id, result, valid, missing_critical_fields_json,
                    issues_json, consistency_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    tenant_id,
                    document_id,
                    str(validation.get("result") or "needs_review"),
                    1 if validation.get("valid") else 0,
                    canonical_json(validation.get("missing_critical_fields") or []),
                    canonical_json(validation.get("issues") or []),
                    canonical_json(validation.get("consistency") or {}),
                    utc_now(),
                ),
            )
            result = str(validation.get("result") or "needs_review")
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action="validation.completed", resource_type="document", resource_id=document_id, payload=validation)
            conn.commit()
        if result == "valid":
            self.update_document_status(tenant_id, document_id, status="validated", processing_status="validated")
        elif result == "rejected" or result == "unsafe_file":
            self.update_document_status(tenant_id, document_id, status="rejected", processing_status=result)
        else:
            self.update_document_status(tenant_id, document_id, status="needs_review", processing_status=result)
        return self.latest_validation(tenant_id, document_id) or {}

    def latest_validation(self, tenant_id: str, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM document_validations WHERE tenant_id=? AND document_id=? ORDER BY created_at DESC LIMIT 1",
                (tenant_id, document_id),
            ).fetchone()
            return self._row(row) if row else None

    def replace_case_match(self, tenant_id: str, document_id: str, match: dict[str, Any], *, actor: str = "case-matcher") -> dict[str, Any]:
        row_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO document_case_matches (
                    id, tenant_id, document_id, matched_case_id, confidence,
                    matched_signals_json, conflicts_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    tenant_id,
                    document_id,
                    match.get("matched_case_id") or None,
                    float(match.get("confidence") or 0.0),
                    canonical_json(match.get("matched_signals") or []),
                    canonical_json(match.get("conflicts") or []),
                    str(match.get("status") or "no_match"),
                    utc_now(),
                ),
            )
            event_name = "case.auto_matched" if match.get("status") == "auto_matched" else "case.match.suggested"
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action=event_name, resource_type="document", resource_id=document_id, payload=match)
            conn.commit()
        return self.latest_case_match(tenant_id, document_id) or {}

    def latest_case_match(self, tenant_id: str, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM document_case_matches WHERE tenant_id=? AND document_id=? ORDER BY created_at DESC LIMIT 1",
                (tenant_id, document_id),
            ).fetchone()
            return self._row(row) if row else None

    def replace_events(self, tenant_id: str, document_id: str, events: Iterable[dict[str, Any]], *, actor: str = "event-engine") -> list[dict[str, Any]]:
        rows = list(events or [])
        with self.connect() as conn:
            for item in rows:
                conn.execute(
                    """
                    INSERT INTO document_events (
                        id, tenant_id, document_id, event_type, title, date_value,
                        evidence_text, confidence, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(item.get("id") or uuid.uuid4().hex),
                        tenant_id,
                        document_id,
                        str(item.get("event_type") or "attivita"),
                        str(item.get("title") or "Evento da verificare"),
                        str(item.get("date_value") or ""),
                        str(item.get("evidence_text") or ""),
                        float(item.get("confidence") or 0.0),
                        str(item.get("status") or "pending_review"),
                        utc_now(),
                    ),
                )
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action="legal.event.proposed", resource_type="document", resource_id=document_id, payload={"count": len(rows)})
            conn.commit()
        return self.list_events(tenant_id, document_id)

    def list_events(self, tenant_id: str, document_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [self._row(row) for row in conn.execute("SELECT * FROM document_events WHERE tenant_id=? AND document_id=? ORDER BY created_at", (tenant_id, document_id)).fetchall()]

    def approve_events(self, tenant_id: str, document_id: str, event_ids: Iterable[str], *, actor: str) -> list[dict[str, Any]]:
        ids = [str(item) for item in event_ids if str(item or "").strip()]
        if not ids:
            return self.list_events(tenant_id, document_id)
        with self.connect() as conn:
            approved_at = utc_now()
            for event_id in ids:
                conn.execute(
                    "UPDATE document_events SET status='approved', approved_by=?, approved_at=? WHERE tenant_id=? AND document_id=? AND id=?",
                    (actor, approved_at, tenant_id, document_id, event_id),
                )
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action="legal.event.approved", resource_type="document", resource_id=document_id, payload={"event_ids": ids})
            conn.commit()
        return self.list_events(tenant_id, document_id)

    def create_review_task(self, tenant_id: str, document_id: str, *, task_type: str, reason: str, fields: dict[str, Any] | None = None, actor: str = "validator") -> dict[str, Any]:
        task_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO document_review_tasks (
                    id, tenant_id, document_id, task_type, status, reason, fields_json,
                    created_at, decision_json
                ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?, '{}')
                """,
                (task_id, tenant_id, document_id, task_type, reason, canonical_json(fields or {}), utc_now()),
            )
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action="review.required", resource_type="document", resource_id=document_id, payload={"task_id": task_id, "reason": reason})
            conn.commit()
        return self.get_review_task(tenant_id, task_id) or {}

    def get_review_task(self, tenant_id: str, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM document_review_tasks WHERE tenant_id=? AND id=?", (tenant_id, task_id)).fetchone()
            return self._row(row) if row else None

    def complete_review(self, tenant_id: str, document_id: str, decision: dict[str, Any], *, actor: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE document_review_tasks
                SET status='completed', reviewed_by=?, reviewed_at=?, decision_json=?
                WHERE tenant_id=? AND document_id=? AND status='open'
                """,
                (actor, utc_now(), canonical_json(decision), tenant_id, document_id),
            )
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action="review.completed", resource_type="document", resource_id=document_id, payload=decision)
            conn.commit()
        self.update_document_status(tenant_id, document_id, status=str(decision.get("status") or "validated"), processing_status="reviewed", reviewed_by=actor)
        return {"ok": True, "document_id": document_id, "decision": decision}

    def create_lex_index_job(self, tenant_id: str, document_id: str, *, status: str, reason: str, chunks: list[dict[str, Any]], metadata: dict[str, Any], actor: str = "lex-indexer") -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        with self.connect() as conn:
            for index, chunk in enumerate(chunks):
                conn.execute(
                    """
                    INSERT INTO lex_document_chunks (
                        id, tenant_id, document_id, chunk_index, page_number, text,
                        metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        tenant_id,
                        document_id,
                        index,
                        chunk.get("page_number"),
                        str(chunk.get("text") or ""),
                        canonical_json(chunk.get("metadata") or metadata),
                        utc_now(),
                    ),
                )
            conn.execute(
                """
                INSERT INTO lex_index_jobs (
                    id, tenant_id, document_id, status, reason, chunks_count,
                    metadata_json, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, tenant_id, document_id, status, reason, len(chunks), canonical_json(metadata), utc_now(), utc_now() if status == "completed" else None),
            )
            event = "lex.index.completed" if status == "completed" else "lex.index.requested"
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action=event, resource_type="document", resource_id=document_id, payload={"job_id": job_id, "status": status, "chunks": len(chunks), "reason": reason})
            conn.commit()
        return self.latest_lex_job(tenant_id, document_id) or {}

    def latest_lex_job(self, tenant_id: str, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM lex_index_jobs WHERE tenant_id=? AND document_id=? ORDER BY created_at DESC LIMIT 1", (tenant_id, document_id)).fetchone()
            return self._row(row) if row else None

    def lex_chunks(self, tenant_id: str, document_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [self._row(row) for row in conn.execute("SELECT * FROM lex_document_chunks WHERE tenant_id=? AND document_id=? ORDER BY chunk_index", (tenant_id, document_id)).fetchall()]

    def archive_tree(self, tenant_id: str, document_id: str) -> dict[str, Any]:
        root = self.get_document(tenant_id, document_id)
        if not root:
            return {"document": None, "children": []}
        return {"document": root, "children": self._children_tree(tenant_id, document_id)}

    def _children_tree(self, tenant_id: str, parent_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM document_archive_children WHERE tenant_id=? AND parent_document_id=? ORDER BY extraction_path_virtuale",
                (tenant_id, parent_id),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            link = self._row(row)
            child = self.get_document(tenant_id, str(link["child_document_id"]))
            out.append({"link": link, "document": child, "children": self._children_tree(tenant_id, str(link["child_document_id"]))})
        return out

    def evidence_payload(self, tenant_id: str, document_id: str) -> dict[str, Any]:
        document = self.get_document(tenant_id, document_id)
        with self.connect() as conn:
            files = [self._row(row) for row in conn.execute("SELECT * FROM document_files WHERE tenant_id=? AND document_id=?", (tenant_id, document_id)).fetchall()]
            audit = [self._row(row) for row in conn.execute("SELECT * FROM evidence_audit_logs WHERE tenant_id=? AND resource_id=? ORDER BY occurred_at", (tenant_id, document_id)).fetchall()]
            chain = [self._row(row) for row in conn.execute("SELECT * FROM evidence_hash_chain WHERE tenant_id=? AND resource_id=? ORDER BY created_at", (tenant_id, document_id)).fetchall()]
        return {
            "document": document,
            "files": files,
            "classification": self.latest_classification(tenant_id, document_id),
            "entities": self.list_entities(tenant_id, document_id),
            "validation": self.latest_validation(tenant_id, document_id),
            "case_match": self.latest_case_match(tenant_id, document_id),
            "events": self.list_events(tenant_id, document_id),
            "lex_index": self.latest_lex_job(tenant_id, document_id),
            "audit": audit,
            "hash_chain": chain,
        }

    def create_proof_bundle(self, tenant_id: str, document_id: str, *, actor: str) -> dict[str, Any]:
        evidence = self.evidence_payload(tenant_id, document_id)
        if not evidence.get("document"):
            raise KeyError("Documento non trovato.")
        bundle_id = uuid.uuid4().hex
        rel = Path("proof_bundles") / safe_tenant(tenant_id) / f"{bundle_id}.zip"
        target = safe_join(self.storage_root, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        manifest = {"created_at": utc_now(), "bundle_id": bundle_id, "document_id": document_id, "evidence": evidence}
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", canonical_json(manifest))
            document = evidence["document"]
            stored_uri = str(document.get("stored_uri") or "")
            if stored_uri:
                try:
                    archive.writestr(f"originale/{Path(stored_uri).name}", self.read_file(stored_uri))
                except OSError:
                    pass
        digest = sha256_file(target)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO proof_bundles (id, tenant_id, document_id, stored_uri, sha256, created_by, created_at, manifest_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (bundle_id, tenant_id, document_id, rel.as_posix(), digest, actor, utc_now(), canonical_json(manifest)),
            )
            self.append_audit(conn, tenant_id=tenant_id, actor=actor, action="proof_bundle.created", resource_type="document", resource_id=document_id, payload={"bundle_id": bundle_id, "sha256": digest})
            conn.commit()
        return {"id": bundle_id, "stored_uri": rel.as_posix(), "sha256": digest, "manifest": manifest}

    def metrics(self, tenant_id: str | None = None) -> dict[str, Any]:
        with self.connect() as conn:
            if tenant_id:
                params = (tenant_id,)
                documents = _scalar(conn, "SELECT COUNT(*) FROM documents WHERE tenant_id=?", params)
                validated = _scalar(conn, "SELECT COUNT(*) FROM document_validations WHERE tenant_id=? AND result='valid'", params)
                review = _scalar(conn, "SELECT COUNT(*) FROM document_validations WHERE tenant_id=? AND result='needs_review'", params)
                rejected = _scalar(conn, "SELECT COUNT(*) FROM document_validations WHERE tenant_id=? AND result IN ('rejected','unsafe_file')", params)
                lex_ready = _scalar(conn, "SELECT COUNT(*) FROM lex_index_jobs WHERE tenant_id=? AND status='completed'", params)
                events_total = _scalar(conn, "SELECT COUNT(*) FROM document_events WHERE tenant_id=?", params)
                events_approved = _scalar(conn, "SELECT COUNT(*) FROM document_events WHERE tenant_id=? AND status='approved'", params)
                class_rows = [row[0] for row in conn.execute("SELECT confidence FROM document_classifications WHERE tenant_id=?", params).fetchall()]
                match_rows = [row[0] for row in conn.execute("SELECT confidence FROM document_case_matches WHERE tenant_id=?", params).fetchall()]
                ocr_rows = [row[0] for row in conn.execute("SELECT confidence_document FROM document_ocr_runs WHERE tenant_id=?", params).fetchall()]
            else:
                documents = _scalar(conn, "SELECT COUNT(*) FROM documents")
                validated = _scalar(conn, "SELECT COUNT(*) FROM document_validations WHERE result='valid'")
                review = _scalar(conn, "SELECT COUNT(*) FROM document_validations WHERE result='needs_review'")
                rejected = _scalar(conn, "SELECT COUNT(*) FROM document_validations WHERE result IN ('rejected','unsafe_file')")
                lex_ready = _scalar(conn, "SELECT COUNT(*) FROM lex_index_jobs WHERE status='completed'")
                events_total = _scalar(conn, "SELECT COUNT(*) FROM document_events")
                events_approved = _scalar(conn, "SELECT COUNT(*) FROM document_events WHERE status='approved'")
                class_rows = [row[0] for row in conn.execute("SELECT confidence FROM document_classifications").fetchall()]
                match_rows = [row[0] for row in conn.execute("SELECT confidence FROM document_case_matches").fetchall()]
                ocr_rows = [row[0] for row in conn.execute("SELECT confidence_document FROM document_ocr_runs").fetchall()]
        auto_rate = (validated / documents) if documents else 0.0
        review_rate = (review / documents) if documents else 0.0
        estimated_reduction = round(min(0.95, auto_rate * 0.65 + (lex_ready / max(documents, 1)) * 0.15 + (events_total / max(documents, 1)) * 0.08), 3) if documents else 0.0
        return {
            "documents": documents,
            "validated_documents": validated,
            "needs_review_documents": review,
            "rejected_documents": rejected,
            "lex_indexed_documents": lex_ready,
            "ocr_document_confidence_avg": _avg(ocr_rows),
            "classification_confidence_avg": _avg(class_rows),
            "case_matching_confidence_avg": _avg(match_rows),
            "event_extraction_accuracy": round(events_approved / events_total, 3) if events_total else 0.0,
            "auto_validated_percent": round(auto_rate * 100, 2),
            "review_percent": round(review_rate * 100, 2),
            "estimated_work_reduction_percent": round(estimated_reduction * 100, 2),
            "target_80_percent_achieved": estimated_reduction >= 0.80,
            "measurement_note": "Il target 80% è vero solo con documenti reali validati; senza campione operativo resta non raggiunto.",
        }

    def _insert_initial_version(self, conn: sqlite3.Connection, document_row: dict[str, Any], *, actor: str) -> None:
        payload = {
            "document_id": document_row["id"],
            "sha256": document_row["sha256"],
            "stored_uri": document_row["stored_uri"],
            "status": document_row["status"],
        }
        prev_hash = self._latest_chain_hash(conn, document_row["tenant_id"], "document", document_row["id"])
        current_hash = chain_hash(prev_hash, payload)
        conn.execute(
            """
            INSERT INTO document_versions (
                id, tenant_id, document_id, version_number, version_type, stored_uri,
                sha256, author, reason, before_json, after_json, prev_hash,
                current_hash, created_at
            ) VALUES (?, ?, ?, 1, 'originale', ?, ?, ?, ?, '{}', ?, ?, ?, ?)
            """,
            (uuid.uuid4().hex, document_row["tenant_id"], document_row["id"], document_row["stored_uri"], document_row["sha256"], actor or "sistema", "Acquisizione originale", canonical_json(payload), prev_hash, current_hash, utc_now()),
        )
        self._append_hash_chain(conn, document_row["tenant_id"], "document", document_row["id"], prev_hash, current_hash, sha256_bytes(canonical_json(payload).encode("utf-8")))

    def append_audit(self, conn: sqlite3.Connection, *, tenant_id: str, actor: str, action: str, resource_type: str, resource_id: str, payload: dict[str, Any] | None = None) -> str:
        event = build_audit_payload(tenant_id=tenant_id, actor=actor, action=action, resource_type=resource_type, resource_id=resource_id, payload=payload or {})
        prev_hash = self._latest_chain_hash(conn, tenant_id, resource_type, resource_id)
        entry_hash = chain_hash(prev_hash, event)
        conn.execute(
            """
            INSERT INTO evidence_audit_logs (
                id, tenant_id, occurred_at, actor, action, resource_type, resource_id,
                payload_json, prev_hash, entry_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (uuid.uuid4().hex, tenant_id, event["occurred_at"], event["actor"], action, resource_type, resource_id, canonical_json(event["payload"]), prev_hash, entry_hash),
        )
        self._append_hash_chain(conn, tenant_id, resource_type, resource_id, prev_hash, entry_hash, sha256_bytes(canonical_json(event).encode("utf-8")))
        return entry_hash

    def _latest_chain_hash(self, conn: sqlite3.Connection, tenant_id: str, resource_type: str, resource_id: str) -> str:
        row = conn.execute(
            """
            SELECT current_hash FROM evidence_hash_chain
            WHERE tenant_id=? AND resource_type=? AND resource_id=?
            ORDER BY created_at DESC, rowid DESC LIMIT 1
            """,
            (tenant_id, resource_type, resource_id),
        ).fetchone()
        return str(row["current_hash"] or "") if row else ""

    def _append_hash_chain(self, conn: sqlite3.Connection, tenant_id: str, resource_type: str, resource_id: str, prev_hash: str, current_hash: str, payload_sha256: str) -> None:
        conn.execute(
            """
            INSERT INTO evidence_hash_chain (
                id, tenant_id, resource_type, resource_id, prev_hash, current_hash,
                payload_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (uuid.uuid4().hex, tenant_id, resource_type, resource_id, prev_hash, current_hash, payload_sha256, utc_now()),
        )

    def _row(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        payload = dict(row)
        for key in list(payload):
            if key.endswith("_json"):
                clean_key = key[:-5]
                try:
                    payload[clean_key] = json.loads(payload.get(key) or "{}")
                except json.JSONDecodeError:
                    payload[clean_key] = [] if str(payload.get(key) or "").startswith("[") else {}
        return payload


def sanitize_filename(filename: str) -> str:
    raw = Path(str(filename or "documento.bin").replace("\\", "/")).name.strip()
    if not raw or raw in {".", ".."}:
        raw = "documento.bin"
    stem = Path(raw).stem or "documento"
    suffixes = "".join(Path(raw).suffixes).lower()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("._-") or "documento"
    if not suffixes:
        suffixes = ".bin"
    return f"{stem[:120]}{suffixes[:24]}"


def safe_tenant(tenant_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(tenant_id or "default")).strip("._-") or "default"


def safe_join(root: str | Path, rel: str | Path) -> Path:
    root_path = Path(root).resolve()
    rel_text = _safe_relative_path_text(rel)
    joined = werkzeug_safe_join(str(root_path), rel_text)
    if not joined:
        raise ValueError("Percorso probatorio non sicuro.")
    target = Path(joined).resolve()
    try:
        target.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("Percorso probatorio non sicuro.") from exc
    return target


def _safe_relative_path_text(rel: str | Path) -> str:
    raw = str(rel or "").replace("\\", "/").strip()
    if not raw or "\x00" in raw or raw.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("Percorso probatorio non sicuro.")
    parts: list[str] = []
    for part in raw.split("/"):
        if part in {"", "."}:
            continue
        if part == ".." or ":" in part or re.search(r"[\x00-\x1f]", part):
            raise ValueError("Percorso probatorio non sicuro.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", part):
            raise ValueError("Percorso probatorio non sicuro.")
        parts.append(part)
    if not parts:
        raise ValueError("Percorso probatorio non sicuro.")
    return "/".join(parts)


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def _avg(values: list[Any]) -> float:
    numbers = [float(value or 0) for value in values]
    return round(sum(numbers) / len(numbers), 3) if numbers else 0.0
