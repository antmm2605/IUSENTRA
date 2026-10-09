"""Service applicativo Documenti AI Fascicolo."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any

from .audit import record_document_ai_event
from .extraction import ExtractionResult, extract_text_from_document
from .models import (
    DOCUMENT_AI_STATUSES,
    DocumentAIRecord,
    DocumentAIPageText,
    DocumentAIVersion,
    DocumentAISearchResult,
    DocumentAIText,
    DocumentAIUploadResult,
    LexIndexingSummary,
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
    compute_sha256_bytes,
    ensure_allowed_size,
    sanitize_filename,
    user_id_from_context,
    validate_document_file_type,
)
from .versioning import build_document_storage_relative_path, build_extracted_text_relative_path, build_initial_version, next_version_number


_NON_INTERACTIVE_READ_ACTORS = frozenset({"scheduler", "scheduler-worker", "scheduler-rebuild"})
IDENTITY_PROVENANCE_MARKER = "Provenienza identità: fonti distinte v1."


def _pages_with_identity_sources(pages, sources):
    """Conserva le provenienze nel pages_json SQL già esistente."""
    result = []
    for page in pages:
        metadata = [dict(item) for item in page.identity_sources]
        for source in sources:
            if source.get('page_number') == page.page_number and source not in metadata:
                metadata.append(dict(source))
        result.append(DocumentAIPageText(page_number=page.page_number, text=page.text, identity_sources=metadata))
    return result


def _preserve_identity_archive(archived, extraction, recovery_version):
    """Aggiunge fonti riscontrate; non promuove il testo storico senza prove."""
    sources = list(extraction.identity_sources) if extraction.ok else []
    for page in extraction.pages if extraction.ok else []:
        sources.extend(item for item in page.identity_sources if item not in sources)
    # Compatibilità con lettori precedenti: l'array contiene soltanto i
    # recuperi che avevano superato i controlli, mai il testo OCR generale.
    for page in extraction.identity_recoveries if extraction.ok else []:
        source = {'page_number': page.page_number, 'mode': 'recovery', 'text': page.text}
        if not any(item.get('page_number') == page.page_number and item.get('mode') == 'recovery'
                   and str(item.get('text', '')).strip() == page.text.strip() for item in sources):
            sources.append(source)
    qualified = []
    for source in sources:
        if source.get('mode') in ('native', 'recovery') and str(source.get('text', '')).strip() and source not in qualified:
            qualified.append(dict(source))
    pages = _pages_with_identity_sources(archived.pages, [])
    for page in pages:
        if not page.identity_sources and page.text.strip():
            page.identity_sources = [{'page_number': page.page_number, 'mode': 'ocr', 'text': page.text}]
    by_number = {page.page_number: page for page in pages}
    body = archived.text
    for source in qualified:
        number, value = source.get('page_number'), str(source['text'])
        page = by_number.get(number)
        if page is None:
            # La posizione è quella restituita dal nuovo lettore, non una
            # pagina inventata per il testo storico privo di geometria.
            page = DocumentAIPageText(page_number=number, text='')
            pages.append(page)
            by_number[number] = page
        if value.strip() not in page.text:
            page.text += ('\n\n' if page.text else '') + value
        if source not in page.identity_sources:
            page.identity_sources.append(source)
        if value.strip() not in body:
            body += '\n\n' + value
    outcome = 'dati recuperati' if qualified else 'nessun dato aggiuntivo verificato'
    return ExtractionResult(ok=True, text=body, pages=pages, extraction_engine=extraction.extraction_engine,
        warnings=list(archived.warnings) + list(extraction.warnings) + [
            f'Recupero identità {recovery_version}: {outcome}; lettura precedente preservata.',
            IDENTITY_PROVENANCE_MARKER],
        identity_recoveries=[DocumentAIPageText(page_number=item.get('page_number'), text=item['text']) for item in qualified],
        identity_sources=[dict(item) for page in pages for item in page.identity_sources])


@contextmanager
def _upload_state_guard(repository, record, user_context):
    """Un errore operativo non può lasciare il documento in corso per sempre."""
    try:
        yield
    except Exception as exc:
        try:
            repository.mark_status(record.tenant_id, record.fascicolo_id, record.id, "error")
            record_document_ai_event(
                repository, "document_ai.upload.failed", tenant_id=record.tenant_id,
                fascicolo_id=record.fascicolo_id, user_context=user_context,
                document_id=record.id, filename=record.original_filename,
                sha256=record.sha256, status="error", error_code="upload_interrupted",
                error_message=str(exc)[:500],
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Stato di errore Document AI non registrato")
        raise


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
    ) -> DocumentAIUploadResult:
        assert_user_can_write(user_context)
        self._assert_fascicolo_access(fascicolo_id)
        original_filename = str(getattr(uploaded_file, "filename", "") or "").strip()
        safe_filename = sanitize_filename(original_filename)
        mime_type = str(getattr(uploaded_file, "content_type", "") or "").strip() or None
        file_type = validate_document_file_type(safe_filename, mime_type)
        content = _read_uploaded_file(uploaded_file)
        ensure_allowed_size(len(content), self.max_size_bytes)

        now = utc_now()
        actor = user_id_from_context(user_context)
        document_id = new_id("docai")
        sha256 = compute_sha256_bytes(content)
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
        with _upload_state_guard(self.repository, record, user_context):
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

            storage_rel = build_document_storage_relative_path(tenant_id, fascicolo_id, document_id, 1, safe_filename)
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
            extracted_text: DocumentAIText | None = None
            if extraction.ok:
                extracted_text_path = build_extracted_text_relative_path(tenant_id, fascicolo_id, document_id, version.version_number)
                extracted_text = DocumentAIText(
                    document_id=document_id,
                    version_id=version.id,
                    tenant_id=tenant_id,
                    fascicolo_id=fascicolo_id,
                    text=extraction.text,
                    pages=_pages_with_identity_sources(extraction.pages, extraction.identity_sources),
                    extraction_engine=extraction.extraction_engine,
                    created_at=utc_now(),
                    warnings=list(extraction.warnings),
                )
                self.repository.write_text_blob(
                    extracted_text_path,
                    json.dumps(extracted_text.to_dict(), ensure_ascii=False, indent=2),
                )
                self.repository.save_extracted_text(extracted_text, extracted_text_path=extracted_text_path)
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
                extraction_status = "completed"
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
                extraction_status = "failed"

            refreshed = self.get_fascicolo_document(tenant_id, fascicolo_id, document_id, user_context)
            assert refreshed.status in DOCUMENT_AI_STATUSES
            upload_result = DocumentAIUploadResult(
                document=refreshed,
                version=version,
                text=extracted_text,
                extraction_status=extraction_status,
                warnings=list(extraction.warnings),
            )
            self.last_upload_result = _upload_result(version, extraction, status=extraction_status)
            return upload_result

    def upload_document_bytes_for_fascicolo(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        filename: str,
        content: bytes,
        mime_type: str | None,
        user_context: object,
        source_metadata: dict[str, Any] | None = None,
    ) -> DocumentAIUploadResult:
        upload = _BytesUpload(filename=filename, content=content, content_type=mime_type)
        result = self.upload_document_for_fascicolo(tenant_id, fascicolo_id, upload, user_context)
        if source_metadata and self.last_upload_result is not None:
            self.last_upload_result["source_metadata"] = dict(source_metadata)
        return result

    def build_lex_indexing_summary(
        self,
        tenant_id: str,
        fascicolo_id: str,
        sources: list[Any],
        user_context: object,
    ) -> LexIndexingSummary:
        from .indexer import DocumentAIIndexer

        return DocumentAIIndexer(self).summarize(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            sources=list(sources or []),
            user_context=user_context,
        )

    def process_lex_indexing_sources(
        self,
        tenant_id: str,
        fascicolo_id: str,
        sources: list[Any],
        user_context: object,
        *,
        retry_errors: bool = False,
    ):
        from .indexer import DocumentAIIndexer

        result = DocumentAIIndexer(self).process(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            sources=list(sources or []),
            user_context=user_context,
            retry_errors=retry_errors,
        )
        import logging
        logging.getLogger(__name__).info("Document AI: lettura terminata, indicizzati=%s saltati=%s errori=%s", result.indexed, result.skipped, len(result.errors))
        # Un'unica pipeline: ogni indicizzazione del fascicolo alimenta il
        # catalogo SQL, senza un secondo click e senza una seconda estrazione.
        if self.fascicoli_repository is not None and self.repository.backend_kind in {"sqlite", "postgresql"}:
            fascicolo = self.fascicoli_repository.get(fascicolo_id)
            logging.getLogger(__name__).info("Document AI: contesto catalogo disponibile=%s", fascicolo is not None)
            if fascicolo is not None:
                from .catalog_pipeline import FascicoloDocumentCatalogPipeline

                catalog = FascicoloDocumentCatalogPipeline(self.repository).run(
                    tenant_id=tenant_id, fascicolo=fascicolo, sources=list(sources or []),
                    actor=user_id_from_context(user_context), process=True,
                )
                if catalog.errors:
                    result.errors.extend(catalog.errors)
                    result.summary.warnings.extend(catalog.errors)
        return result

    def list_fascicolo_documents(
        self,
        tenant_id: str,
        fascicolo_id: str,
        user_context: object,
    ) -> list[DocumentAIRecord]:
        assert_user_can_read(user_context)
        self._assert_fascicolo_access(fascicolo_id)
        return self.repository.list_documents(tenant_id, fascicolo_id, user_context)

    def reacquire_existing_version(self, tenant_id: str, fascicolo_id: str, document_id: str, content: bytes, user_context: object, *, identity_recovery: bool = False) -> DocumentAIText:
        """Crea una nuova versione auditata dallo stesso blob, senza duplicare il record."""
        assert_user_can_write(user_context)
        self._assert_fascicolo_access(fascicolo_id)
        record = self.repository.get_document(tenant_id, fascicolo_id, document_id)
        if record is None:
            raise DocumentAINotFound("Documento AI non trovato.")
        if compute_sha256_bytes(content) != record.sha256:
            raise DocumentAIValidationError("Impronta del blob diversa dal documento corrente.")
        ensure_allowed_size(len(content), self.max_size_bytes)
        if identity_recovery:
            current_text = self.repository.get_extracted_text(tenant_id, fascicolo_id, document_id, record.current_version_id)
            from legal_ocr.motore.identita import RECUPERO_IDENTITA_VERSIONE
            if (current_text and IDENTITY_PROVENANCE_MARKER in current_text.warnings
                    and any(f'Recupero identità {RECUPERO_IDENTITA_VERSIONE}:' in warning for warning in current_text.warnings)):
                return current_text
        versions = self.repository.list_versions(tenant_id, fascicolo_id, document_id)
        candidates = [item for item in versions if item.sha256 == record.sha256 and item.storage_path]
        previous = next((item for item in candidates if item.id == record.current_version_id), None)
        if previous is None and candidates:
            previous = max(candidates, key=lambda item: item.version_number)
        extraction = (extract_text_from_document(content, record.original_filename, record.file_type, identity_scan=True)
                      if identity_recovery else extract_text_from_document(content, record.original_filename, record.file_type))
        if identity_recovery:
            archived = self.repository.get_extracted_text(tenant_id, fascicolo_id, document_id, record.current_version_id)
            if archived is None or not archived.text.strip():
                raise DocumentAIValidationError("Recupero identità senza lettura archiviata corrente.")
            extraction = _preserve_identity_archive(archived, extraction, RECUPERO_IDENTITA_VERSIONE)
        if not extraction.ok or not str(extraction.text or "").strip():
            raise DocumentAIValidationError("Riacquisizione non adottabile: testo affidabile assente.")
        number = next_version_number(versions)
        storage_path = previous.storage_path if previous else build_document_storage_relative_path(
            tenant_id, fascicolo_id, document_id, number, record.safe_filename)
        version = DocumentAIVersion(
            id=new_id("docaiver"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
            document_id=document_id, version_number=number, source=previous.source if previous else "upload",
            storage_path=storage_path, extracted_text_path=None, pdf_preview_path=None,
            sha256=record.sha256, created_by=user_id_from_context(user_context), created_at=utc_now(),
        )
        with self.repository.catalog_write_batch():
            if previous is None:
                self.repository.write_blob(storage_path, content)
            self.repository.create_version(version)
            text = DocumentAIText(document_id=document_id, version_id=version.id, tenant_id=tenant_id,
                fascicolo_id=fascicolo_id, text=extraction.text,
                pages=_pages_with_identity_sources(extraction.pages, extraction.identity_sources),
                extraction_engine=extraction.extraction_engine, created_at=utc_now(), warnings=list(extraction.warnings))
            text_path = build_extracted_text_relative_path(tenant_id, fascicolo_id, document_id, number)
            self.repository.write_text_blob(text_path, json.dumps(text.to_dict(), ensure_ascii=False, indent=2))
            self.repository.save_extracted_text(text, extracted_text_path=text_path)
            self.repository.set_current_version(tenant_id, fascicolo_id, document_id, version.id,
                status="ready", page_count=len(extraction.pages) if extraction.pages else None)
            record_document_ai_event(self.repository, "document_ai.version.created", tenant_id=tenant_id,
                fascicolo_id=fascicolo_id, user_context=user_context, document_id=document_id, version_id=version.id,
                sha256=record.sha256, filename=record.original_filename, status="ready",
                payload={"source":"reacquisition","previous_version_id":previous.id if previous else None,
                         "restored_missing_version":previous is None,"engine":extraction.extraction_engine,
                         "identity_recovery": identity_recovery,
                         "recovered_pages": [item.page_number for item in extraction.identity_recoveries]})
            record_document_ai_event(self.repository, "document_ai.extraction.completed", tenant_id=tenant_id,
                fascicolo_id=fascicolo_id, user_context=user_context, document_id=document_id, version_id=version.id,
                sha256=record.sha256, filename=record.original_filename, status="ready",
                payload={"engine":extraction.extraction_engine,"page_count":len(extraction.pages),"warnings":extraction.warnings})
        return text

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
        actor = user_id_from_context(user_context).strip().casefold()
        if actor not in _NON_INTERACTIVE_READ_ACTORS:
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
        if document.status != "ready":
            raise DocumentAIValidationError("Documento non indicizzato o non pronto per la ricerca.")
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


class _BytesUpload:
    def __init__(self, *, filename: str, content: bytes, content_type: str | None) -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = bytes(content)

    def read(self) -> bytes:
        return self._content

    def seek(self, _index: int) -> None:
        return None


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


DocumentIntelligenceService = DocumentAIService
