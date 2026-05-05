"""Service applicativo Documenti AI Fascicolo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .audit import record_document_ai_event
from .extraction import ExtractionResult, extract_text_from_document
from .models import (
    DOCUMENT_AI_STATUSES,
    DocumentAIRecord,
    DocumentAISearchResult,
    DocumentAIText,
    new_id,
    utc_now,
)
from .repository import DocumentAIRepository
from .security import (
    DEFAULT_MAX_DOCUMENT_AI_BYTES,
    DocumentAINotFound,
    DocumentAIValidationError,
    assert_user_can_read,
    assert_user_can_write,
    compute_sha256,
    sanitize_filename,
    user_id_from_context,
    validate_document_file_type,
)
from .versioning import build_initial_version


class DocumentAIService:
    def __init__(
        self,
        repository: DocumentAIRepository,
        fascicoli_repository: Any = None,
        *,
        max_size_bytes: int = DEFAULT_MAX_DOCUMENT_AI_BYTES,
    ):
        self.repository = repository
        self.fascicoli_repository = fascicoli_repository
        self.max_size_bytes = max_size_bytes
        self.last_upload_result: dict[str, Any] | None = None

    def upload_document_for_fascicolo(
        self,
        tenant_id: str,
        fascicolo_id: str,
        uploaded_file: Any,
        user_context: object,
    ) -> DocumentAIRecord:
        assert_user_can_write(user_context)
        self._assert_fascicolo_access(fascicolo_id)
        original_filename = str(getattr(uploaded_file, "filename", "") or "").strip()
        safe_filename = sanitize_filename(original_filename)
        mime_type = str(getattr(uploaded_file, "content_type", "") or "").strip() or None
        file_type = validate_document_file_type(safe_filename, mime_type)
        content = _read_uploaded_file(uploaded_file)
        if not content:
            raise DocumentAIValidationError("File vuoto o non leggibile.")
        if len(content) > self.max_size_bytes:
            raise DocumentAIValidationError("File superiore al limite configurato per i documenti AI.")

        now = utc_now()
        actor = user_id_from_context(user_context)
        document_id = new_id("docai")
        sha256 = compute_sha256(content)
        record = DocumentAIRecord(
            id=document_id,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            original_filename=original_filename,
            safe_filename=safe_filename,
            file_type=file_type,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=sha256,
            status="processing",
            current_version_id=None,
            page_count=None,
            created_by=actor,
            created_at=now,
            updated_at=now,
        )
        self.repository.create_document_record(record)
        record_document_ai_event(
            self.repository,
            "document_ai.upload.started",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            user_context=user_context,
            document_id=document_id,
            sha256=sha256,
            filename=original_filename,
            status="processing",
        )

        storage_rel = str(Path(tenant_id) / fascicolo_id / document_id / f"v1-{safe_filename}").replace("\\", "/")
        self.repository.write_blob(storage_rel, content)
        version = build_initial_version(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            document_id=document_id,
            storage_path=storage_rel,
            sha256=sha256,
            created_by=actor,
        )
        self.repository.create_version(version)
        record_document_ai_event(
            self.repository,
            "document_ai.version.created",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            user_context=user_context,
            document_id=document_id,
            version_id=version.id,
            sha256=sha256,
            filename=original_filename,
            status="processing",
            payload={"version_number": 1, "source": "upload"},
        )

        extraction = extract_text_from_document(content, safe_filename, file_type)
        if extraction.ok:
            extracted_text_path = str(Path(tenant_id) / fascicolo_id / document_id / f"{version.id}.txt").replace("\\", "/")
            self.repository.write_text_blob(extracted_text_path, extraction.text)
            text = DocumentAIText(
                document_id=document_id,
                version_id=version.id,
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                text=extraction.text,
                pages=extraction.pages,
                extraction_engine=extraction.extraction_engine,
                created_at=utc_now(),
                warnings=list(extraction.warnings),
            )
            self.repository.save_extracted_text(text, extracted_text_path=extracted_text_path)
            page_count = len(extraction.pages) if extraction.pages else None
            self.repository.set_current_version(
                tenant_id,
                fascicolo_id,
                document_id,
                version.id,
                status="ready",
                page_count=page_count,
            )
            record_document_ai_event(
                self.repository,
                "document_ai.extraction.completed",
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                user_context=user_context,
                document_id=document_id,
                version_id=version.id,
                sha256=sha256,
                filename=original_filename,
                status="ready",
                payload={"engine": extraction.extraction_engine, "page_count": page_count, "warnings": extraction.warnings},
            )
            record_document_ai_event(
                self.repository,
                "document_ai.upload.completed",
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                user_context=user_context,
                document_id=document_id,
                version_id=version.id,
                sha256=sha256,
                filename=original_filename,
                status="ready",
            )
            self.last_upload_result = _upload_result(version, extraction, status="completed")
        else:
            self.repository.set_current_version(
                tenant_id,
                fascicolo_id,
                document_id,
                version.id,
                status="error",
                page_count=None,
            )
            record_document_ai_event(
                self.repository,
                "document_ai.extraction.failed",
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                user_context=user_context,
                document_id=document_id,
                version_id=version.id,
                sha256=sha256,
                filename=original_filename,
                status="error",
                error_code=extraction.error_code,
                error_message=extraction.error_message,
                payload={"engine": extraction.extraction_engine, "warnings": extraction.warnings},
            )
            record_document_ai_event(
                self.repository,
                "document_ai.upload.failed",
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                user_context=user_context,
                document_id=document_id,
                version_id=version.id,
                sha256=sha256,
                filename=original_filename,
                status="error",
                error_code=extraction.error_code,
                error_message=extraction.error_message,
            )
            self.last_upload_result = _upload_result(version, extraction, status="failed")

        refreshed = self.get_fascicolo_document(tenant_id, fascicolo_id, document_id, user_context)
        assert refreshed.status in DOCUMENT_AI_STATUSES
        return refreshed

    def list_fascicolo_documents(
        self,
        tenant_id: str,
        fascicolo_id: str,
        user_context: object,
    ) -> list[DocumentAIRecord]:
        assert_user_can_read(user_context)
        self._assert_fascicolo_access(fascicolo_id)
        return self.repository.list_documents(tenant_id, fascicolo_id, user_context)

    def get_fascicolo_document(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        user_context: object,
    ) -> DocumentAIRecord:
        assert_user_can_read(user_context)
        self._assert_fascicolo_access(fascicolo_id)
        document = self.repository.get_document(tenant_id, fascicolo_id, document_id, user_context)
        if not document:
            raise DocumentAINotFound("Documento o fascicolo non trovato")
        return document

    def get_fascicolo_document_detail(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        user_context: object,
    ) -> tuple[DocumentAIRecord, list[Any], dict[str, str | None]]:
        document = self.get_fascicolo_document(tenant_id, fascicolo_id, document_id, user_context)
        versions = self.repository.list_versions(tenant_id, fascicolo_id, document_id)
        audit_summary = self.repository.audit_summary(tenant_id, fascicolo_id, document_id)
        return document, versions, audit_summary

    def get_fascicolo_document_text(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        user_context: object,
    ) -> DocumentAIText:
        document = self.get_fascicolo_document(tenant_id, fascicolo_id, document_id, user_context)
        if document.status != "ready":
            raise DocumentAIValidationError("Testo non disponibile: estrazione non completata.")
        text = self.repository.get_extracted_text(tenant_id, fascicolo_id, document_id, document.current_version_id)
        if not text:
            raise DocumentAINotFound("Testo del documento non trovato")
        record_document_ai_event(
            self.repository,
            "document_ai.read",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            user_context=user_context,
            document_id=document_id,
            version_id=text.version_id,
            sha256=document.sha256,
            filename=document.original_filename,
            status=document.status,
        )
        return text

    def search_fascicolo_document(
        self,
        tenant_id: str,
        fascicolo_id: str,
        document_id: str,
        query: str,
        user_context: object,
        max_results: int = 20,
    ) -> list[DocumentAISearchResult]:
        clean_query = str(query or "").strip()
        if not clean_query:
            raise DocumentAIValidationError("Query di ricerca mancante.")
        document = self.get_fascicolo_document(tenant_id, fascicolo_id, document_id, user_context)
        results = self.repository.search_extracted_text(
            tenant_id,
            fascicolo_id,
            document_id,
            clean_query,
            user_context,
            max_results=max_results,
        )
        record_document_ai_event(
            self.repository,
            "document_ai.search",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            user_context=user_context,
            document_id=document_id,
            version_id=document.current_version_id,
            sha256=document.sha256,
            filename=document.original_filename,
            status=document.status,
            payload={"query_length": len(clean_query), "results_count": len(results)},
        )
        return results

    def _assert_fascicolo_access(self, fascicolo_id: str) -> None:
        if self.fascicoli_repository is None:
            return
        getter = getattr(self.fascicoli_repository, "get", None)
        if callable(getter) and not getter(fascicolo_id):
            raise DocumentAINotFound("Documento o fascicolo non trovato")


def _read_uploaded_file(uploaded_file: Any) -> bytes:
    reader = getattr(uploaded_file, "read", None)
    if not callable(reader):
        raise DocumentAIValidationError("File non leggibile.")
    content = reader()
    seeker = getattr(uploaded_file, "seek", None)
    if callable(seeker):
        try:
            seeker(0)
        except Exception:
            pass
    if isinstance(content, str):
        content = content.encode("utf-8")
    if not isinstance(content, (bytes, bytearray)):
        raise DocumentAIValidationError("File non leggibile.")
    return bytes(content)


def _upload_result(version: Any, extraction: ExtractionResult, *, status: str) -> dict[str, Any]:
    return {
        "version": version,
        "extraction": {
            "status": status,
            "engine": extraction.extraction_engine,
            "page_count": len(extraction.pages) if extraction.pages else None,
            "warnings": list(extraction.warnings),
        },
    }
