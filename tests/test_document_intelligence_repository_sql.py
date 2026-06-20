from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from pct.document_intelligence.extraction import ExtractionResult
from pct.document_intelligence.models import DocumentAIPageText, DocumentAIRecord, DocumentAIText, DocumentAIVersion, utc_now
from pct.document_intelligence.repository import (
    POSTGRES_SCHEMA_DOCUMENTI_AI,
    SQL_DOCUMENT_AI_FILE_TYPES,
    SQLITE_SCHEMA_DOCUMENTI_AI,
    DocumentAIRepository,
)
from pct.document_intelligence.security import DocumentAIValidationError
from pct.document_intelligence.service import DocumentAIService


class _Upload:
    filename = "memoria.docx"
    content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def __init__(self, content: bytes = b"contenuto") -> None:
        self._content = content

    def read(self) -> bytes:
        return self._content

    def seek(self, _index: int) -> None:
        return None


def _context() -> dict[str, object]:
    return {"user_id": "user-sql", "skip_permission_check": True}


def _record(**overrides) -> DocumentAIRecord:
    payload = {
        "id": "doc-sql-1",
        "tenant_id": "tenant-a",
        "fascicolo_id": "fas-1",
        "original_filename": "atto.pdf",
        "safe_filename": "atto.pdf",
        "file_type": "pdf",
        "mime_type": "application/pdf",
        "size_bytes": 12,
        "sha256": "b" * 64,
        "status": "processing",
        "current_version_id": None,
        "page_count": None,
        "created_by": "user-sql",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    payload.update(overrides)
    return DocumentAIRecord(**payload)


def _version(document_id: str = "doc-sql-1", version_number: int = 1, **overrides) -> DocumentAIVersion:
    payload = {
        "id": f"ver-sql-{version_number}",
        "tenant_id": "tenant-a",
        "fascicolo_id": "fas-1",
        "document_id": document_id,
        "version_number": version_number,
        "source": "upload",
        "storage_path": f"tenant-a/fascicoli/fas-1/documenti_ai/{document_id}/v{version_number}/atto.pdf",
        "extracted_text_path": None,
        "pdf_preview_path": None,
        "sha256": "b" * 64,
        "created_by": "user-sql",
        "created_at": utc_now(),
    }
    payload.update(overrides)
    return DocumentAIVersion(**payload)


def test_document_ai_migrazione_sqlite_applicabile_su_db_temporaneo(tmp_path: Path):
    db_path = tmp_path / "documenti_ai.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(SQLITE_SCHEMA_DOCUMENTI_AI.read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT INTO fascicolo_documenti_ai (
                id, tenant_id, fascicolo_id, original_filename, safe_filename, file_type,
                mime_type, size_bytes, sha256, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "doc-eml",
                "tenant-a",
                "fas-1",
                "ricevuta.eml",
                "ricevuta.eml",
                "eml",
                "message/rfc822",
                12,
                "d" * 64,
                "ready",
                "user-sql",
                utc_now(),
                utc_now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO fascicolo_documenti_ai (
                id, tenant_id, fascicolo_id, original_filename, safe_filename, file_type,
                mime_type, size_bytes, sha256, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "doc-txt",
                "tenant-a",
                "fas-1",
                "nota.txt",
                "nota.txt",
                "txt",
                "text/plain",
                12,
                "e" * 64,
                "ready",
                "user-sql",
                utc_now(),
                utc_now(),
            ),
        )
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
        }

    assert "fascicolo_documenti_ai" in tables
    assert "fascicolo_documenti_ai_versioni" in tables
    assert "fascicolo_documenti_ai_testi" in tables
    assert "fascicolo_documenti_ai_audit" in tables
    assert "idx_fascicolo_documenti_ai_tenant_fascicolo" in indexes
    assert "idx_fascicolo_documenti_ai_testi_doc" in indexes


