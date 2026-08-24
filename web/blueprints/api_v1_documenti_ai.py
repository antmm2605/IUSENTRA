"""API v1 UI per Documenti AI Fascicolo."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request

from pct.document_intelligence import DocumentAIRecord
from pct.document_intelligence.security import (
    DocumentAINotFound,
    DocumentAIPermissionDenied,
    DocumentAIValidationError,
)
from web.services.document_intelligence_runtime import (
    apply_sentenza_automation_for_document_text,
    build_document_ai_service,
    build_document_catalog_payload,
    build_lex_indexing_summary_payload,
    document_ai_tenant_id,
    document_ai_user_context,
    fascicoli_db_path,
    resolve_document_catalog_assignment,
)
from web.services.tenant_api_auth import api_key_valid_for_request

api_v1_documenti_ai = Blueprint("api_v1_documenti_ai", __name__, url_prefix="/api/v1/ui")


def _api_key_valida() -> bool:
    return api_key_valid_for_request()


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or _api_key_valida():
            return func(*args, **kwargs)
        return _errore("Autenticazione richiesta.", "permission_denied", 403)

    return wrapper


def _tenant_id() -> str:
    return document_ai_tenant_id()


def _fascicoli_db_path() -> str:
    return fascicoli_db_path()


def _user_context() -> dict[str, Any]:
    return document_ai_user_context()


def _errore(detail: str, code: str, status: int):
    return jsonify({"mock_fallback": False, "detail": detail, "code": code}), status


def _handle_error(exc: Exception):
    if isinstance(exc, DocumentAIValidationError):
        current_app.logger.info("Validazione Documenti AI non superata: %s", exc)
        return _errore("Richiesta non valida.", "validation_error", 400)
    if isinstance(exc, DocumentAIPermissionDenied):
        return _errore("Operazione non autorizzata", "permission_denied", 403)
    if isinstance(exc, DocumentAINotFound):
        return _errore("Documento o fascicolo non trovato", "not_found", 404)
    current_app.logger.exception("Errore Documenti AI Fascicolo")
    return _errore(
        "Errore interno durante l'elaborazione del documento",
        "document_ai_internal_error",
        500,
    )


def _serialize_document(document: DocumentAIRecord) -> dict[str, Any]:
    return {
        "id": document.id,
        "original_filename": document.original_filename,
        "safe_filename": document.safe_filename,
        "file_type": document.file_type,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "sha256": document.sha256,
        "status": document.status,
        "current_version_id": document.current_version_id,
        "page_count": document.page_count,
        "created_by": document.created_by,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _serialize_version(version: Any) -> dict[str, Any]:
    return {
        "id": version.id,
        "version_number": version.version_number,
        "source": version.source,
        "sha256": version.sha256,
        "created_at": version.created_at,
    }


def _capabilities() -> dict[str, bool]:
    return {
        "upload": False,
        "read": True,
        "search": True,
        "lex_tools": True,
        "generate_docx": False,
        "propose_edits": False,
        "compare": False,
    }


def _serialize_lex_indexing(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_documents": int(summary.get("total_documents") or 0),
        "ready": int(summary.get("ready") or 0),
        "queued": int(summary.get("queued") or 0),
        "indexing": int(summary.get("indexing") or 0),
        "errors": int(summary.get("errors") or 0),
        "stale": int(summary.get("stale") or 0),
        "not_indexed": int(summary.get("not_indexed") or 0),
        "archived": int(summary.get("archived") or 0),
        "last_indexed_at": summary.get("last_indexed_at") or None,
        "status": str(summary.get("status") or "ready"),
        "warnings": [str(item) for item in list(summary.get("warnings") or [])[:12]],
    }


@api_v1_documenti_ai.get("/fascicoli/<fascicolo_id>/documenti-ai")
@_richiedi_auth
def lista_documenti_ai(fascicolo_id: str):
    try:
        service = build_document_ai_service()
        documents = service.list_fascicolo_documents(_tenant_id(), fascicolo_id, _user_context())
        return jsonify(
            {
                "mock_fallback": False,
                "fascicolo_id": fascicolo_id,
                "documents": [_serialize_document(document) for document in documents],
                "capabilities": _capabilities(),
            }
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.get("/fascicoli/<fascicolo_id>/lex-indexing")
@_richiedi_auth
def stato_indicizzazione_lex(fascicolo_id: str):
    try:
        summary = build_lex_indexing_summary_payload(fascicolo_id, process=False)
        return jsonify({"mock_fallback": False, "fascicolo_id": fascicolo_id, "lex_indexing": _serialize_lex_indexing(summary)})
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.post("/fascicoli/<fascicolo_id>/lex-indexing/aggiorna")
@_richiedi_auth
def aggiorna_indice_lex(fascicolo_id: str):
    try:
        summary = build_lex_indexing_summary_payload(fascicolo_id, process=True)
        return jsonify({"mock_fallback": False, "fascicolo_id": fascicolo_id, "lex_indexing": _serialize_lex_indexing(summary)})
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.post("/fascicoli/<fascicolo_id>/lex-indexing/riprova-errori")
@_richiedi_auth
def riprova_errori_indice_lex(fascicolo_id: str):
    try:
        summary = build_lex_indexing_summary_payload(fascicolo_id, process=True, retry_errors=True)
        return jsonify({"mock_fallback": False, "fascicolo_id": fascicolo_id, "lex_indexing": _serialize_lex_indexing(summary)})
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.get("/fascicoli/<fascicolo_id>/catalogazione-documentale")
@_richiedi_auth
def catalogazione_documentale_fascicolo(fascicolo_id: str):
    try:
        payload = build_document_catalog_payload(fascicolo_id, process=False)
        return jsonify({"mock_fallback": False, **payload})
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.post("/fascicoli/<fascicolo_id>/catalogazione-documentale/aggiorna")
@_richiedi_auth
def aggiorna_catalogazione_documentale_fascicolo(fascicolo_id: str):
    try:
        raw = request.get_json(silent=True)
        payload = raw if isinstance(raw, dict) else request.form.to_dict(flat=True)
        retry = str(payload.get("retry") or "").strip().lower() in {"1", "true", "si"}
        # La GET React resta leggera. Prima dell'estrazione controlliamo il
        # catalogo SQL: se ogni hash corrente è già catalogato non riapriamo
        # PDF/P7M né rieseguiamo OCR, ma rieseguiamo solo il resolver
        # versionato. Questo rende il pulsante idempotente e reattivo.
        pre_catalog = build_document_catalog_payload(fascicolo_id, process=False)
        missing_current_assignment = any(
            bool(item.get("supported"))
            and (
                not isinstance(item.get("assignment"), dict)
                or str((item.get("assignment") or {}).get("document_sha256") or "")
                != str(item.get("sha256") or "")
            )
            for item in list(pre_catalog.get("documents") or [])
        )
        if retry or missing_current_assignment:
            lex_indexing = build_lex_indexing_summary_payload(
                fascicolo_id,
                process=True,
                retry_errors=retry,
            )
        else:
            # Tutti i documenti supportati hanno già un record Document AI e
            # una catalogazione SQL con la stessa impronta. Il bottone deve
            # quindi restituire subito lo stato corrente, senza riaprire la
            # pipeline di indicizzazione né automazioni estranee al refresh.
            supported = [item for item in list(pre_catalog.get("documents") or []) if item.get("supported")]
            lex_indexing = {
                "total_documents": len(supported),
                "ready": len(supported),
                "queued": 0,
                "indexing": 0,
                "errors": 0,
                "stale": 0,
                "not_indexed": 0,
                "archived": 0,
                "status": "ready",
                "warnings": [],
            }
        catalog = build_document_catalog_payload(fascicolo_id, process=True, retry=retry)
        return jsonify({"mock_fallback": False, "lex_indexing": _serialize_lex_indexing(lex_indexing), **catalog})
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.post("/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>/catalogazione-documentale/revisione")
@_richiedi_auth
def revisione_catalogazione_documentale(fascicolo_id: str, documento_id: str):
    try:
        raw = request.get_json(silent=True)
        payload = raw if isinstance(raw, dict) else request.form.to_dict(flat=True)
        status = str(payload.get("status") or "").strip().lower()
        note = str(payload.get("note") or "").strip()
        if len(note) > 2000:
            raise DocumentAIValidationError("Nota di revisione troppo lunga.")
        assignment = resolve_document_catalog_assignment(
            fascicolo_id,
            documento_id,
            status=status,
            note=note,
        )
        return jsonify({"mock_fallback": False, "assignment": assignment, "message": "Revisione della catalogazione registrata nel fascicolo."})
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.post("/fascicoli/<fascicolo_id>/documenti-ai/upload")
@_richiedi_auth
def upload_documento_ai(fascicolo_id: str):
    try:
        uploaded = request.files.get("file")
        if uploaded is None:
            raise DocumentAIValidationError("File mancante.")
        service = build_document_ai_service()
        upload_outcome = service.upload_document_for_fascicolo(_tenant_id(), fascicolo_id, uploaded, _user_context())
        document = upload_outcome.document
        upload_result = service.last_upload_result or {}
        version = upload_result.get("version") or upload_outcome.version
        extraction = upload_result.get("extraction") or {}
        sentence_automation = None
        if upload_outcome.text is not None:
            metadata = {
                "tenant_id": _tenant_id(),
                "fascicolo_id": fascicolo_id,
                "document_id": document.id,
                "sha256": document.sha256,
                "filename": document.original_filename,
                "safe_filename": document.safe_filename,
                "source": "document_ai_upload",
            }
            sentence_automation = apply_sentenza_automation_for_document_text(
                fascicolo_id=fascicolo_id,
                tenant_id=_tenant_id(),
                document_id=document.id,
                text=upload_outcome.text.text,
                metadata=metadata,
                actor=str((_user_context() or {}).get("user_id") or "Document AI"),
            )
        return (
            jsonify(
                {
                    "mock_fallback": False,
                    "document": _serialize_document(document),
                    "version": _serialize_version(version) if version else None,
                    "extraction": {
                        "status": extraction.get("status") or ("completed" if document.status == "ready" else "failed"),
                        "engine": extraction.get("engine") or "",
                        "page_count": extraction.get("page_count"),
                        "warnings": extraction.get("warnings") or [],
                    },
                    "sentenza_automation": sentence_automation,
                }
            ),
            201,
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.get("/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>")
@_richiedi_auth
def dettaglio_documento_ai(fascicolo_id: str, documento_id: str):
    try:
        service = build_document_ai_service()
        document, versions, audit_summary = service.get_fascicolo_document_detail(
            _tenant_id(),
            fascicolo_id,
            documento_id,
            _user_context(),
        )
        return jsonify(
            {
                "mock_fallback": False,
                "document": _serialize_document(document),
                "versions": [_serialize_version(version) for version in versions],
                "audit_summary": audit_summary,
            }
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.get("/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>/testo")
@_richiedi_auth
def testo_documento_ai(fascicolo_id: str, documento_id: str):
    try:
        service = build_document_ai_service()
        text = service.get_fascicolo_document_text(_tenant_id(), fascicolo_id, documento_id, _user_context())
        return jsonify(
            {
                "mock_fallback": False,
                "document_id": text.document_id,
                "version_id": text.version_id,
                "status": "ready",
                "extraction_engine": text.extraction_engine,
                "page_count": len(text.pages) if text.pages else None,
                "text": text.text,
                "pages": [page.to_dict() for page in text.pages],
                "warnings": list(text.warnings),
            }
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_documenti_ai.post("/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>/cerca")
@_richiedi_auth
def cerca_documento_ai(fascicolo_id: str, documento_id: str):
    try:
        payload = request.get_json(silent=True) or {}
        query = str(payload.get("query") or "").strip()
        if not query:
            raise DocumentAIValidationError("Query di ricerca mancante.")
        max_results = int(payload.get("max_results") or 20)
        service = build_document_ai_service()
        results = service.search_fascicolo_document(
            _tenant_id(),
            fascicolo_id,
            documento_id,
            query,
            _user_context(),
            max_results=max_results,
        )
        return jsonify(
            {
                "mock_fallback": False,
                "document_id": documento_id,
                "query": query,
                "results": [
                    {
                        "page_number": result.page_number,
                        "snippet": result.snippet,
                        "start_offset": result.start_offset,
                        "end_offset": result.end_offset,
                    }
                    for result in results
                ],
            }
        )
    except Exception as exc:
        return _handle_error(exc)