def test_document_ai_migrazione_postgres_ha_schema_reale():
    schema = POSTGRES_SCHEMA_DOCUMENTI_AI.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS fascicolo_documenti_ai" in schema
    assert "CREATE TABLE IF NOT EXISTS fascicolo_documenti_ai_versioni" in schema
    assert "document_id TEXT NOT NULL REFERENCES fascicolo_documenti_ai(id) ON DELETE CASCADE" in schema
    assert "pages_json JSONB NOT NULL DEFAULT '[]'::jsonb" in schema
    assert "payload_json JSONB NOT NULL DEFAULT '{}'::jsonb" in schema
    assert "BIGSERIAL PRIMARY KEY" in schema
    assert "AUTOINCREMENT" not in schema
    assert "CHECK (status IN ('uploaded', 'processing', 'ready', 'error', 'archived'))" in schema
    for file_type in SQL_DOCUMENT_AI_FILE_TYPES:
        assert f"'{file_type}'" in schema
    assert "fascicolo_documenti_ai_file_type_check" in schema


def test_document_ai_sqlite_migra_vincolo_legacy_per_txt_ed_eml(tmp_path: Path):
    db_path = tmp_path / "studio.db"
    now = utc_now()
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE fascicolo_documenti_ai (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                fascicolo_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                safe_filename TEXT NOT NULL,
                file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx', 'doc')),
                mime_type TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('uploaded', 'processing', 'ready', 'error', 'archived')),
                current_version_id TEXT,
                page_count INTEGER,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO fascicolo_documenti_ai (
                id, tenant_id, fascicolo_id, original_filename, safe_filename, file_type,
                mime_type, size_bytes, sha256, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "doc-legacy",
                "tenant-a",
                "fas-1",
                "atto.pdf",
                "atto.pdf",
                "pdf",
                "application/pdf",
                12,
                "a" * 64,
                "ready",
                "user-sql",
                now,
                now,
            ),
        )

    repo = DocumentAIRepository.from_sqlite_db(db_path, storage_root=tmp_path / "storage")
    repo.create_document_record(
        _record(
            id="doc-eml",
            original_filename="ricevuta.eml",
            safe_filename="ricevuta.eml",
            file_type="eml",
            mime_type="message/rfc822",
        )
    )
    repo.create_document_record(
        _record(
            id="doc-txt",
            original_filename="nota.txt",
            safe_filename="nota.txt",
            file_type="txt",
            mime_type="text/plain",
        )
    )

    indexed_types = {
        document.original_filename: document.file_type
        for document in repo.list_documents("tenant-a", "fas-1")
    }

    assert indexed_types["atto.pdf"] == "pdf"
    assert indexed_types["ricevuta.eml"] == "eml"
    assert indexed_types["nota.txt"] == "txt"
    repo.close()


def test_document_ai_repository_sqlite_persistente_filtra_e_ricarica(tmp_path: Path):
    db_path = tmp_path / "studio.db"
    repo = DocumentAIRepository.from_sqlite_db(db_path, storage_root=tmp_path / "storage")
    repo.create_document_record(_record())
    repo.create_document_record(_record(id="doc-other-tenant", tenant_id="tenant-b"))
    repo.create_document_record(_record(id="doc-other-fascicolo", fascicolo_id="fas-2"))
    version = repo.create_version(_version())
    repo.set_current_version("tenant-a", "fas-1", "doc-sql-1", version.id, status="ready", page_count=1)
    repo.save_extracted_text(
        DocumentAIText(
            document_id="doc-sql-1",
            version_id=version.id,
            tenant_id="tenant-a",
            fascicolo_id="fas-1",
            text="Il testo contiene clausola e procura.",
            pages=[DocumentAIPageText(page_number=1, text="Il testo contiene clausola e procura.")],
            extraction_engine="test-sql",
            created_at=utc_now(),
            warnings=["warning controllato"],
        ),
        extracted_text_path="tenant-a/fascicoli/fas-1/documenti_ai/doc-sql-1/v1/extracted_text.json",
    )
    repo.append_audit_event(
        {
            "id": "audit-sql-1",
            "tenant_id": "tenant-a",
            "fascicolo_id": "fas-1",
            "document_id": "doc-sql-1",
            "version_id": version.id,
            "user_id": "user-sql",
            "event_type": "document_ai.upload.completed",
            "timestamp": utc_now(),
            "sha256": "b" * 64,
            "filename": "atto.pdf",
            "status": "ready",
            "text": "questo contenuto non deve finire in audit",
        }
    )

    assert repo.storage_stats("tenant-a", "fas-1") == {
        "backend_kind": "sqlite",
        "documents": 1,
        "versions": 1,
        "texts": 1,
        "audit_events": 1,
    }
    assert [doc.id for doc in repo.list_documents("tenant-a", "fas-1")] == ["doc-sql-1"]
    assert repo.search_extracted_text("tenant-a", "fas-1", "doc-sql-1", "CLAUSOLA")[0].page_number == 1
    assert repo.search_extracted_text("tenant-b", "fas-1", "doc-sql-1", "clausola") == []
    repo.close()

    reloaded = DocumentAIRepository.from_sqlite_db(db_path, storage_root=tmp_path / "storage")
    document = reloaded.get_document("tenant-a", "fas-1", "doc-sql-1")
    text = reloaded.get_extracted_text("tenant-a", "fas-1", "doc-sql-1")
    summary = reloaded.audit_summary("tenant-a", "fas-1", "doc-sql-1")

    assert document is not None
    assert document.current_version_id == version.id
    assert text is not None
    assert text.warnings == ["warning controllato"]
    assert summary["last_event"] == "document_ai.upload.completed"
    assert not (tmp_path / "storage" / "documenti_ai.json").exists()
    reloaded.close()


def test_document_ai_repository_sqlite_presidia_vincoli(tmp_path: Path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db", storage_root=tmp_path / "storage")
    repo.create_document_record(_record())
    repo.create_version(_version())

    with pytest.raises(DocumentAIValidationError):
        repo.create_version(_version())

    with pytest.raises(sqlite3.IntegrityError):
        repo._conn().execute(
            """
            INSERT INTO fascicolo_documenti_ai (
                id, tenant_id, fascicolo_id, original_filename, safe_filename, file_type,
                mime_type, size_bytes, sha256, status, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "doc-invalid",
                "tenant-a",
                "fas-1",
                "bad.exe",
                "bad.exe",
                "exe",
                "application/octet-stream",
                1,
                "c" * 64,
                "ready",
                "user-sql",
                utc_now(),
                utc_now(),
            ),
        )
    repo.close()


def test_document_ai_service_scrive_su_repository_sqlite_persistente(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "studio.db"
    repository = DocumentAIRepository.from_sqlite_db(db_path, storage_root=tmp_path / "storage")
    service = DocumentAIService(repository)
    monkeypatch.setattr(
        "pct.document_intelligence.service.extract_text_from_document",
        lambda *_args: ExtractionResult(
            ok=True,
            text="Memoria con procura allegata.",
            pages=[DocumentAIPageText(page_number=1, text="Memoria con procura allegata.")],
            extraction_engine="test-sql-service",
        ),
    )

    result = service.upload_document_for_fascicolo("tenant-a", "fas-1", _Upload(), _context())
    repository.close()

    reloaded = DocumentAIRepository.from_sqlite_db(db_path, storage_root=tmp_path / "storage")

    assert result.document.status == "ready"
    assert reloaded.get_document("tenant-a", "fas-1", result.document.id) is not None
    assert reloaded.get_extracted_text("tenant-a", "fas-1", result.document.id) is not None
    assert reloaded.storage_stats("tenant-a", "fas-1")["audit_events"] >= 3
    reloaded.close()
